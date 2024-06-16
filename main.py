from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, storage, auth
from google.cloud import aiplatform
import os
import tempfile
import requests  
import google.generativeai as genai

# Initialize Flask app
app = Flask(__name__)

# Initialize Firebase
cred = credentials.Certificate(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))
firebase_admin.initialize_app(cred)

# Initialize Gemini API client
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')


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
        video_directory = f"users/{user_id}/projects/{project_id}"
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

                # Read video content as bytes
                with open(file_path, 'rb') as f:
                    video_data.append(f.read())

        # Prompt the Gemini API with all videos and the prompt
        gemini_response = prompt_gemini_api(video_data, gemini_prompt)

        # Return the response to the Android app
        return jsonify({'gemini_response': gemini_response})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Function to download a video from Firebase Storage
def download_video(video_path, file_path):
    storage_client = storage
    bucket = storage_client.bucket('craiteapp.appspot.com')
    blob = bucket.blob(video_path)
    blob.download_to_filename(file_path)

# Function to prompt the Gemini API 
def prompt_gemini_api(video_path, gemini_prompt):
    # ... (Code to interact with the Gemini API using video_path and gemini_prompt)
    # Return the response from the Gemini API
    return response

# Function to check if a video belongs to the user
def video_belongs_to_user(video_path, user_id):
    # Assuming your Firebase Storage structure is like: users/{userId}/projects/{projectId}/videos/...
    return video_path.startswith(f'users/{user_id}/')

# Function to get all files in a directory
def get_all_file_paths(directory, recursive=False):
  all_file_paths = []
  for filename in os.listdir(directory):
    file_path = os.path.join(directory, filename)
    if os.path.isfile(file_path):
      all_file_paths.append(file_path)
    elif recursive and os.path.isdir(file_path):
      all_file_paths.extend(get_all_file_paths(file_path, recursive))  # Recursive call

  return all_file_paths


if __name__ == '__main__':
    app.run(debug=True)