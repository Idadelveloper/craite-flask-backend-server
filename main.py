from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, storage, auth
from google.cloud import aiplatform
import os
import tempfile
import requests  
import google.generativeai as genai
import time
from dotenv import load_dotenv

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
        video_directory = f"users/{user_id}/projects/{project_id}/"
        video_paths = get_all_file_paths(video_directory)
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

                # Uploads video to Gemini
                gemini_video = upload_to_gemini(file_path)
                video_data.append(gemini_video)

                # # Read video content as bytes
                # with open(file_path, 'rb') as f:
                #     video_data.append(f.read())

        wait_for_files_active(video_data)

        # Prompt the Gemini API with all videos and the prompt
        gemini_response = prompt_gemini_api(video_data, gemini_prompt)

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
def prompt_gemini_api(video_paths, gemini_prompt):
    response = model.generate_content(video_paths, gemini_prompt)
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
  print()

# Function to check if a video belongs to the user
def video_belongs_to_user(video_path, user_id):
    # Assuming your Firebase Storage structure is like: users/{userId}/projects/{projectId}/videos/...
    return video_path.startswith(f'users/{user_id}/')

# Function to get all files in a Firebase cloud storage dir
def get_all_file_paths(directory):
    bucket = storage.bucket()
    blobs = bucket.list_blobs(prefix=directory)
    return [blob.name for blob in blobs if not blob.name.endswith('/')]


if __name__ == '__main__':
    app.run(debug=True)