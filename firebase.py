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


class Firebase:
        
    # Function to get all files in a Firebase cloud storage dir
    @staticmethod
    def get_all_file_paths(directory, storage_bucket):
        bucket = storage_bucket
        blobs = bucket.list_blobs(prefix=directory)
        print(blobs)
        return [blob.name for blob in blobs if not blob.name.endswith('/')]
    
    # Function to download a video from Firebase Storage
    @staticmethod
    def download_media(video_path, file_path, storage_bucket):
        bucket = storage_bucket
        blob = bucket.blob(video_path)
        blob.download_to_filename(file_path)
     
     # Function to store gemini response to firestore   
    @staticmethod
    def store_gemini_response(user_id, project_id, prompt_id, gemini_response, firestore_client):
        """Stores the Gemini response in Firestore."""
        try:
            # Get firestore client
            db = firestore_client

            # Assuming your Firestore structure is like: users/{userId}/projects/{projectId}/prompts/{promptId}
            doc_ref = db.collection("users").document(user_id) \
                .collection("projects").document(str(project_id)) \
                .collection("prompts").document(prompt_id)

            doc_ref.update({"geminiResponse": gemini_response})
            print(f"Gemini response stored for prompt ID: {prompt_id}")
        except Exception as e:
            print(f"Error storing Gemini response: {e}")
        
    