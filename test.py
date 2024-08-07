import os
import moviepy
import ffmpeg
import uuid

def concatenate_videos_movie(video_data, output_dir):
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
  print(final_clip.size)

  return output_clip_path, durations, total_duration


def concatenate_videos_ffmpeg(video_data, output_dir):
  """Concatenates multiple videos from a dictionary and returns the output path,
  durations, and total duration.

  Args:
      video_data: A dictionary with video names as keys and their paths as values.
      output_dir: The path to save the concatenated video.

  Returns:
      A tuple containing:
          - The output path of the concatenated video.
          - A dictionary with video names as keys and lists of [start_timestamp, end_timestamp] for durations.
          - The total duration of the concatenated video in seconds.
  """

  clips = []
  durations = {}
  total_duration = 0

  # Create ffmpeg input streams from video paths
  for video_name, video_path in video_data.items():
    in_stream = ffmpeg.input(video_path)
    clips.append(in_stream)

    # Get video duration using ffmpeg probe
    probe = ffmpeg.probe(video_path)
    video_stream = next(stream for stream in probe['streams'] if stream['codec_type'] == 'video')
    duration = float(video_stream['duration'])

    durations[video_name] = [total_duration, total_duration + duration]
    total_duration += duration

  basename, extension = os.path.splitext(os.path.basename(next(iter(video_data.values()))))
  new_filename = f"{basename}_{uuid.uuid4()}{extension}"
  output_clip_path = os.path.join(output_dir, new_filename)

  # Concatenate the streams using ffmpeg.concat
  out_stream = ffmpeg.concat(*clips)

  # Define the output file with desired filename
  out = ffmpeg.output(out_stream, output_clip_path)

  # Run the ffmpeg process
  ffmpeg.run(out)

  print(f"Concatenated videos saved to: {output_clip_path}")

  return output_clip_path, durations, total_duration


def concatenate_videos_test(video_dir, output_dir):
  """Concatenates multiple videos from a directory and returns the output path,
  durations, and total duration.

  Args:
      video_dir: The directory path containing the videos to concatenate.
      output_dir: The path to save the concatenated video.

  Returns:
      A tuple containing:
          - The output path of the concatenated video.
          - A dictionary with video names as keys and lists of [start_timestamp, end_timestamp] for durations.
          - The total duration of the concatenated video in seconds.
  """

  clips = []
  durations = {}
  total_duration = 0

  # Get a list of video filenames in the directory
  video_filenames = [f for f in os.listdir(video_dir) if os.path.isfile(os.path.join(video_dir, f))]

  # Create ffmpeg input streams from video paths
  for video_name in video_filenames:
    video_path = os.path.join(video_dir, video_name)
    in_stream = ffmpeg.input(video_path)
    clips.append(in_stream)

    # Get video duration using ffmpeg probe
    probe = ffmpeg.probe(video_path)
    video_stream = next(stream for stream in probe['streams'] if stream['codec_type'] == 'video')
    duration = float(video_stream['duration'])

    durations[video_name] = [total_duration, total_duration + duration]
    total_duration += duration

  basename, extension = os.path.splitext(os.path.basename(video_filenames[0]))  # Use first filename
  new_filename = f"{basename}_{uuid.uuid4()}{extension}"
  output_clip_path = os.path.join(output_dir, new_filename)

  # Concatenate the streams using ffmpeg.concat
  out_stream = ffmpeg.concat(*clips)

  # Define the output file with desired filename
  out = ffmpeg.output(out_stream, output_clip_path)

  # Run the ffmpeg process
  ffmpeg.run(out)

  print(f"Concatenated videos saved to: {output_clip_path}")

  return output_clip_path, durations, total_duration

print(concatenate_videos_test('videos', 'videos'))