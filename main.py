from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, storage, auth, firestore
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
import json

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
  tools = [edits]
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
        try:
          gemini_response = prompt_gemini_api(video_data[0], gemini_prompt, video_data[1])
          print("sleeping again... switch network")
          sleep(60)
          print(gemini_response)

            # Store Gemini response in Firestore
          if prompt_id:
            store_gemini_response(user_id, project_id, prompt_id, gemini_response)


          # Return the response to the Android app
          return {'gemini_response': gemini_response}
        except Exception as e:
          print(f"Error calling Gemini API: {e}")

        

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def return_empty_response():
  effects = [return_effect("", "")]
  text = [return_text("", "", "", "")]
  return {
    "video_edits": [return_video_edit("", "", "", "", effects, text, "")]
  }

def store_gemini_response(user_id, project_id, prompt_id, gemini_response):
    """Stores the Gemini response in Firestore."""
    try:
      # Get firestore client
      db = firestore.client()

      # Assuming your Firestore structure is like: users/{userId}/projects/{projectId}/prompts/{promptId}
      doc_ref = db.collection("users").document(user_id) \
          .collection("projects").document(str(project_id)) \
          .collection("prompts").document(prompt_id)

      doc_ref.update({"geminiResponse": gemini_response})
      print(f"Gemini response stored for prompt ID: {prompt_id}")
    except Exception as e:
        print(f"Error storing Gemini response: {e}")


def return_video_edit(_id, video_name, start_time, end_time, effects, text, transition):
  return {
    'id': _id,
    'video_name': video_name,
    'start_time': start_time,
    'end_time': end_time,
    'effects': effects,
    'text': text,
    'transition': transition
  }

def return_effect(name, adjustment):
  return {
    'name': name,
    'adjustment': adjustment,
    }

def return_text(text, font_size, text_color, background_color):
  return {
    "text": text,
    "font_size": font_size,
    "text_color": text_color,
    "background_color": background_color
  }


# Function to download a video from Firebase Storage
def download_video(video_path, file_path):
    storage_client = storage
    bucket = storage_client.bucket('craiteapp.appspot.com')
    blob = bucket.blob(video_path)
    blob.download_to_filename(file_path)

