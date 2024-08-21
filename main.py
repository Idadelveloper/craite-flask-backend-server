from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, storage, auth, firestore
from google.cloud import aiplatform
import os
import tempfile
import requests  
import google.generativeai as genai
from google.generativeai.protos import HarmCategory, SafetySetting
import concurrent.futures
from time import sleep
from dotenv import load_dotenv
from moviepy.editor import VideoFileClip, concatenate_videoclips
import uuid
import textwrap
import json
import ffmpeg
import traceback
from firebase import Firebase
from gemini import Gemini

# Initialize Flask app
app = Flask(__name__)

load_dotenv()

# Initialize Firebase
cred = credentials.Certificate(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))
firebase_admin.initialize_app(cred, {
    'storageBucket': 'craiteapp.appspot.com'
})

# Initialize Gemini API client
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Create the model
generation_config = {
  "temperature": 0.7,
  "top_p": 0.95,
  "top_k": 64,
  "max_output_tokens": 200000,
}


model = genai.GenerativeModel(
  model_name="gemini-1.5-pro-exp-0801",
  generation_config=generation_config
)


# Route to handle requests from the Android app
@app.route('/process_videos', methods=['POST'])
def process_videos():
    try:
        # Get data from the request (assuming JSON format)
        data = request.get_json()
        user_id = data.get('user_id')
        gemini_prompt = data.get('gemini_prompt')
        project_id = data.get('project_id')
        prompt_id = data.get('prompt_id')

        if not (project_id and user_id and gemini_prompt):
            return jsonify({'error': 'Missing required parameters'}), 400

        # Verify user
        try:
            user = auth.get_user(user_id)
        except auth.UserNotFoundError:
            return jsonify({'error': 'Invalid user ID'}), 401
          
        # Download audio if any and prepare for the Gemini API
        bucket = storage.bucket()
        audio_directory = f"users/{user_id}/projects/{project_id}/audios"
        audio_paths = Firebase.get_all_file_paths(audio_directory, bucket)
        downloaded_audio_paths = dict()
        

        # Download videos and prepare data for Gemini API
        video_directory = f"users/{user_id}/projects/{project_id}/videos"
        video_paths = Firebase.get_all_file_paths(video_directory, bucket)
        downloaded_video_paths = dict()
        video_data = []
        with tempfile.TemporaryDirectory() as temp_dir:
            for video_path in video_paths:
                # Check if the video belongs to the user
                if not video_belongs_to_user(video_path, user_id):
                    return jsonify({'error': 'Unauthorized access to video'}), 403

                # Download the video
                file_name = video_path.split('/')[-1]
                file_path = os.path.join(temp_dir, file_name)
                Firebase.download_media(video_path, file_path, bucket)

                # adds key-value pairs of file_name: file_path to a downloaded_video_paths dictionary
                downloaded_video_paths[file_path] = file_path

                # Uploads video to Gemini
            file_name, audio_file_path = False, False
            if len(audio_paths) > 0:
              file_name = audio_paths[-1].split('/')[-1]
              audio_file_path = os.path.join(temp_dir, file_name)
              Firebase.download_media(audio_paths[-1], audio_file_path, bucket)

            # Concatenate video
            concatenated_video_path, video_durations, total_duration = concatenate_videos(downloaded_video_paths, temp_dir)
            
            # upload concatenated video and audio to Gemini
            gemini_video = Gemini.upload_to_gemini(path=concatenated_video_path, genai=genai)
            if audio_file_path:
              gemini_audio = Gemini.upload_to_gemini(path=audio_file_path, genai=genai)
            else:
              gemini_audio = None
            
            
            video_data.append(gemini_video)
            video_data.append(video_durations)
            video_data.append(total_duration)
            video_data.append(gemini_audio)

        wait_for_file_active(video_data[0])
        print(f"final vid = {video_data[0]}")
        
        if video_data[3]:
          wait_for_file_active(video_data[3])
          print(f"final vid = {video_data[3]}")
        
        

        # Prompt the Gemini API with all videos and the prompt
        try:
          gemini_response = Gemini.prompt_gemini_api(video_data[0], gemini_prompt, video_data[1], video_data[3], model)
          print(gemini_response)

            # Store Gemini response in Firestore
          db = firestore.client()
          if prompt_id:
            Firebase.store_gemini_response(user_id, project_id, prompt_id, gemini_response, db)


          # Return the response to the Android app
          print(gemini_response)
          return {'gemini_response': gemini_response}
        except Exception as e:
          print(f"Error calling Gemini API: {e}")

        

    except Exception as e:
        print(f"Error processing videos: {e}")
        traceback.print_exc()  # Print the full traceback
        return jsonify({'error': str(e)}), 500


def wait_for_files_active(files):
  """Waits for the given files to be active.

  Some files uploaded to the Gemini API need to be processed before they can be
  used as prompt inputs. The status can be seen by querying the file's "state"
  field.

  This implementation uses a simple blocking polling loop. Production code
  should probably employ a more sophisticated approach.
  """
  print("Waiting for file processing...")
  for name in (file.name for file in files):
    file = genai.get_file(name)
    while file.state.name == "PROCESSING":
      print(".", end="", flush=True)
      time.sleep(10)
      file = genai.get_file(name)
    if file.state.name != "ACTIVE":
      raise Exception(f"File {file.name} failed to process")
  print("...all files ready")


def wait_for_file_active(file, timeout=1000):
  """Waits for the given file to become active in Gemini.

  Uses asynchronous waiting to avoid blocking the main thread.

  Args:
      file: The Genai file object to wait for.
      timeout: Maximum waiting time in seconds (default: 60).

  Raises:
      Exception: If the file fails to process within the timeout or encounters
                  an unexpected error.
  """

  while file.state.name == "PROCESSING":
    print('.', end='')
    sleep(240)
    file = genai.get_file(file.name)

  if file.state.name == "FAILED":
    raise ValueError(file.state.name)

    print("...file ready")


# Function to check if a video belongs to the user
def video_belongs_to_user(video_path, user_id):
    # Assuming your Firebase Storage structure is like: users/{userId}/projects/{projectId}/videos/...
    return video_path.startswith(f'users/{user_id}/')


def concatenate_videos(video_data, output_dir):
  """Concatenates multiple videos from a dictionary and returns the output path,
  durations, and total duration.

  Args:
      video_data: A dictionary with video names as keys and their paths as values.
      output_path: The path to save the concatenated video.

  Returns:
      A tuple containing:
          - The output path of the concatenated video.
          - A dictionary with video names as keys and lists of [start_timestamp, end_timestamp] for durations.
          - The total duration of the concatenated video in seconds.
  """

  clips = []
  durations = {}
  total_duration = 0

  for video_name, video_path in video_data.items():
    clip = VideoFileClip(video_path)
    clips.append(clip)
    duration = clip.duration
    durations[video_name] = [total_duration, total_duration + duration]
    total_duration += duration

  basename, extension = os.path.splitext(os.path.basename(next(iter(video_data.values()))))
  new_filename = f"{basename}_{uuid.uuid4()}{extension}"
  output_clip_path = os.path.join(output_dir, new_filename)

  final_clip = concatenate_videoclips(clips)
  final_clip.write_videofile(output_clip_path)
  print(f"Concatenated videos saved to: {output_clip_path}")
  print(final_clip.size)

  return output_clip_path, durations, total_duration
    

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')


    





