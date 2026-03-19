"""
Create a vertical reel from a blessing segment.

Takes the blessing segment timestamps and word data, then:
1. Clips the segment from the source video
2. Detects and tracks the speaker's face
3. Crops to 9:16 vertical centered on the speaker
4. Adds word-by-word animated captions with color highlight
5. Exports the final reel
"""

import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp


def clip_segment(video_path: str, start: float, end: float, output_path: str):
    """Extract a segment from the video using FFmpeg."""
    print(f"Clipping {start:.1f}s to {end:.1f}s...")
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", video_path,
        "-t", str(end - start),
        "-c", "copy",
        output_path,
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    print(f"  Clipped to {output_path}")


def detect_speaker_position(video_path: str, sample_frames: int = 30) -> dict:
    """
    Detect the average position of the speaker's face in the video.
    Returns the center x,y coordinates as fractions of frame dimensions.
    """
    print("Detecting speaker position...")
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    face_detection = mp.solutions.face_detection.FaceDetection(
        model_selection=1,  # Full range model (for distant faces)
        min_detection_confidence=0.5,
    )

    face_centers_x = []
    face_centers_y = []
    face_sizes = []

    # Sample frames evenly across the video
    frame_indices = np.linspace(0, total_frames - 1, sample_frames, dtype=int)

    for idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_detection.process(rgb_frame)

        if results.detections:
            # Take the largest face (most likely the speaker)
            best_detection = max(
                results.detections,
                key=lambda d: d.location_data.relative_bounding_box.width
                * d.location_data.relative_bounding_box.height,
            )
            bbox = best_detection.location_data.relative_bounding_box
            cx = bbox.xmin + bbox.width / 2
            cy = bbox.ymin + bbox.height / 2
            face_centers_x.append(cx)
            face_centers_y.append(cy)
            face_sizes.append(bbox.width * bbox.height)

    cap.release()
    face_detection.close()

    if not face_centers_x:
        print("  WARNING: No faces detected. Using center crop.")
        return {"cx": 0.5, "cy": 0.4, "face_size": 0.05, "width": width, "height": height}

    avg_cx = np.median(face_centers_x)
    avg_cy = np.median(face_centers_y)
    avg_size = np.median(face_sizes)

    print(f"  Speaker at ({avg_cx:.2f}, {avg_cy:.2f}), face_size={avg_size:.4f}")
    print(f"  Frame dimensions: {width}x{height}")

    return {
        "cx": float(avg_cx),
        "cy": float(avg_cy),
        "face_size": float(avg_size),
        "width": width,
        "height": height,
    }


def generate_caption_filter(words: list, segment_start: float, target_width: int = 1080) -> str:
    """
    Generate FFmpeg drawtext filter for word-by-word animated captions
    with color highlight on the current word.

    Style: White bold text, current word in yellow/gold, dark backdrop.
    """
    if not words:
        return ""

    # Group words into lines of ~4-5 words for readability
    lines = []
    current_line = []
    current_char_count = 0

    for word_data in words:
        word = word_data["word"]
        if current_char_count + len(word) > 25 and current_line:
            lines.append(current_line)
            current_line = []
            current_char_count = 0
        current_line.append(word_data)
        current_char_count += len(word) + 1

    if current_line:
        lines.append(current_line)

    # Group lines into display groups (show 1-2 lines at a time)
    filters = []
    font_size = 58
    font = "Arial"
    y_pos = "h-h/4"  # Lower quarter of the frame

    for line_words in lines:
        if not line_words:
            continue

        line_start = line_words[0]["start"] - segment_start
        line_end = line_words[-1]["end"] - segment_start

        # For each word in the line, create two drawtext entries:
        # 1. The full line in white (background)
        # 2. The highlighted word in yellow (overlay, timed to that word)

        full_text = " ".join(w["word"] for w in line_words)

        # Escape special characters for FFmpeg
        full_text_escaped = full_text.replace("'", "'\\''").replace(":", "\\:")
        full_text_escaped = full_text_escaped.replace("%", "%%")

        # Background: full line in white, shown for the duration of the line
        filters.append(
            f"drawtext=text='{full_text_escaped}'"
            f":fontfile=/System/Library/Fonts/Helvetica.ttc"
            f":fontsize={font_size}"
            f":fontcolor=white"
            f":borderw=3:bordercolor=black"
            f":x=(w-text_w)/2"
            f":y={y_pos}"
            f":enable='between(t,{line_start:.2f},{line_end:.2f})'"
        )

        # Highlight each word in yellow when it's being spoken
        for i, word_data in enumerate(line_words):
            word = word_data["word"]
            word_start = word_data["start"] - segment_start
            word_end = word_data["end"] - segment_start

            # Calculate x offset for this word within the line
            prefix = " ".join(w["word"] for w in line_words[:i])
            prefix_with_space = prefix + " " if prefix else ""

            word_escaped = word.replace("'", "'\\''").replace(":", "\\:")
            word_escaped = word_escaped.replace("%", "%%")
            prefix_escaped = prefix_with_space.replace("'", "'\\''").replace(":", "\\:")
            prefix_escaped = prefix_escaped.replace("%", "%%")

            # Use a yellow/gold color for the active word
            filters.append(
                f"drawtext=text='{word_escaped}'"
                f":fontfile=/System/Library/Fonts/Helvetica.ttc"
                f":fontsize={font_size}"
                f":fontcolor=#FFD700"
                f":borderw=3:bordercolor=black"
                f":x=(w-text_w)/2+{len(prefix_with_space)}*{font_size}*0.45"
                f":enable='between(t,{word_start:.2f},{word_end:.2f})'"
                f":y={y_pos}"
            )

    return ",".join(filters)


