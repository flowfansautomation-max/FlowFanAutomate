"""
Batch process a Flow Church video: download, transcribe last 30 min,
find blessing, extract all possible reels with clean sentence endings.
"""

import json
import subprocess
import sys
import os
from pathlib import Path


def run(cmd, timeout=600):
    """Run a shell command and return output."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0 and "Error" in result.stderr:
        print(f"  CMD ERROR: {result.stderr[-200:]}")
    return result


def download_video(video_id, output_dir):
    """Download video from YouTube."""
    out_path = f"{output_dir}/full_video.mp4"
    if os.path.exists(out_path):
        print(f"  Already downloaded: {out_path}")
        return out_path

    print(f"  Downloading {video_id}...")
    r = run(f'yt-dlp -f 18 --no-part -o "{out_path}" "https://www.youtube.com/watch?v={video_id}"', timeout=1200)
    if not os.path.exists(out_path):
        print(f"  Download failed!")
        return None
    return out_path


def get_duration(video_path):
    """Get video duration in seconds."""
    r = run(f'ffprobe -v quiet -show_format "{video_path}"')
    for line in r.stdout.split("\n"):
        if line.startswith("duration="):
            return float(line.split("=")[1])
    return 0


def extract_last_30min(video_path, output_dir):
    """Extract last 30 minutes of video."""
    out_path = f"{output_dir}/last_30min.mp4"
    if os.path.exists(out_path):
        print(f"  Already extracted: {out_path}")
        return out_path

    duration = get_duration(video_path)
    start = max(0, duration - 1800)
    h, m, s = int(start // 3600), int((start % 3600) // 60), int(start % 60)
    print(f"  Extracting last 30 min (from {h}:{m:02d}:{s:02d})...")
    run(f'ffmpeg -y -ss {start} -i "{video_path}" -c copy "{out_path}"')
    return out_path


def transcribe_and_find_blessing(audio_path, output_dir):
    """Transcribe and find the blessing segment."""
    transcript_path = f"{output_dir}/last_30min.transcript.json"
    blessing_path = f"{output_dir}/last_30min.blessing.json"

    if os.path.exists(blessing_path):
        print(f"  Already found blessing: {blessing_path}")
        with open(blessing_path) as f:
            return json.load(f)

    # Import and run find_blessing
    sys.path.insert(0, str(Path(__file__).parent))
    from find_blessing import transcribe_audio, find_blessing_segment

    transcript = transcribe_audio(audio_path, "base")
    with open(transcript_path, "w") as f:
        json.dump(transcript, f, indent=2)

    blessing = find_blessing_segment(transcript)
    if blessing:
        with open(blessing_path, "w") as f:
            json.dump(blessing, f, indent=2)
    return blessing


def find_reel_boundaries(transcript_path, blessing_start, blessing_end):
    """
    Find natural sentence boundaries within the blessing to create
    multiple reels. Each reel should be 60-120 seconds and end on
    a complete thought.
    """
    with open(transcript_path) as f:
        transcript = json.load(f)

    # Get all segments in the blessing range
    blessing_segs = []
    for seg in transcript["segments"]:
        if seg["end"] < blessing_start - 5:
            continue
        if seg["start"] > blessing_end + 5:
            break
        blessing_segs.append(seg)

    if not blessing_segs:
        return []

    # Find strong ending points (sentences ending with period, "amen", "Jesus", "Lord", etc.)
    end_markers = ["amen", "amen.", "jesus.", "lord.", "name.", "you.", "life.", "strength.",
                   "blessed.", "healed.", "christ.", "god.", "peace.", "forever.", "begotten."]

    potential_ends = []
    for seg in blessing_segs:
        text_lower = seg["text"].lower().strip()
        last_word = text_lower.split()[-1] if text_lower.split() else ""
        # Check if segment ends on a strong note
        is_strong_end = (
            last_word.rstrip(".!,") in ["amen", "jesus", "lord", "christ", "god", "blessed",
                                         "healed", "peace", "life", "strength", "forever",
                                         "you", "name", "world", "begotten"] or
            text_lower.endswith(".") or
            text_lower.endswith("!") or
            "amen" in text_lower[-10:] or
            "in jesus" in text_lower[-20:] or
            "god bless you" in text_lower
        )
        if is_strong_end:
            potential_ends.append(seg["end"])

    # Build reels: aim for 60-120 seconds each
    reels = []
    reel_start = blessing_start
    min_duration = 55
    max_duration = 130

    for end_time in potential_ends:
        duration = end_time - reel_start
        if duration >= min_duration:
            reels.append({"start": reel_start, "end": end_time, "duration": duration})
            reel_start = end_time + 0.5  # Small gap for next reel

    # If we have leftover content at the end
    if reel_start < blessing_end - 30:
        # Find any end point
        for end_time in potential_ends:
            if end_time > reel_start + 30:
                reels.append({"start": reel_start, "end": end_time,
                             "duration": end_time - reel_start})
                break

    # Filter out reels that are too long (split them)
    final_reels = []
    for reel in reels:
        if reel["duration"] <= max_duration:
            final_reels.append(reel)
        else:
            # Try to find a midpoint
            mid_ends = [e for e in potential_ends
                       if reel["start"] + min_duration < e < reel["end"] - 30]
            if mid_ends:
                split = mid_ends[len(mid_ends) // 2]
                final_reels.append({"start": reel["start"], "end": split,
                                   "duration": split - reel["start"]})
                final_reels.append({"start": split + 0.5, "end": reel["end"],
                                   "duration": reel["end"] - split - 0.5})
            else:
                final_reels.append(reel)  # Keep as-is if can't split

    return final_reels


def create_reel(clip_path, output_path):
    """Create vertical reel from a clip."""
    run(
        f'ffmpeg -y -i "{clip_path}" '
        f'-vf "scale=1080:607,pad=1080:1920:(ow-iw)/2:(oh-ih)/2.5:black" '
        f'-c:v libx264 -preset medium -crf 22 '
        f'-c:a aac -b:a 128k '
        f'-movflags +faststart -r 30 '
        f'"{output_path}"'
    )


def process_video(video_id, title, output_dir):
    """Full pipeline for one video."""
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n{'='*60}")
    print(f"PROCESSING: {title}")
    print(f"{'='*60}")

    # Step 1: Download
    video_path = download_video(video_id, output_dir)
    if not video_path:
        return []

    # Step 2: Extract last 30 min
    last30_path = extract_last_30min(video_path, output_dir)

    # Step 3: Transcribe and find blessing
    print("  Transcribing...")
    blessing = transcribe_and_find_blessing(last30_path, output_dir)
    if not blessing:
        print("  ERROR: Could not find blessing segment!")
        return []

    b_start = blessing["start"]
    b_end = blessing["end"]
    b_dur = b_end - b_start
    print(f"  Blessing: {int(b_start//60)}:{int(b_start%60):02d} - {int(b_end//60)}:{int(b_end%60):02d} ({b_dur:.0f}s)")

    # Step 4: Find reel boundaries
    transcript_path = f"{output_dir}/last_30min.transcript.json"
    reel_boundaries = find_reel_boundaries(transcript_path, b_start, b_end)

    if not reel_boundaries:
        # Fallback: create one big reel from the whole blessing
        reel_boundaries = [{"start": b_start, "end": b_end, "duration": b_dur}]

    print(f"  Found {len(reel_boundaries)} reel(s)")

    # Step 5: Create reels
    reel_files = []
    for i, reel in enumerate(reel_boundaries):
        clip_path = f"{output_dir}/clip_{i+1}_raw.mp4"
        reel_path = f"{output_dir}/reel_{i+1}.mp4"

        dur = reel["end"] - reel["start"]
        print(f"  Reel {i+1}: {int(reel['start']//60)}:{int(reel['start']%60):02d} - "
              f"{int(reel['end']//60)}:{int(reel['end']%60):02d} ({dur:.0f}s)")

        # Extract clip
        run(f'ffmpeg -y -ss {reel["start"]} -i "{last30_path}" -t {dur} -c copy "{clip_path}"')

        # Create vertical reel
        create_reel(clip_path, reel_path)

        if os.path.exists(reel_path):
            size_mb = os.path.getsize(reel_path) / 1024 / 1024
            reel_files.append(reel_path)
            print(f"    -> {reel_path} ({size_mb:.1f}MB)")

    return reel_files


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python batch_process.py <video_id> <title>")
        sys.exit(1)

    video_id = sys.argv[1]
    title = sys.argv[2]
    output_dir = f"processing/{video_id}"

    reels = process_video(video_id, title, output_dir)
    print(f"\n{'='*60}")
    print(f"DONE: {len(reels)} reel(s) created")
    for r in reels:
        print(f"  {r}")
    print(f"{'='*60}")
