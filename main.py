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
firebase_admin.initialize_app(cred, {
    'storageBucket': 'craiteapp.appspot.com'
})

# Initialize Gemini API client
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')


if __name__ == '__main__':
    app.run(debug=True)