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
import textwrap
from gemini_response import GeminiResponse

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
  "max_output_tokens": 100000,
}

effect = genai.protos.Schema(
  type=genai.protos.Type.OBJECT,
  properties = {
    'name': genai.protos.Schema(type=genai.protos.Type.STRING),
    'adjustment': genai.protos.Schema(type=genai.protos.Type.STRING),
    }
  )

video_edit = genai.protos.Schema(
  type = genai.protos.Type.OBJECT,
  properties = {
    'video_name': genai.protos.Schema(type=genai.protos.Type.STRING),
    'id': genai.protos.Schema(type=genai.protos.Type.NUMBER),
    'start_time': genai.protos.Schema(type=genai.protos.Type.STRING),
    'end_time': genai.protos.Schema(type=genai.protos.Type.STRING),
    'edit': genai.protos.Schema(
      type = genai.protos.Type.OBJECT,
      properties = {
        'type': genai.protos.Schema(type=genai.protos.Type.STRING)
      }
      ),
    'effects': genai.protos.Schema(
      type=genai.protos.Type.ARRAY,
      items = effect
      ),
    'text': genai.protos.Schema(type=genai.protos.Type.STRING),
    'transition': genai.protos.Schema(
      type = genai.protos.Type.OBJECT,
      properties = {
        'type': genai.protos.Schema(type=genai.protos.Type.STRING)
        }
    )
  }
)

video_edits = genai.protos.Schema(
  type = genai.protos.Type.ARRAY,
  items = video_edit
)

gemini_json = genai.protos.Schema(
  type = genai.protos.Type.OBJECT,
  properties = {
    'video_edits': video_edits
  }
)

edits = genai.protos.Tool(
  function_declarations=[
    genai.protos.FunctionDeclaration(
      name='video_edits',
      description='returns a json object of all the video edit settings',
      parameters = video_edits
    )
  ]
)

