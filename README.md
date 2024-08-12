# craite-flask-backend-server
Backend server for the craite android app to handle Gemini API requests


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


## Contributors
- Ida Delphine
