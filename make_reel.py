"""
Complete reel maker: crop to vertical + add simple animated captions.
Uses only FFmpeg drawtext (no ASS dependency needed).
Keeps it simple: shows 1 line at a time, all caps, white with gold keyword highlight.
"""

import json
import subprocess
import sys
from pathlib import Path
import cv2
import numpy as np


def detect_face_x(video_path: str) -> tuple:
    """Detect speaker face x-center. Returns (cx_fraction, width, height)."""
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    xs = []
    for idx in np.linspace(0, total_frames - 1, 20, dtype=int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
        if len(faces) > 0:
            f = max(faces, key=lambda f: f[2] * f[3])
            xs.append((f[0] + f[2] / 2) / w)
    cap.release()

    cx = float(np.median(xs)) if xs else 0.5
    return cx, w, h


def make_reel(video_path: str, words_json: str, output_path: str):
    """Create vertical reel with face crop and line-by-line captions."""

    with open(words_json) as f:
        data = json.load(f)
    words = data["words"]
    clip_start = data["start"]

    # Face detection
    print("Detecting face...")
    cx, src_w, src_h = detect_face_x(video_path)
    print(f"  Face at x={cx:.2f}, frame={src_w}x{src_h}")

    # Calculate 9:16 crop
    crop_w = int(src_h * 9 / 16)
    crop_h = src_h
    if crop_w > src_w:
        crop_w = src_w
        crop_h = int(src_w * 16 / 9)

    cx_px = int(cx * src_w)
    crop_x = max(0, min(cx_px - crop_w // 2, src_w - crop_w))
    crop_y = 0

    print(f"  Crop: {crop_w}x{crop_h} at ({crop_x},{crop_y})")

    # Group words into caption lines
    lines = []
    current = []
    chars = 0
    for wd in words:
        w = wd["word"]
        if chars + len(w) > 25 and current:
            lines.append(current)
            current = []
            chars = 0
        current.append(wd)
        chars += len(w) + 1
    if current:
        lines.append(current)

    print(f"  {len(lines)} caption lines to render")

    # Build drawtext filters — one per line, simple white text
    fontfile = "/System/Library/Fonts/Helvetica.ttc"
    fontsize = 56

    # Limit to manageable number of drawtext filters
    # FFmpeg can handle ~100 drawtext filters without issues
    dt_filters = []
    for line_words in lines:
        text = " ".join(w["word"].upper() for w in line_words)
        t_start = line_words[0]["start"] - clip_start
        t_end = line_words[-1]["end"] - clip_start + 0.15

        if t_start < 0:
            t_start = 0
        if t_end <= 0:
            continue

        # Escape text for FFmpeg drawtext
        safe = text.replace("\\", "\\\\\\\\").replace("'", "\u2019").replace(":", "\\\\:").replace("%", "%%%%").replace('"', '\\"')

        dt_filters.append(
            f"drawtext=text='{safe}'"
            f":fontfile={fontfile}:fontsize={fontsize}"
            f":fontcolor=white:borderw=4:bordercolor=black@0.9"
            f":shadowx=2:shadowy=2:shadowcolor=black@0.5"
            f":x=(w-text_w)/2:y=h-h*0.2"
            f":enable='between(t,{t_start:.3f},{t_end:.3f})'"
        )

    # Build complete filter chain
    vf = f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale=1080:1920:flags=lanczos"
    vf += ",drawbox=x=0:y=ih*0.72:w=iw:h=ih*0.28:color=black@0.4:t=fill"

    # Add caption filters in batches if needed
    if dt_filters:
        vf += "," + ",".join(dt_filters)

    print("Rendering...")
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "22",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        "-r", "30",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    if result.returncode != 0:
        # Try without captions
        print("  Full filter failed, trying without captions...")
        vf_simple = f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale=1080:1920:flags=lanczos,drawbox=x=0:y=ih*0.72:w=iw:h=ih*0.28:color=black@0.4:t=fill"
        cmd_simple = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", vf_simple,
            "-c:v", "libx264", "-preset", "medium", "-crf", "22",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            "-r", "30",
            output_path,
        ]
        subprocess.run(cmd_simple, capture_output=True, check=True, timeout=300)
        print(f"  Exported WITHOUT captions -> {output_path}")
        return

    print(f"  Done -> {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python make_reel.py <clip.mp4> <words.json> <output.mp4>")
        sys.exit(1)
    make_reel(sys.argv[1], sys.argv[2], sys.argv[3])
