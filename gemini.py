from flask import Flask, request, jsonify
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


class Gemini:
    
    @staticmethod
    def upload_to_gemini(path, mime_type=None):
            """Uploads the given file to Gemini.

            See https://ai.google.dev/gemini-api/docs/prompting_with_media
            """
            if not os.path.exists(path):
                raise Exception(f"File not found: {path}")

            file = genai.upload_file(path, mime_type=mime_type)
            print(f"Uploaded file '{file.display_name}' as: {file.uri}")
            return file
        
        
    # Function to prompt the Gemini API 
    @staticmethod
    def prompt_gemini_api(video_file, gemini_prompt, video_durations, audio_file):
        user_prompt = "You are a video editor. Given a video (which might be a concatenation of multiple clips), \\n\"" + str(video_durations) + "\"\\nThis is what the user wants for their final video final video: \"" + gemini_prompt + "\"\\nEven though you have been provided a single video, using the above video names and timestamps, treat each as a single video and understand whats going on based on the sound, actions and interactions. The goal is for you to create a video not more than 60 seconds long.\n Make sure you identify each clip by looking at its video name above and check its corresponding timeframe based on its start and ending timestamp in the inputted video. After identifying a video, treat it as an independent video. Forexample if you identify a video from the 10th to the 15th second, treat that video as a independent 5 second video. All the videos you identify and isolate will be considered as the videoclips where you will carryout various edit functionalities on them"

        prompt = textwrap.dedent("""
        You are to create edit settings by understanding what is happening in each of the video clips you identified as stated above as well as what the user wants for the final video and suggest various edit functionalities in a purely json format. Even if the user did not specify did not specify how the video should look like or it isn't clear, make sure you can identify relevant parts or clips of the video that will match the audio and if how the video should look like was specified, make sure your suggestions matches it too. 
        The goal is to capture and suggest the key moments and best parts of the video(s) while making sure they all sum up to at most the time limit. You are to suggest the text overlays, perform video editing like changes in brightness, contrast, saturation, or any of the other effects listed above if you wish. Different edit functionalities can be performed on a single video clip at different time intervals and the videos must not appear in the order they came in. You decide how they appear based on the message you are trying to pass. You can trim a single video clip multiple times at different timestamps if possible. 
        
        If an audio has been provided, you are  also to suggest some edits on it. For the audio edits, you are simply to trim it in such a way that it matches or syncs with the final video. Make sure you calculate the start and end time of the audio to match the length of the resulting video after the video edits have been applied.

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
                        },
                        {
                            "name": "rotate",
                            "adjustment": 90
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
                        },
                        {
                            "name": "vignette",
                            "adjustment": [0.5, 0.5]
                        },
                        {
                            "name": "zoomIn",
                            "adjustment": [2.0, 1L]
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
            ],
            "audio_edits": {
                "start_time": 0.004576,
                "end_time": 6.98762344
            }
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
        - **`saturation`:** This controls how vivid the colors in the clip are.  0 is the neutral point and the color stays thesame. Positive numbers like like 0.5, 1, 2, etc will make the colors in the video more intense and vibrant. The higher the number, the more saturated and punchy the colors become. Negative numbers like like -0.5, -1, etc will make the colors more muted and washed out. The further negative you go, the closer you get to a black and white look.
        - **`vignette`**: This effect creates a soft, darkened border around the edges of the video, drawing attention to the center. The strength of the effect is controlled by two values between 0 and 1: outerRadius (how far the darkening extends) and innerRadius (the size of the unaffected center area). It should be a list of 2 float values like this: [outerRadius, innerRadius]
        - **`fisheye`**: This effect distorts the video to create a wide-angle, rounded look, similar to a fisheye lens. The strength of the distortion is controlled by a value between 0 (no distortion) and 1 (maximum distortion). The adjustment value should be a single float in a list.
        - **`colorTint`**: This effect applies a tint of a specific color over the entire video. The color is specified using a hex color code (e.g., "#FF0000" for red, "#0000FF" for blue).
        - **`rotate`**: This effect rotates the video by a specified number of degrees (e.g., 90 degrees). This will be a list containing and integer value specifying the number of degrees.
        - **`zoomIn`**: It takes a list containing 2 values, [zoomFactor, durationSeconds]. This effect gradually zooms into the video over a specified duration.
            -zoomFactor (Float): How much to zoom in. A value of 2.0 means zooming in to twice the original size.
            -durationSeconds (Long): How long the zoom-in effect should last, in seconds.
        - **`zoomOut`**: This effect gradually zooms out of the video over a specified duration.
            - zoomFactor (Float): How much to zoom out. A value of 0.5 means zooming out to half the original size.
            - durationSeconds (Long): How long the zoom-out effect should last, in seconds.
        text: This is a list of text overlays we want to put on top of the video. Each text overlay has:
        - **`text`:** The actual words to display.
        - **`font_size`:** How big the text should be in pixels for a mobile device
        - **`text_color`:** The color of the text, written as a hex code (like #3de490 for a greenish color).
        - **`background_color`:** The color behind the text, also a hex code.  "#80000000" means a semi-transparent black, so the video can still be seen a bit behind the text.

        transition: This tells us how to smoothly blend this clip with the next one in the sequence. "fade" means the clip will slowly fade out as the next one fades in. There are other options like "slide" or "cross-fade". If it's empty (like in the second video edit), there's no special transition.
        
        
        Let's look at the audio edits:
        "audio_edits": {
                "start_time": 0.004576,
                "end_time": 6.98762344
            }
        The `start_time` signfies the time where the trimming of the audio will start while the `end_time` signifies the time where the trimming of the audio will end.
        


        Important Notes:
        - Multiple Edits on One Video: You noticed that video IDs 4 and 5 use the same video_name. This means we can take different chunks of the same video clip and edit them separately!
        - No Text Required: Some video edits might not have any text overlays, like video ID 5. That's totally fine!
        No Effects Required: Some videos might also not have any effects.
        - When suggesting the start_time and end_time for a video clip to be trimmed, remember to isolate that clip. If that clip happened to be between the 10th and the 15th second of the original clip, consider it a 0 to 5 seconds video and suggest edits on it like you will suggest on a 0 to 5 seconds video. For example for this clip we can condider to have start time at 1.00345 and end time at 4.55789 rather than at 11.00345 and 14.55789 respectfully. Know that in this video clip you are identifying interesting parts relevant to the final video you are trying to create so the start time must not be exactly at the 0th second neither must the end time necesarily be at the last second of the video clip. Try to be flexible.
        - The IDs are integers that dictate the sequence in which the new video clips must appear in the final video
        - when proposing the edit settings sum up the different timeframes making sure it doesn't exceed the duration limit above.
        - All the effects must not be used. The point of the effects is to modify the video or make it more interesting


        You are to carry out this by proposing time stamp intervals for each video and the edit fuctionalities to be performed during that interval. You decide on which edits go where based on what is expected of you and the goal is to make the result as interesting, creative and as engaging as possible. Try as much as possible to identify the specified content type if mentioned and work towards delivering something creative in that area or get creative and come up wit what you believe is best. Some of this content type include comedy skits, dance trends, lip-syncing, tutorials, product demons, vlogs, reviews, etc. You will suggest how the videos are displayed and what to include or exclude so as to pass the information needed or make it as interesting and creative as possible.  
        
        NB: Make sure you identify each video in the input concatenated videos and treat it independent of the other assuming the its actual start time os 0 and its end time is its end time in the concatenated video minis its start time in the concatenated video. Remember you are applying edits to each independent video you succeed to identify by suggesting parts of this video to trim (using its new start time and end time)
        
        Before you suggest any edits, make sure you identify each clip by looking at its video name above and check its corresponding timeframe based on its start and ending timestamp in the inputted video. You have also been given the start and ending timestamp of each video in the input video. After identifying a video, treat it as an independent video. Forexample if you identify a video from the 10th to the 15th second, treat that video as a independent 5 second video. All the videos you identify and isolate will be considered as the videoclips where you will carryout various edit functionalities on them"
        
        Lets look at our example again to understand whats expected for each video edit:
        
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
        
        Here's what some part mean:
        - id: This is like a unique number tag for the trimmed version of this video clip. So, after we trim this video, we'll think of it as "video clip number 1". This is important for putting the clips in the right order later. It's always a whole number (an integer).
        - video_name: This is the video name assigneed to that video clip. It's like saying, "Hey, go find this specific video to work with." Each video has a unique name, so we don't get them mixed up.
        - start_time: This tells us where to start chopping the video, measured in seconds. It's a decimal number (a float) because we might want to start at a very precise moment, like 0.734 seconds in. The start_time MUST not begin at 0
        - end_time: This tells us where to stop chopping the video, also in seconds and also a float for precision. So, for this clip, we're only using the part of the video between 0.734 seconds and 3.530 seconds. The end_time MUST not begin at the last second.
        
        effects: This is a list of special visual tweaks we want to apply to the video clip. Think of it like adding filters on Instagram. Right now, we only have three options:
        - **`brightness`:** This controls how bright or dark the clip looks.  The adjustment value is a number between -1 and 1.  Zero means no change, positive numbers make it brighter, and negative numbers make it darker.  In this example, 0.333 makes the clip a bit brighter.
        - **`contrast`:** This controls the difference between the darkest and lightest parts of the clip.  Again, the adjustment is between -1 and 1.  Zero means no change, positive numbers increase the contrast (making darks darker and lights lighter), and negative numbers decrease the contrast (making everything look more similar in brightness).
        - **`saturation`:** This controls how vivid the colors in the clip are.  0 is the neutral point and the color stays thesame. Positive numbers like like 0.5, 1, 2, etc will make the colors in the video more intense and vibrant. The higher the number, the more saturated and punchy the colors become. Negative numbers like like -0.5, -1, etc will make the colors more muted and washed out. The further negative you go, the closer you get to a black and white look.
        - **`vignette`**: This effect creates a soft, darkened border around the edges of the video, drawing attention to the center. The strength of the effect is controlled by two values between 0 and 1: outerRadius (how far the darkening extends) and innerRadius (the size of the unaffected center area). It should be a list of 2 float values like this: [outerRadius, innerRadius]
        - **`fisheye`**: This effect distorts the video to create a wide-angle, rounded look, similar to a fisheye lens. The strength of the distortion is controlled by a value between 0 (no distortion) and 1 (maximum distortion). The adjustment value should be a single float in a list.
        - **`colorTint`**: This effect applies a tint of a specific color over the entire video. The color is specified using a hex color code (e.g., "#FF0000" for red, "#0000FF" for blue).
        - **`rotate`**: This effect rotates the video by a specified number of degrees (e.g., 90 degrees). This will be a list containing and integer value specifying the number of degrees.
        - **`zoomIn`**: It takes a list containing 2 values, [zoomFactor, durationSeconds]. This effect gradually zooms into the video over a specified duration.
            -zoomFactor (Float): How much to zoom in. A value of 2.0 means zooming in to twice the original size.
            -durationSeconds (Long): How long the zoom-in effect should last, in seconds.
        - **`zoomOut`**: This effect gradually zooms out of the video over a specified duration.
            - zoomFactor (Float): How much to zoom out. A value of 0.5 means zooming out to half the original size.
            - durationSeconds (Long): How long the zoom-out effect should last, in seconds.
        text: This is a list of text overlays we want to put on top of the video. Each text overlay has:
        - **`text`:** The actual words to display.
        - **`font_size`:** How big the text should be in pixels for a mobile device
        - **`text_color`:** The color of the text, written as a hex code (like #3de490 for a greenish color).
        - **`background_color`:** The color behind the text, also a hex code.  "#80000000" means a semi-transparent black, so the video can still be seen a bit behind the text.
        
        
        Also remember the start and end time of the audio edits should be calculated in such a way that if all those video edits are applied and the audio is trimmed its length would be the length of the new video


        If for whatsoever reason you cannot produce a response or come up with video editing functionalities, generate a json response with empty values for all the videos'. Otherwise, the response should be in pure raw json given the structure above. The response should begin with a '{' and end with '}'. Make sure you don't exceed the maximum output tokens of 100000 and no matter what, provide a complete response.
    
    
    
    """)
        new_prompt = user_prompt + prompt
        
        chat_session = model.start_chat(
            history=[
            {
                "role": "user",
                "parts": [
                video_file,
                ],
            },
            {
                "role": "user",
                "parts": [
                audio_file,
                ],
            },
        ]
        )
        print("sending request...")
        try:
            response = chat_session.send_message(new_prompt)

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
            
            audio_edits = {
                "start_time": "",
                "end_time": ""
            } 
            if gemini_response_json['audio_edits']:
                audio_edits = gemini_response_json['audio_edits']
            

            return {
                'video_edits': video_edits,
                'audio_edits': audio_edits
            }
        except Exception as e:
            print(e)
            
        
        