"""
Add word-by-word animated captions to a vertical reel using FFmpeg.
Simpler approach: generate an ASS subtitle file, then burn it in.
"""

import json
import sys
from pathlib import Path
import subprocess


def generate_ass_subtitles(words: list, clip_start: float, output_path: str):
    """
    Generate ASS (Advanced SubStation Alpha) subtitle file with
    word-by-word animation using {\kf} karaoke tags.
    White text with gold highlight on the current word.
    """

    # Group words into display lines of ~4-5 words
    lines = []
    current_line = []
    char_count = 0

    for wd in words:
        word = wd["word"]
        if char_count + len(word) > 25 and current_line:
            lines.append(current_line)
            current_line = []
            char_count = 0
        current_line.append(wd)
        char_count += len(word) + 1
    if current_line:
        lines.append(current_line)

    # ASS file header
    ass_content = """[Script Info]
Title: Prophetic Blessing Captions
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Helvetica Neue,62,&H00FFFFFF,&H0000D7FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,3,2,2,40,40,380,1
Style: Highlight,Helvetica Neue,62,&H0000D7FF,&H0000D7FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,3,2,2,40,40,380,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    for line_words in lines:
        if not line_words:
            continue

        line_start = line_words[0]["start"] - clip_start
        line_end = line_words[-1]["end"] - clip_start + 0.1

        if line_start < 0:
            line_start = 0
        if line_end <= 0:
            continue

        # Format timestamps as H:MM:SS.cc
        def fmt_ass_time(s):
            h = int(s // 3600)
            m = int((s % 3600) // 60)
            sec = int(s % 60)
            cs = int((s % 1) * 100)
            return f"{h}:{m:02d}:{sec:02d}.{cs:02d}"

        start_str = fmt_ass_time(line_start)
        end_str = fmt_ass_time(line_end)

        # Build the karaoke text with {\kf} tags
        # \kf = smooth fill karaoke (sweeps color from left to right)
        # Duration is in centiseconds
        karaoke_parts = []
        for wd in line_words:
            word = wd["word"].upper()
            # Duration of this word in centiseconds
            dur_cs = int((wd["end"] - wd["start"]) * 100)
            if dur_cs < 10:
                dur_cs = 10
            # Gap between words
            karaoke_parts.append(f"{{\\kf{dur_cs}}}{word} ")

        text = "".join(karaoke_parts).strip()

        ass_content += f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text}\n"

    with open(output_path, "w") as f:
        f.write(ass_content)

    print(f"  Generated {len(lines)} caption lines -> {output_path}")
    return output_path


def burn_subtitles(video_path: str, ass_path: str, output_path: str):
    """Burn ASS subtitles into the video."""
    print("  Burning captions into video...")

    # Escape the path for FFmpeg filter
    ass_escaped = ass_path.replace("'", "'\\''").replace(":", "\\:")

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"ass='{ass_escaped}'",
        "-c:v", "libx264", "-preset", "medium", "-crf", "22",
        "-c:a", "copy",
        "-movflags", "+faststart",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f"  ASS burn failed: {result.stderr[-300:]}")
        # Try with subtitles filter instead
        print("  Trying with subtitles filter...")
        cmd2 = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"subtitles='{ass_escaped}'",
            "-c:v", "libx264", "-preset", "medium", "-crf", "22",
            "-c:a", "copy",
            "-movflags", "+faststart",
            output_path,
        ]
        result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=300)
        if result2.returncode != 0:
            print(f"  Subtitles filter also failed: {result2.stderr[-300:]}")
            return False

    print(f"  Done -> {output_path}")
    return True


def main():
    if len(sys.argv) < 4:
        print("Usage: python add_captions.py <video.mp4> <words.json> <output.mp4>")
        sys.exit(1)

    video_path = sys.argv[1]
    words_json = sys.argv[2]
    output_path = sys.argv[3]

    with open(words_json) as f:
        clip_data = json.load(f)

    # Generate ASS subtitle file
    ass_path = str(Path(video_path).with_suffix(".ass"))
    generate_ass_subtitles(clip_data["words"], clip_data["start"], ass_path)

    # Burn subtitles into video
    success = burn_subtitles(video_path, ass_path, output_path)

    if success:
        print(f"\nFinal reel with captions: {output_path}")
    else:
        print(f"\nCaptions failed. Video without captions at: {video_path}")


if __name__ == "__main__":
    main()
