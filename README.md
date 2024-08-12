# craite-flask-backend-server
Backend server for the craite android app to handle Gemini API requests. It returns edit settings needed by the [craite android app](https://github.com/Idadelveloper/craite)


## Building and Running the Flask backend Server
1. **Python 3.7 or higher:** Download and install from https://www.python.org/ .
2. **Virtual Environment (Recommended):** Create a virtual environment to manage dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
```
3. **Firebase Project:** Set up a Firebase project with:
    - Firebase Authentication (with Anonymous sign-in enabled)
    - Firebase Storage (for storing media files)
    - Firebase Firestore (for storing prompt data and Gemini responses)
      **Google Cloud Project:** Create a Google Cloud project and enable the Gemini API.
    - Obtain API Key and set it as an environment variable.
    - You can also get a Gemini API key from Google AI Studio (https://ai.google.dev/aistudio)
    - Create a service account with necessary permissions and download its JSON credentials file.
4. **Required Libraries:** Install the necessary Python packages:
```bash
pip install -r requirements.txt
```

### Steps to Run
1. **Clone the Repository:** Clone the project from GitHub:
```bash
git clone https://github.com/Idadelveloper/craite-flask-backend-server
```
2. **Set Up Environment Variables:**
    - Create a file named .env in the project root directory.
    - Use the provided example.env as a template and fill in the values:
```
GOOGLE_API_KEY=your_gemini_api_key
GOOGLE_APPLICATION_CREDENTIALS=creds/your_service_account_file
```
- Place the downloaded Firebase credentials JSON file in the `creds` directory.
3. **Activate Virtual Environment:**
```bash
source venv/bin/activate
```
4. **Run the Flask App:**
```bash
flask run
```
- The app will typically run on `http://127.0.0.1:5000/`.

### Linking the Frontend to the Backend
In the `NewProjectViewModel` of the app, got to the `sendPromptDataToFirestore` method and add your base url
```kotlin
val baseUrl = "your_backend_server_base_url_here"
```


# API Reference for Craite Backend Server
This API reference provides details on the endpoints available in the Craite Flask backend server, which facilitates video processing and interaction with the Gemini API

### Base URL
The base URL for all API endpoints is:
```bash
http://your-backend-server-address:5000/
```
Replace your-backend-server-address with the actual address or domain name of your deployed Flask server.

### Endpoints
**POST /process_videos**
This endpoint initiates the video processing workflow. It receives a JSON payload containing user information, prompt, and project details.
#### Request Body (JSON):**
```json
{
  "user_id": "firebase_user_id",
  "gemini_prompt": "Your descriptive prompt for video editing",
  "project_id": 123,
  "prompt_id": "firebase_prompt_id"
}
```
#### Response (JSON):
- **Success (200 OK):** Returns a JSON object containing the Gemini response with edit settings.
- **Error (400 Bad Request):** Indicates missing or invalid parameters in the request.
- **Error (401 Unauthorized):** Indicates an invalid user ID.
- **Error (403 Forbidden):** Indicates unauthorized access to a video.
- **Error (500 Internal Server Error):** Indicates an unexpected error during processing.

#### Example Request (using cURL):
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"user_id": "your_user_id", "gemini_prompt": "Edit the video to highlight the key moments", "project_id": 123, "prompt_id": "your_prompt_id"}' \
  http://your-backend-server-address:5000/process_videos
```

##### Notes:
- This API reference provides a basic overview. Refer to the code for detailed implementation and error handling.