def create_vertical_reel(
    video_path: str,
    speaker_pos: dict,
    words: list,
    segment_start: float,
    output_path: str,
    target_width: int = 1080,
    target_height: int = 1920,
):
    """
    Create the final vertical reel with face-centered crop and captions.
    """
    src_w = speaker_pos["width"]
    src_h = speaker_pos["height"]

    # Calculate crop dimensions for 9:16 from the source
    # We want to crop a vertical strip centered on the speaker
    aspect_ratio = target_width / target_height  # 9/16 = 0.5625
    crop_w = int(src_h * aspect_ratio)
    crop_h = src_h

    if crop_w > src_w:
        crop_w = src_w
        crop_h = int(src_w / aspect_ratio)

    # Center the crop on the speaker's x position
    cx_pixels = int(speaker_pos["cx"] * src_w)
    crop_x = max(0, cx_pixels - crop_w // 2)
    crop_x = min(crop_x, src_w - crop_w)

    # Vertical offset - position so speaker's face is in upper portion
    cy_pixels = int(speaker_pos["cy"] * src_h)
    crop_y = max(0, cy_pixels - int(crop_h * 0.35))  # Face at ~35% from top
    crop_y = min(crop_y, src_h - crop_h)

    print(f"  Crop: {crop_w}x{crop_h} at ({crop_x}, {crop_y})")
    print(f"  Scale to: {target_width}x{target_height}")

    # Build the FFmpeg filter chain
    # 1. Crop to vertical centered on speaker
    # 2. Scale to target resolution
    # 3. Add dark gradient at bottom for captions
    # 4. Add word-by-word captions

    crop_filter = f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y}"
    scale_filter = f"scale={target_width}:{target_height}"

    # Dark gradient overlay at the bottom for caption readability
    gradient_filter = (
        f"drawbox=x=0:y=ih*0.65:w=iw:h=ih*0.35:color=black@0.4:t=fill"
    )

    # Caption filter
    caption_filter = generate_caption_filter(words, segment_start, target_width)

    # Combine all filters
    filter_parts = [crop_filter, scale_filter, gradient_filter]
    if caption_filter:
        filter_parts.append(caption_filter)

    full_filter = ",".join(filter_parts)

    print(f"  Building reel...")
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", full_filter,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  FFmpeg error: {result.stderr[-500:]}")
        # Try without captions if filter is too complex
        print("  Retrying without captions...")
        simple_filter = f"{crop_filter},{scale_filter},{gradient_filter}"
        cmd[cmd.index("-vf") + 1] = simple_filter
        subprocess.run(cmd, capture_output=True, check=True)
        print(f"  WARNING: Exported without captions. Caption filter was too complex.")

    print(f"  Reel exported to {output_path}")


def main():
    if len(sys.argv) < 3:
        print("Usage: python create_reel.py <clipped_video> <blessing_json>")
        sys.exit(1)

    video_path = sys.argv[1]
    blessing_json_path = sys.argv[2]

    with open(blessing_json_path) as f:
        blessing = json.load(f)

    # Detect speaker position
    speaker_pos = detect_speaker_position(video_path)

    # Create the reel
    output_path = str(Path(video_path).parent / "reel_output.mp4")
    create_vertical_reel(
        video_path=video_path,
        speaker_pos=speaker_pos,
        words=blessing["words"],
        segment_start=blessing["start"],
        output_path=output_path,
    )

    print(f"\nDone! Reel saved to: {output_path}")


if __name__ == "__main__":
    main()
