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
  
def return_audio_edits(start_time, end_time):
  return {
    "start_time": start_time,
    "end_time": end_time
  }