model = genai.GenerativeModel(
  model_name="gemini-1.5-flash",
  generation_config=generation_config,
  tools = edits
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
            video_data.append(video_durations)

        wait_for_file_active(video_data[0])
        print(f"final vid = {video_data[0]}")
        print("sleeping now... switch network")
        sleep(60)

        # Prompt the Gemini API with all videos and the prompt
        gemini_response = prompt_gemini_api(video_data[0], gemini_prompt, video_data[1])
        print(gemini_response.candidates)

        # Return the response to the Android app
        return {'gemini_response': gemini_response.text}

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Function to download a video from Firebase Storage
def download_video(video_path, file_path):
    storage_client = storage
    bucket = storage_client.bucket('craiteapp.appspot.com')
    blob = bucket.blob(video_path)
    blob.download_to_filename(file_path)

# Function to prompt the Gemini API 
def prompt_gemini_api(video_file, gemini_prompt, video_durations):
    user_prompt = "You are a video editor. The given video could either be a single video or a sequence of concatenated videos. For the concatenated video, below are some key-value pairs of the video name alongside its start and end time (video: [start time, end time])\\n\"" + str(video_durations) + "\"\\nThis is what i want for my final video: \"" + gemini_prompt + "\"\\nEven though I have given you a single video, using the above video names and timestamps, treat each as a single video and understand whats going on based on the sound, actions and interactions. The goal is for you to create a video approximately 30 seconds long."

    prompt = textwrap.dedent("""
   You are to create it by understanding what is happening in the video as well as what is I want for the final video and suggest various edit functionalities in a purely json format. Even if I did not specify how the video should look like or it isn't clear, make sure you can identify relevant parts or clips of the video that will match the audio and if how the video should look like was specified, make sure your suggestions matches it too. 
  The goal is to capture and suggest the key moments and best parts of the video(s) while making sure they all sum up to at most the time limit. You are to suggest the text formatting(bold, italics, underline,font size, text positioning), perform video editing like changes in brightness, contrast, saturation, exposure, sharpness, cropping & resizing, effects, rotation and flipping, trimming, splitting and cutting, adding text overlays, speed changes, transitions, and captions. Different edit functionalities can be performed on a single video at different time intervals and the videos must not appear chronologically. You decide how they appear based on the message you are trying to pass. You can trim a single video clip multiple times at different timestamps if possible. 

  These are the various edit functionalities a you must use on the video. All must not be used at one. Select which is most appropriate for the given scenario and goal.

  You are to carry out this by proposing time stamp intervals for each video and the edit fuctionalities to be performed during that interval. You decide on which edits go where based on what is expected of you and the goal is to make the result as interesting, creative and as engaging as possible. Try as much as possible to identify the specified content type if mentioned and work towards delivering something creative in that area or get creative and come up wit what you believe is best. Some of this content type include comedy skits, dance trends, lip-syncing, tutorials, product demons, vlogs, reviews, etc. You will suggest how the videos are displayed and what to include or exclude so as to pass the information needed or make it as interesting and creative as possible. Make the you try to make the audio sync with the video for better results. 

  Below is a list of all the video editting functionalities:
  - Basic Adjustments:
      Brightness: Adjusts the overall lightness or darkness of the video.
      Contrast: Controls the difference between light and dark areas in the video, creating a more dramatic or flat look.
      Saturation: Alters the intensity of colors within the video, making them appear more vibrant (higher saturation) or muted (lower saturation).
      Exposure: Controls the overall amount of light captured in the video. Adjusting exposure can affect brightness and contrast.
      Sharpness: Enhances the crispness and definition of edges in the video.

  - Transformations:
      Resize: Changes the dimensions (width and height) of the video clip.
      Crop: Defines a specific rectangular area to focus on within the video frame.

  - Effects:
      Speed: Controls the playback speed of the video clip. Values greater than 1.0 speed up the video, while values less than 1.0 slow it down.

  - Text Overlays:
      Label: Defines the text content to be displayed on the screen.
      Position: Specifies the location of the text overlay (e.g., top-center, bottom-right).
      Font Size: Sets the size of the text.
      Color: Defines the color of the text.
      Duration: Determines how long the text overlay appears on the screen.

  - Transitions:
      Cut: An abrupt transition from one clip to the next without any fade effect.
      Dissolve: A gradual fade from one clip to the next, creating a smoother transition.
      (There can be other transition types available depending on your editing software.)

  - Audio Edits:
      Sound Effects: External audio elements inserted at specific points in the video to enhance specific moments.
      Fade In/Out: Gradual increase or decrease in volume at the beginning and end of the video, respectively.

  - Global Edits:
  These edits apply to the entire video project:
      Call to Action Overlay: Text overlay prompting viewers to take a specific action, like visiting a website or subscribing to a channel.
      Social Media Handle Overlay: Subtly displays your social media handle throughout the video for audience connection.

  For now, you will come up with proposed video edis. Below is a sample response
  {
      "video_edits": [
          {
        "video_name": "video_1",
        "id": 1
        "start_time": 0.0,
        "end_time": 20.0,
        "edit": {
          "type": "trim"
        },
        "transform": "None",
        "effects": [
          {
            "name": "speed",
            "adjectment": 1.2  // Increase speed slightly for a fast-paced feel
          },
          {
            "name": "brightness",
            "adjustment": 0.1  // Adjust based on video content
          },
          {
            "name": "contrast",
            "adjustment": 0.15  // Adjust based on video content
          }
        ],
        "text": [],
        "transition": {
          "type": "cut"  // Suggest quick cuts for a dynamic vibe
        }
      },
      {
        "video_name": "video_2",
        "id": 2
        "start_time": 0.0,
        "end_time": 10.0,
        "edit": {
          "type": "trim"
        },
        "transform": "None",
        "effects": [
          {
            "name": "saturation",
            "adjustment": 0.1  // Adjust based on video content
          },
          {
            "name": "sharpen",
            "adjustment": 0.5  // Adjust based on video content
          }
        ],
        "text": [],
        "transition": {
          "type": "dissolve"  // Use dissolve for celebration clip
        }
      // ... other video edits for clip 2 and beyond ...
      ]
      
      
  }

  Now come up with a pure json response of the various different video edits per clip. Here is a breakdown of all the available functionalities of the "video_edits" part:
  video_edits:
  This part defines edits for each video clip of project. A video clip are the various inputed videos. You are to perform different edits per clip basd on the available functions below. Each video edit object contains properties that control how that specific clip is handled:
  video_name: (String) The name of the video clip used in the project.
  start_time: (Number) The starting point of the video clip you are suggesting based of the video name  (in seconds).
  end_time: (Number) The ending point of the new video clip you are suggesting vased on the existing video you are suggesting (in seconds).
  edit: (Object) Defines the type of edit applied:
  type: (String) Can be "trim" for shortening the clip, or other edit types supported by your editing software.
  transform: (Object) Optional, specifies any transformations applied:
  Can include properties like "resize" for changing dimensions or "crop" for defining a specific area of focus.
  effects: (Array) A list of effects applied to the clip:
  Each effect is an object with a name property (e.g., "speed", "reverse", "blur", ) and an adjustment value (strength of the effect)
  text: (Array) Optional, defines text overlays within the clip:
  Each text object specifies properties like "label" (text content), "position" (location on screen), "font_size", "color", and "duration" (time the text appears).
  transition: (Object) Optional, defines the transition used when switching to the next clip:
  Has a type property that can be "cut" (abrupt transition), "dissolve" (gradual fade), or other transitions available in your software.

  If for whatsoever reason you cannot produce a response or come up with video editing functionalities, simply write 'cannot produce response'. Otherwise, the response should be in pure raw json format given the structure above. Make sure you don't exceed the maximum output tokens of 100000
  """)
    new_prompt = user_prompt + prompt
    response = model.generate_content([video_file, new_prompt], tool_config={'function_calling_config':'ANY'})
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
    file = genai.get_file(file.name)

  if file.state.name == "FAILED":
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


    

def return_video_edit(video_name, _id, start_time, end_time, edit, effects, text, transition):
  return {
    'video_name': video_name,
    'id': _id,
    'start_time': start_time,
    'end_time': end_time,
    'edit': edit,
    'effects': effects,
    'text': text,
    'transition': transition
  }

def return_effect(name, adjustment):
  return {
    'name': name,
    'adjustment': adjustment,
    }



