from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, storage, auth
from google.cloud import aiplatform
import os
import tempfile
import requests  
import google.generativeai as genai
import concurrent.futures
from time import sleep
from dotenv import load_dotenv
from moviepy.editor import VideoFileClip, concatenate_videoclips
import uuid

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
  "temperature": 1,
  "top_p": 0.95,
  "top_k": 64,
  "max_output_tokens": 8192,
  "response_mime_type": "application/json",
}

model = genai.GenerativeModel(
  model_name="gemini-1.5-flash",
  generation_config=generation_config,
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

        if not (project_id and user_id and gemini_prompt):
            return jsonify({'error': 'Missing required parameters'}), 400

        # Verify user
        try:
            user = auth.get_user(user_id)
        except auth.UserNotFoundError:
            return jsonify({'error': 'Invalid user ID'}), 401

        # Download videos and prepare data for Gemini API
        video_directory = f"users/{user_id}/projects/{project_id}/videos"
        video_paths = get_all_file_paths(video_directory)
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
                download_video(video_path, file_path)

                # adds key-value pairs of file_name: file_path to a downloaded_video_paths dictionary
                downloaded_video_paths[file_path] = file_path

                # Uploads video to Gemini
                # gemini_video = upload_to_gemini(file_path)
                # video_data.append(gemini_video)

            # Concatenate video
            concatenated_video_path, video_durations, total_duration = concatenate_videos(downloaded_video_paths, temp_dir)
            print(concatenated_video_path)
            print(video_durations)
            print(total_duration)

            # upload concatenated video to Gemini
            gemini_video = upload_to_gemini(concatenated_video_path)
            video_data.append(gemini_video)

        wait_for_file_active(video_data[0])
        print(f"final vid = {video_data[0]}")

        # Prompt the Gemini API with all videos and the prompt
        gemini_response = prompt_gemini_api(video_data[0], gemini_prompt)

        # Return the response to the Android app
        return jsonify({'gemini_response': gemini_response})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Function to download a video from Firebase Storage
def download_video(video_path, file_path):
    storage_client = storage
    bucket = storage_client.bucket('craiteapp.appspot.com')
    blob = bucket.blob(video_path)
    blob.download_to_filename(file_path)

# Function to prompt the Gemini API 
def prompt_gemini_api(video_file, gemini_prompt):
    response = model.generate_content([video_file, gemini_prompt])
    return response

def upload_to_gemini(path, mime_type=None):
  """Uploads the given file to Gemini.

  See https://ai.google.dev/gemini-api/docs/prompting_with_media
  """
  if not os.path.exists(path):
    raise Exception(f"File not found: {path}")

  file = genai.upload_file(path, mime_type=mime_type)
  print(f"Uploaded file '{file.display_name}' as: {file.uri}")
  return file

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
    file = genai.get_file(video_file.name)

  if video_file.state.name == "FAILED":
    raise ValueError(file.state.name)

    print("...file ready")


# Function to check if a video belongs to the user
def video_belongs_to_user(video_path, user_id):
    # Assuming your Firebase Storage structure is like: users/{userId}/projects/{projectId}/videos/...
    return video_path.startswith(f'users/{user_id}/')

# Function to get all files in a Firebase cloud storage dir
def get_all_file_paths(directory):
    bucket = storage.bucket()
    blobs = bucket.list_blobs(prefix=directory)
    return [blob.name for blob in blobs if not blob.name.endswith('/')]

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

  return output_clip_path, durations, total_duration


if __name__ == '__main__':
    app.run(debug=True)