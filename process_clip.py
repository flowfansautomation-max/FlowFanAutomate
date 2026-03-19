"""
Process a raw clip into a vertical reel with face tracking and animated captions.
"""

import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np


def detect_face_center(video_path: str) -> tuple:
    """Detect average face position using OpenCV's DNN face detector."""
    print("  Detecting speaker face position...")
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Use OpenCV's Haar cascade face detector (no extra downloads needed)
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    centers_x = []
    # Sample 20 frames
    for idx in np.linspace(0, total_frames - 1, 20, dtype=int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        if len(faces) > 0:
            # Take the largest face
            largest = max(faces, key=lambda f: f[2] * f[3])
            fx, fy, fw, fh = largest
            centers_x.append((fx + fw / 2) / w)

    cap.release()

    cx = float(np.median(centers_x)) if centers_x else 0.5
    print(f"  Speaker at x={cx:.2f} (frame {w}x{h}), detected in {len(centers_x)}/20 frames")
    return cx, w, h


def build_caption_filter(words: list, clip_start: float) -> str:
    """
    Build FFmpeg drawtext filter for word-by-word animated captions.
    White text with current word highlighted in gold.
    """
    if not words:
        return ""

    # Group words into display lines (~4-5 words each)
    lines = []
    current_line = []
    char_count = 0

    for wd in words:
        word = wd["word"]
        if char_count + len(word) > 22 and current_line:
            lines.append(current_line)
            current_line = []
            char_count = 0
        current_line.append(wd)
        char_count += len(word) + 1
    if current_line:
        lines.append(current_line)

    filters = []
    fontfile = "/System/Library/Fonts/Helvetica.ttc"
    fontsize = 52
    y_position = "h-h*0.22"

    for line_words in lines:
        if not line_words:
            continue

        line_start = line_words[0]["start"] - clip_start
        line_end = line_words[-1]["end"] - clip_start

        if line_start < 0:
            line_start = 0
        if line_end < 0:
            continue

        full_text = " ".join(w["word"].upper() for w in line_words)

        # Escape for FFmpeg
        def esc(t):
            return t.replace("\\", "\\\\").replace("'", "'\\''").replace(":", "\\:").replace("%", "%%%%")

        # Background line in white
        filters.append(
            f"drawtext=text='{esc(full_text)}'"
            f":fontfile={fontfile}:fontsize={fontsize}"
            f":fontcolor=white:borderw=3:bordercolor=black@0.8"
            f":x=(w-text_w)/2:y={y_position}"
            f":enable='between(t\\,{line_start:.2f}\\,{line_end:.2f})'"
        )

        # Highlighted word in gold, one at a time
        for i, wd in enumerate(line_words):
            ws = wd["start"] - clip_start
            we = wd["end"] - clip_start
            if ws < 0:
                ws = 0
            if we < 0:
                continue

            word_upper = wd["word"].upper()
            # Calculate x offset: measure prefix text width
            prefix_words = [w["word"].upper() for w in line_words[:i]]
            prefix = " ".join(prefix_words)
            if prefix:
                prefix += " "

            # Use drawtext with x offset calculated from prefix width
            # FFmpeg can compute text_w, so we use a trick:
            # Place the highlighted word at the same y, computing x from prefix
            filters.append(
                f"drawtext=text='{esc(word_upper)}'"
                f":fontfile={fontfile}:fontsize={fontsize}"
                f":fontcolor=#FFD700:borderw=3:bordercolor=black@0.8"
                f":x=(w-text_w)/2+{len(prefix)}*{fontsize}*0.52-text_w/2+{len(word_upper)}*{fontsize}*0.26"
                f":y={y_position}"
                f":enable='between(t\\,{ws:.2f}\\,{we:.2f})'"
            )

    return ",".join(filters)


def create_reel(video_path: str, words_json: str, output_path: str):
    """Create vertical reel with face tracking crop and animated captions."""

    with open(words_json) as f:
        clip_data = json.load(f)

    words = clip_data["words"]
    clip_start = clip_data["start"]

    # Step 1: Detect face
    cx, src_w, src_h = detect_face_center(video_path)

    # Step 2: Calculate crop for 9:16
    target_ratio = 9 / 16  # 0.5625
    crop_w = int(src_h * target_ratio)  # Width based on full height
    crop_h = src_h

    if crop_w > src_w:
        crop_w = src_w
        crop_h = int(src_w / target_ratio)

    # Center crop on speaker's face
    cx_px = int(cx * src_w)
    crop_x = max(0, cx_px - crop_w // 2)
    crop_x = min(crop_x, src_w - crop_w)
    crop_y = 0  # Use full height

    print(f"  Crop: {crop_w}x{crop_h} at ({crop_x},{crop_y}) from {src_w}x{src_h}")

    # Step 3: Build FFmpeg filter
    # Crop -> Scale to 1080x1920 -> Dark gradient at bottom -> Captions
    vf_parts = [
        f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y}",
        "scale=1080:1920:flags=lanczos",
        # Dark gradient at bottom for caption readability
        "drawbox=x=0:y=ih*0.7:w=iw:h=ih*0.3:color=black@0.45:t=fill",
    ]

    caption_filter = build_caption_filter(words, clip_start)

    # Step 4: Try with captions first, fallback without if filter is too complex
    print("  Rendering reel...")

    if caption_filter:
        full_vf = ",".join(vf_parts) + "," + caption_filter
    else:
        full_vf = ",".join(vf_parts)

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", full_vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "22",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        "-r", "30",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        print(f"  Caption filter failed, trying without captions...")
        # Fallback: just crop and scale
        simple_vf = ",".join(vf_parts)
        cmd_simple = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", simple_vf,
            "-c:v", "libx264", "-preset", "medium", "-crf", "22",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            "-r", "30",
            output_path,
        ]
        subprocess.run(cmd_simple, capture_output=True, check=True, timeout=300)
        print(f"  Exported WITHOUT captions: {output_path}")
        return False  # Signal that captions failed
    else:
        print(f"  Exported with captions: {output_path}")
        return True


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python process_clip.py <raw_clip.mp4> <words.json> <output.mp4>")
        sys.exit(1)

    success = create_reel(sys.argv[1], sys.argv[2], sys.argv[3])
    if success:
        print("\nDone! Reel created with animated captions.")
    else:
        print("\nDone! Reel created (captions need manual adjustment).")
