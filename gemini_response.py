class GeminiResponse:
    def __init__(self):
        self.video_edits = []
        self.effects = []


    def return_video_edits():
        return {
            'video_edits': self.video_edits
        }

    def return_effects(effect):
        self.effects.append(effect)
        return self.effects

    def return_video_edit(self, video_name, _id, start_time, end_time, edit, effects, text, transition):
        video_edit = {
            'video_name': video_name,
            'id': _id,
            'start_time': start_time,
            'end_time': end_time,
            'edit': edit,
            'effects': effects,
            'text': text,
            'transition': transition
        }
        self.video_edits.append(video_edit)
        return 

    def return_effect(self, name, adjustment):
        return {
            'name': name,
            'adjustment': adjustment,
            }