# Function to prompt the Gemini API 
def prompt_gemini_api(video_file, gemini_prompt, video_durations):
    user_prompt = "You are a video editor. Given a video (which might be a concatenation of multiple clips), \\n\"" + str(video_durations) + "\"\\nThis is what the user wants for their final video final video: \"" + gemini_prompt + "\"\\nEven though you have been provided a single video, using the above video names and timestamps, treat each as a single video and understand whats going on based on the sound, actions and interactions. The goal is for you to create a video not more than 60 seconds long.\n Make sure you identify each clip by looking at its video name above and check its corresponding timeframe based on its start and ending timestamp in the inputted video. After identifying a video, treat it as an independent video. Forexample if you identify a video from the 10th to the 15th second, treat that video as a independent 5 second video. All the videos you identify and isolate will be considered as the videoclips where you will carryout various edit functionalities on them"

    prompt = textwrap.dedent("""
    You are to create edit settings by understanding what is happening in each of the video clips you identified as stated above as well as what the user wants for the final video and suggest various edit functionalities in a purely json format. Even if the user did not specify did not specify how the video should look like or it isn't clear, make sure you can identify relevant parts or clips of the video that will match the audio and if how the video should look like was specified, make sure your suggestions matches it too. 
    The goal is to capture and suggest the key moments and best parts of the video(s) while making sure they all sum up to at most the time limit. You are to suggest the text overlays, perform video editing like changes in brightness, contrast, saturation. Different edit functionalities can be performed on a single video clip at different time intervals and the videos must not appear in the order they came in. You decide how they appear based on the message you are trying to pass. You can trim a single video clip multiple times at different timestamps if possible. 

    Here is a sample of how the json response you must return should look like:
    "video_edits": [
              {
                  "id": 1,
                  "video_name": "/tmp/tmpn45wu176/video_0_1718959816080.mp4",
                  "start_time": 0.734861348165432,
                  "end_time": 3.530177287369108,
                  "effects": [
                      {
                          "name": "brightness",
                          "adjustment": [0.3333637]
                      }
                  ],
                  "text": [
                      {
                          "text": "Having some coffee with my sister",
                          "font_size": 28,
                          "text_color": "#3de490",
                          "background_color": "#80000000"
                      }
                      
                  ],
                  "transition": "fade"
                  
              },
              {
                  "id": 2,
                  "video_name": "/tmp/tmpn45wu176/video_1_1718959816136.mp4",
                  "start_time": 0.401773244161053,
                  "end_time": 2.8618605101782535,
                  "effects": [
                      {
                          "name": "brightness",
                          "adjustment": [-0.46320993]
                      },
                      {
                          "name": "contrast",
                          "adjustment": [0.3143587]
                      },
                      {
                          "name": "saturation",
                          "adjustment": [1.4236718]
                      }
                  ],
                  "text": [
                      {
                          "text": "The coffee tasted delicious",
                          "font_size": 26,
                          "text_color": "#223a18",
                          "background_color": "#80000000"
                      }
                      
                  ],
                  "transition": ""
                  
              },
              {
                  "id": 3,
                  "video_name": "/tmp/tmpn45wu176/video_3_1718959816192.mp4",
                  "start_time": 3.49878691889803517,
                  "end_time": 6.981376295379518,
                  "effects": [
                      {
                          "name": "brightness",
                          "adjustment": [-0.46320993]
                      },
                      {
                          "name": "saturation",
                          "adjustment": [1.3028498]
                      }
                  ],
                  "text": [
                      {
                          "text": "Guess who walked in? My brother",
                          "font_size": 26,
                          "text_color": "#171f34",
                          "background_color": "#80000000"
                      }
                      
                  ],
                  "transition": "fade"
                  
              },
              {
                  "id": 4,
                  "video_name": "/tmp/tmpn45wu176/video_4_1718959816213.mp4",
                  "start_time": 0.665023107211262,
                  "end_time": 2.9066618703894362,
                  "effects": [
                      {
                          "name": "saturation",
                          "adjustment": [0.506017]
                      }
                  ],
                  "text": [],
                  "transition": "slide"
                  
              },
              {
                  "id": 5,
                  "video_name": "/tmp/tmpn45wu176/video_4_1718959816213.mp4",
                  "start_time": 4.268023107211265,
                  "end_time": 8.5066638703894361,
                  "effects": [
                      {
                          "name": "brightness",
                          "adjustment": [0.032896698]
                      },
                      {
                          "name": "contrast",
                          "adjustment": [0.018022478]
                      }
                  ],
                  "text": [],
                  "transition": "cross-fade"
                  
              },
              {
                  "id": 6,
                  "video_name": "/tmp/tmpn45wu176/video_5_1718959816192.mp4",
                  "start_time": 0.8979263059372027,
                  "end_time": 3.355789246300705,
                  "effects": [
                      {
                          "name": "brightness",
                          "adjustment": [-0.40000975]
                      },
                      {
                          "name": "contrast",
                          "adjustment": [0.8433415]
                      },
                      {
                          "name": "saturation",
                          "adjustment": [1.0755221]
                      }
                  ],
                  "text": [
                      {
                          "text": "We all had such a great time",
                          "font_size": 22,
                          "text_color": "#f97b5d",
                          "background_color": "#80000000"
                      }
                      
                  ],
                  "transition": "fade"
                  
              }
          ]
    }

    Let's break down this JSON response and understand what each part of the video edit settings means:
    Think of this JSON like a recipe for editing a bunch of videos and stitching them together. Each item in the video_edits list is like instructions for a single video clip.
    Let's look at one of these video edit instructions:

    {
        "id": 1,
        "video_name": "/tmp/tmpn45wu176/video_0_1718959816080.mp4",
        "start_time": 0.734861348165432,
        "end_time": 3.530177287369108,
        "effects": [
            {
                "name": "brightness",
                "adjustment": [0.3333637]
            }
        ],
        "text": [
            {
                "text": "Having some coffee with my sister",
                "font_size": 28,
                "text_color": "#3de490",
                "background_color": "#80000000"
            }
        ],
        "transition": "fade"
    }

    Here's what each part means:
    - id: This is like a unique number tag for the trimmed version of this video clip. So, after we trim this video, we'll think of it as "video clip number 1". This is important for putting the clips in the right order later. It's always a whole number (an integer).
    - video_name: This is the video name assigneed to that video clip. It's like saying, "Hey, go find this specific video to work with." Each video has a unique name, so we don't get them mixed up.
    - start_time: This tells us where to start chopping the video, measured in seconds. It's a decimal number (a float) because we might want to start at a very precise moment, like 0.734 seconds in. The start_time MUST not begin at 0
    - end_time: This tells us where to stop chopping the video, also in seconds and also a float for precision. So, for this clip, we're only using the part of the video between 0.734 seconds and 3.530 seconds. The end_time MUST not begin at the last second.


    effects: This is a list of special visual tweaks we want to apply to the video clip. Think of it like adding filters on Instagram. Right now, we only have three options:
    - **`brightness`:** This controls how bright or dark the clip looks.  The adjustment value is a number between -1 and 1.  Zero means no change, positive numbers make it brighter, and negative numbers make it darker.  In this example, 0.333 makes the clip a bit brighter.
    - **`contrast`:** This controls the difference between the darkest and lightest parts of the clip.  Again, the adjustment is between -1 and 1.  Zero means no change, positive numbers increase the contrast (making darks darker and lights lighter), and negative numbers decrease the contrast (making everything look more similar in brightness).
    - **`saturation`:** This controls how vivid the colors in the clip are.  Zero means black and white, 1 means normal colors, and numbers above 1 make the colors super intense.
    text: This is a list of text overlays we want to put on top of the video. Each text overlay has:
    - **`text`:** The actual words to display.
    - **`font_size`:** How big the text should be in pixels for a mobile device
    - **`text_color`:** The color of the text, written as a hex code (like #3de490 for a greenish color).
    - **`background_color`:** The color behind the text, also a hex code.  "#80000000" means a semi-transparent black, so the video can still be seen a bit behind the text.

    transition: This tells us how to smoothly blend this clip with the next one in the sequence. "fade" means the clip will slowly fade out as the next one fades in. There are other options like "slide" or "cross-fade". If it's empty (like in the second video edit), there's no special transition.


    Important Notes:
    - Multiple Edits on One Video: You noticed that video IDs 4 and 5 use the same video_name. This means we can take different chunks of the same video clip and edit them separately!
    - No Text Required: Some video edits might not have any text overlays, like video ID 5. That's totally fine!
    No Effects Required: Some videos might also not have any effects.
    - When suggesting the start_time and end_time for a video clip to be trimmed, remember to isolate that clip. If that clip happened to be between the 10th and the 15th second of the original clip, consider it a 0 to 5 seconds video and suggest edits on it like you will suggest on a 0 to 5 seconds video. For example for this clip we can condider to have start time at 1.00345 and end time at 4.55789 rather than at 11.00345 and 14.55789 respectfully. Know that in this video clip you are identifying interesting parts relevant to the final video you are trying to create so the start time must not be exactly at the 0th second neither must the end time necesarily be at the last second of the video clip. Try to be flexible.
    - The IDs are integers that dictate the sequence in which the new video clips must appear in the final video
    - when proposing the edit settings sum up the different timeframes making sure it doesn't exceed the duration limit above.


  You are to carry out this by proposing time stamp intervals for each video and the edit fuctionalities to be performed during that interval. You decide on which edits go where based on what is expected of you and the goal is to make the result as interesting, creative and as engaging as possible. Try as much as possible to identify the specified content type if mentioned and work towards delivering something creative in that area or get creative and come up wit what you believe is best. Some of this content type include comedy skits, dance trends, lip-syncing, tutorials, product demons, vlogs, reviews, etc. You will suggest how the videos are displayed and what to include or exclude so as to pass the information needed or make it as interesting and creative as possible.  


  If for whatsoever reason you cannot produce a response or come up with video editing functionalities, generate a json response with empty values for all the videos'. Otherwise, the response should be in pure raw json given the structure above. The response should begin with a '{' and end with '}'. Make sure you don't exceed the maximum output tokens of 100000 and no matter what, provide a complet response.
  
  """)
    new_prompt = user_prompt + prompt
    response = model.generate_content([video_file, new_prompt], tool_config={'function_calling_config':'ANY'})
    if response.prompt_feedback:
      print(response.prompt_feedback)


    print(response.text)
    res = response.text
    lines = res.splitlines(keepends=True)
    res = ''.join(lines[1:-1])
    gemini_response_json = json.loads(res)
    print(json.dumps(gemini_response_json, indent=4))

    # Process Gemini response and create video edits using function calls
    video_edits = []
    for edit in gemini_response_json['video_edits']:
      video_name = edit['video_name']
      _id = edit['id']
      start_time = edit['start_time']
      end_time = edit['end_time']
      effects = [return_effect(effect['name'], effect['adjustment']) for effect in edit['effects']]
      text = [return_text(text['text'], text['font_size'], text['text_color'], text['background_color']) for text in edit['text']]
      transition = edit['transition']
      video_edits.append(return_video_edit(_id, video_name, start_time, end_time, effects, text, transition))

    return {
      'video_edits': video_edits
    }

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
    app.run(debug=True, host='0.0.0.0')


    





