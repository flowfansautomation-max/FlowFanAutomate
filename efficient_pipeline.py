"""
Efficient FlowFanAutomate Pipeline v2

Two-pass approach:
  Pass 1: Grab YouTube auto-captions for playlist videos, scan for
          communion → blessing keywords. No downloads needed.
  Pass 2: Download ONLY the blessing segments from videos that matched,
          then create reels with glitch validation.

Key improvements over v1:
  - No full video downloads (segment-only via yt-dlp --download-sections)
  - No Whisper transcription (uses YouTube auto-captions)
  - Multi-format glitch detection (compares format streams)
  - validate_clip() after every reel creation
"""

import json
import subprocess
import sys
import os
import re
from pathlib import Path


# ── Helpers ──────────────────────────────────────────────────────────────

def run(cmd, timeout=600):
    """Run a shell command and return result."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0 and result.stderr:
        # Only print real errors, not info messages
        err = result.stderr.strip()
        if err and "Error" in err:
            print(f"  CMD ERROR: {err[-300:]}")
    return result


def fmt_time(seconds):
    """Format seconds as HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# ── Pass 1: Auto-Caption Scanning ────────────────────────────────────────

def fetch_auto_captions(video_id, output_dir):
    """
    Download YouTube auto-captions (json3 format) without downloading video.
    Returns path to caption file, or None if unavailable.
    """
    os.makedirs(output_dir, exist_ok=True)
    caption_path = f"{output_dir}/{video_id}.en.json3"

    if os.path.exists(caption_path):
        return caption_path

    print(f"  Fetching auto-captions for {video_id}...")
    r = run(
        f'yt-dlp --write-auto-sub --sub-lang en --sub-format json3 '
        f'--skip-download --no-warnings '
        f'-o "{output_dir}/{video_id}" '
        f'"https://www.youtube.com/watch?v={video_id}"',
        timeout=60
    )

    # yt-dlp saves as video_id.en.json3
    if os.path.exists(caption_path):
        return caption_path

    # Try alternative naming
    for ext in [".en.json3", ".en-orig.json3"]:
        alt = f"{output_dir}/{video_id}{ext}"
        if os.path.exists(alt):
            return alt

    print(f"  No auto-captions available for {video_id}")
    return None


def parse_json3_captions(caption_path):
    """
    Parse YouTube json3 caption format into segments with timestamps.
    Returns list of {start, end, text} dicts (times in seconds).
    """
    with open(caption_path) as f:
        data = json.load(f)

    segments = []
    for event in data.get("events", []):
        start_ms = event.get("tStartMs", 0)
        dur_ms = event.get("dDurationMs", 0)

        # Build text from segs
        text_parts = []
        for seg in event.get("segs", []):
            utf8 = seg.get("utf8", "").strip()
            if utf8 and utf8 != "\n":
                text_parts.append(utf8)

        text = " ".join(text_parts).strip()
        if not text:
            continue

        segments.append({
            "start": start_ms / 1000.0,
            "end": (start_ms + dur_ms) / 1000.0,
            "text": text,
        })

    return segments


def scan_for_blessing(segments, total_duration=None):
    """
    Scan caption segments for communion → blessing pattern.
    Returns {blessing_start, blessing_end, communion_time} or None.
    """
    if not segments:
        return None

    if total_duration is None:
        total_duration = segments[-1]["end"] if segments else 0

    # Only search the last 30 minutes
    search_start = max(0, total_duration - 1800)

    # Phase 1: Find communion
    communion_keywords = [
        "communion", "body of christ", "blood of christ",
        "bread and the cup", "take and eat", "do this in remembrance",
        "holy communion", "lord's supper", "lord's table",
        "body and the blood", "body and blood",
    ]

    communion_time = None
    for seg in segments:
        if seg["start"] < search_start:
            continue
        text_lower = seg["text"].lower()
        for kw in communion_keywords:
            if kw in text_lower:
                communion_time = seg["start"]

    # Phase 2: Find blessing trigger (after communion if found)
    blessing_triggers = [
        "the lord bless you",
        "lord bless you and keep you",
        "may the lord bless",
        "the lord make his face",
        "the lord lift up",
        "i bless you in the name",
        "receive this blessing",
        "i speak a blessing",
        "blessing of the lord",
    ]

    b_search_start = communion_time if communion_time else search_start
    blessing_start = None

    for seg in segments:
        if seg["start"] < b_search_start:
            continue
        text_lower = seg["text"].lower()
        for trigger in blessing_triggers:
            if trigger in text_lower:
                blessing_start = seg["start"]
                break
        if blessing_start:
            break

    # Fallback: search for "bless" in last 30 min
    if not blessing_start:
        for seg in segments:
            if seg["start"] < search_start:
                continue
            if "bless" in seg["text"].lower():
                blessing_start = seg["start"]
                break

    if not blessing_start:
        return None

    # Phase 3: Find blessing end
    end_keywords = ["amen", "god bless you", "in jesus name", "in jesus' name"]
    max_end = blessing_start + 600
    last_amen = None

    for seg in segments:
        if seg["start"] < blessing_start:
            continue
        if seg["start"] > max_end:
            break
        text_lower = seg["text"].lower()
        for kw in end_keywords:
            if kw in text_lower:
                last_amen = seg["end"]

    blessing_end = (last_amen + 2) if last_amen else (blessing_start + 300)

    return {
        "blessing_start": blessing_start,
        "blessing_end": blessing_end,
        "duration": blessing_end - blessing_start,
        "communion_time": communion_time,
    }


def scan_playlist(playlist_url, captions_dir="captions"):
    """
    Pass 1: Scan entire playlist for videos with blessings.
    Returns list of {video_id, title, blessing_start, blessing_end, ...}.
    """
    print("=" * 60)
    print("PASS 1: Scanning playlist for blessings via auto-captions")
    print("=" * 60)

    # Get playlist video IDs and titles
    print("Fetching playlist info...")
    r = run(
        f'yt-dlp --flat-playlist --print "%(id)s|||%(title)s|||%(duration)s" '
        f'--no-warnings "{playlist_url}"',
        timeout=120
    )

    videos = []
    for line in r.stdout.strip().split("\n"):
        if "|||" not in line:
            continue
        parts = line.split("|||")
        if len(parts) >= 2:
            vid_id = parts[0].strip()
            title = parts[1].strip()
            dur = float(parts[2].strip()) if len(parts) > 2 and parts[2].strip() else 0
            videos.append({"id": vid_id, "title": title, "duration": dur})

    print(f"Found {len(videos)} videos in playlist\n")

    hits = []
    for i, video in enumerate(videos):
        print(f"[{i+1}/{len(videos)}] {video['title'][:50]}...")

        # Skip very short videos (< 30 min) — unlikely to have blessing
        if video["duration"] and video["duration"] < 1800:
            print(f"  Skipping (too short: {video['duration']/60:.0f} min)")
            continue

        # Fetch auto-captions
        caption_path = fetch_auto_captions(video["id"], captions_dir)
        if not caption_path:
            print(f"  Skipping (no captions)")
            continue

        # Parse and scan
        segments = parse_json3_captions(caption_path)
        if not segments:
            print(f"  Skipping (empty captions)")
            continue

        total_dur = video["duration"] or (segments[-1]["end"] if segments else 0)
        result = scan_for_blessing(segments, total_dur)

        if result:
            hit = {
                "video_id": video["id"],
                "title": video["title"],
                "duration": total_dur,
                **result,
            }
            hits.append(hit)
            print(f"  BLESSING FOUND: {fmt_time(result['blessing_start'])} - "
                  f"{fmt_time(result['blessing_end'])} "
                  f"({result['duration']:.0f}s)")
        else:
            print(f"  No blessing found")

    print(f"\n{'=' * 60}")
    print(f"Pass 1 complete: {len(hits)} videos with blessings out of {len(videos)}")
    print(f"{'=' * 60}\n")

    return hits


# ── Pass 2: Segment Download + Reel Creation ─────────────────────────────

def download_segment(video_id, start_sec, end_sec, output_dir, fmt="18"):
    """
    Download only the blessing segment using yt-dlp --download-sections.
    Tries multiple formats for glitch comparison.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Add 10s buffer on each side
    dl_start = max(0, start_sec - 10)
    dl_end = end_sec + 10

    out_path = f"{output_dir}/blessing_segment.mp4"
    if os.path.exists(out_path):
        print(f"  Already downloaded segment: {out_path}")
        return out_path

    start_str = fmt_time(dl_start)
    end_str = fmt_time(dl_end)

    print(f"  Downloading segment {start_str} - {end_str} (format {fmt})...")
    r = run(
        f'yt-dlp -f {fmt} '
        f'--download-sections "*{dl_start}-{dl_end}" '
        f'--no-part --force-keyframes-at-cuts '
        f'-o "{out_path}" '
        f'"https://www.youtube.com/watch?v={video_id}"',
        timeout=300
    )

    if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
        size_mb = os.path.getsize(out_path) / 1024 / 1024
        print(f"  Downloaded: {size_mb:.1f}MB")
        return out_path

    print(f"  Segment download failed!")
    return None


def download_segment_alt_format(video_id, start_sec, end_sec, output_dir):
    """
    Download the same segment in an alternative format for glitch comparison.
    Returns path or None.
    """
    alt_path = f"{output_dir}/blessing_segment_alt.mp4"
    if os.path.exists(alt_path):
        return alt_path

    dl_start = max(0, start_sec - 10)
    dl_end = end_sec + 10

    # Try format 22 (720p mp4) as alternative
    print(f"  Downloading alt format for glitch comparison...")
    r = run(
        f'yt-dlp -f 22 '
        f'--download-sections "*{dl_start}-{dl_end}" '
        f'--no-part --force-keyframes-at-cuts '
        f'-o "{alt_path}" '
        f'"https://www.youtube.com/watch?v={video_id}"',
        timeout=300
    )

    if os.path.exists(alt_path) and os.path.getsize(alt_path) > 10000:
        return alt_path

    # Try best mp4
    r = run(
        f'yt-dlp -f "best[ext=mp4]" '
        f'--download-sections "*{dl_start}-{dl_end}" '
        f'--no-part --force-keyframes-at-cuts '
        f'-o "{alt_path}" '
        f'"https://www.youtube.com/watch?v={video_id}"',
        timeout=300
    )

    if os.path.exists(alt_path) and os.path.getsize(alt_path) > 10000:
        return alt_path

    return None


# ── Glitch Detection & Validation ────────────────────────────────────────

def validate_clip(clip_path, max_freeze_sec=3.0, max_black_sec=2.0, max_silence_sec=5.0):
    """
    Validate a clip for glitches using FFmpeg detection filters.
    Returns (is_valid, issues_list).

    Checks:
      - Freeze frames (sustained identical frames)
      - Black frames (unexpected black sections)
      - Extended silence (long gaps with no audio)
    """
    issues = []

    if not os.path.exists(clip_path):
        return False, ["File does not exist"]

    file_size = os.path.getsize(clip_path)
    if file_size < 10000:
        return False, ["File too small (likely corrupt)"]

    # Check for freeze frames
    print(f"    Checking for freeze frames...")
    r = run(
        f'ffmpeg -i "{clip_path}" -vf "freezedetect=n=-60dB:d=2" '
        f'-an -f null - 2>&1',
        timeout=120
    )
    output = r.stdout + r.stderr
    freeze_matches = re.findall(r'freeze_duration:\s*([\d.]+)', output)
    total_freeze = sum(float(d) for d in freeze_matches)
    if total_freeze > max_freeze_sec:
        issues.append(f"Freeze frames: {total_freeze:.1f}s total")

    # Check for black frames
    print(f"    Checking for black frames...")
    r = run(
        f'ffmpeg -i "{clip_path}" -vf "blackdetect=d=1:pix_th=0.10" '
        f'-an -f null - 2>&1',
        timeout=120
    )
    output = r.stdout + r.stderr
    black_matches = re.findall(r'black_duration:\s*([\d.]+)', output)
    total_black = sum(float(d) for d in black_matches)
    if total_black > max_black_sec:
        issues.append(f"Black frames: {total_black:.1f}s total")

    # Check for extended silence
    print(f"    Checking for silence...")
    r = run(
        f'ffmpeg -i "{clip_path}" -af "silencedetect=n=-40dB:d=3" '
        f'-vn -f null - 2>&1',
        timeout=120
    )
    output = r.stdout + r.stderr
    silence_matches = re.findall(r'silence_duration:\s*([\d.]+)', output)
    total_silence = sum(float(d) for d in silence_matches)
    if total_silence > max_silence_sec:
        issues.append(f"Extended silence: {total_silence:.1f}s total")

    is_valid = len(issues) == 0
    if is_valid:
        print(f"    PASSED validation")
    else:
        print(f"    FAILED: {'; '.join(issues)}")

    return is_valid, issues


def check_source_glitches(primary_path, alt_path=None):
    """
    Check if the source video segment has glitches.
    If alt_path is provided, compare both — if both have glitches,
    the source video itself is bad and should be skipped.
    """
    primary_valid, primary_issues = validate_clip(
        primary_path, max_freeze_sec=5.0, max_black_sec=3.0, max_silence_sec=8.0
    )

    if primary_valid:
        return True, primary_path

    if alt_path and os.path.exists(alt_path):
        print(f"  Primary format has issues: {primary_issues}")
        print(f"  Checking alt format...")
        alt_valid, alt_issues = validate_clip(
            alt_path, max_freeze_sec=5.0, max_black_sec=3.0, max_silence_sec=8.0
        )
        if alt_valid:
            print(f"  Using alt format (primary had glitches)")
            return True, alt_path
        else:
            print(f"  BOTH formats have glitches — skipping this video")
            return False, None

    print(f"  Source has glitches and no alt format available — skipping")
    return False, None


# ── Reel Boundaries ──────────────────────────────────────────────────────

def find_reel_boundaries_from_captions(caption_segments, blessing_start, blessing_end):
    """
    Find natural sentence boundaries within the blessing using caption data.
    Each reel should be 55-130 seconds and end on a complete thought.
    """
    # Get blessing-range segments
    blessing_segs = [
        s for s in caption_segments
        if s["end"] >= blessing_start - 5 and s["start"] <= blessing_end + 5
    ]

    if not blessing_segs:
        return [{"start": blessing_start, "end": blessing_end,
                 "duration": blessing_end - blessing_start}]

    # Find strong ending points
    end_words = {"amen", "jesus", "lord", "christ", "god", "blessed",
                 "healed", "peace", "life", "strength", "forever",
                 "you", "name", "world", "begotten"}

    potential_ends = []
    for seg in blessing_segs:
        text = seg["text"].lower().strip()
        last_word = text.split()[-1].rstrip(".,!?") if text.split() else ""
        is_strong = (
            last_word in end_words or
            text.endswith(".") or text.endswith("!") or
            "amen" in text[-10:] or
            "in jesus" in text[-20:] or
            "god bless you" in text
        )
        if is_strong:
            potential_ends.append(seg["end"])

    # Build reels: 55-130 seconds each
    reels = []
    reel_start = blessing_start
    min_dur, max_dur = 55, 130

    for end_time in potential_ends:
        dur = end_time - reel_start
        if dur >= min_dur:
            reels.append({"start": reel_start, "end": end_time, "duration": dur})
            reel_start = end_time + 0.5

    # Leftover
    if reel_start < blessing_end - 30:
        for end_time in potential_ends:
            if end_time > reel_start + 30:
                reels.append({"start": reel_start, "end": end_time,
                             "duration": end_time - reel_start})
                break

    # Split reels that are too long
    final = []
    for reel in reels:
        if reel["duration"] <= max_dur:
            final.append(reel)
        else:
            mid_ends = [e for e in potential_ends
                       if reel["start"] + min_dur < e < reel["end"] - 30]
            if mid_ends:
                split = mid_ends[len(mid_ends) // 2]
                final.append({"start": reel["start"], "end": split,
                             "duration": split - reel["start"]})
                final.append({"start": split + 0.5, "end": reel["end"],
                             "duration": reel["end"] - split - 0.5})
            else:
                final.append(reel)

    return final if final else [{"start": blessing_start, "end": blessing_end,
                                  "duration": blessing_end - blessing_start}]


# ── Reel Creation ────────────────────────────────────────────────────────

def create_reel(clip_path, output_path):
    """Create vertical 9:16 reel from a clip (letterboxed style)."""
    run(
        f'ffmpeg -y -i "{clip_path}" '
        f'-vf "scale=1080:607,pad=1080:1920:(ow-iw)/2:(oh-ih)/2.5:black" '
        f'-c:v libx264 -preset medium -crf 22 '
        f'-c:a aac -b:a 128k '
        f'-movflags +faststart -r 30 '
        f'"{output_path}"'
    )


# ── Main Pipeline ────────────────────────────────────────────────────────

def process_hit(hit, output_base="processing", captions_dir="captions"):
    """
    Pass 2 for a single video: download segment, create reels, validate.
    """
    vid = hit["video_id"]
    output_dir = f"{output_base}/{vid}"
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n{'=' * 60}")
    print(f"PROCESSING: {hit['title'][:50]}")
    print(f"Blessing: {fmt_time(hit['blessing_start'])} - {fmt_time(hit['blessing_end'])} "
          f"({hit['duration']:.0f}s)")
    print(f"{'=' * 60}")

    # Step 1: Download only the blessing segment
    segment_path = download_segment(
        vid, hit["blessing_start"], hit["blessing_end"], output_dir
    )
    if not segment_path:
        return []

    # Step 2: Download alt format for glitch comparison
    alt_path = download_segment_alt_format(
        vid, hit["blessing_start"], hit["blessing_end"], output_dir
    )

    # Step 3: Check source for glitches
    source_ok, use_path = check_source_glitches(segment_path, alt_path)
    if not source_ok:
        print(f"  SKIPPING {vid} — source video has glitches")
        return []

    # Step 4: Get reel boundaries from captions
    caption_path = f"{captions_dir}/{vid}.en.json3"
    if not os.path.exists(caption_path):
        # Check alt naming
        for ext in [".en.json3", ".en-orig.json3"]:
            alt_cap = f"{captions_dir}/{vid}{ext}"
            if os.path.exists(alt_cap):
                caption_path = alt_cap
                break

    # Calculate offset: segment was downloaded starting from (blessing_start - 10)
    segment_offset = max(0, hit["blessing_start"] - 10)

    if os.path.exists(caption_path):
        cap_segments = parse_json3_captions(caption_path)
        reel_bounds = find_reel_boundaries_from_captions(
            cap_segments, hit["blessing_start"], hit["blessing_end"]
        )
    else:
        reel_bounds = [{"start": hit["blessing_start"], "end": hit["blessing_end"],
                        "duration": hit["duration"]}]

    print(f"  Found {len(reel_bounds)} potential reel(s)")

    # Step 5: Create and validate reels
    valid_reels = []
    for i, reel in enumerate(reel_bounds):
        clip_path = f"{output_dir}/clip_{i+1}_raw.mp4"
        reel_path = f"{output_dir}/reel_{i+1}.mp4"

        # Adjust times relative to the downloaded segment
        clip_start = reel["start"] - segment_offset
        clip_dur = reel["end"] - reel["start"]

        print(f"\n  Reel {i+1}: {fmt_time(reel['start'])} - {fmt_time(reel['end'])} "
              f"({clip_dur:.0f}s)")

        # Extract clip from segment
        run(f'ffmpeg -y -ss {clip_start} -i "{use_path}" -t {clip_dur} -c copy "{clip_path}"')

        if not os.path.exists(clip_path):
            print(f"    Failed to extract clip")
            continue

        # Create vertical reel
        create_reel(clip_path, reel_path)

        if not os.path.exists(reel_path):
            print(f"    Failed to create reel")
            continue

        # Validate the reel
        is_valid, issues = validate_clip(reel_path)

        if is_valid:
            size_mb = os.path.getsize(reel_path) / 1024 / 1024
            valid_reels.append(reel_path)
            print(f"    VALID -> {reel_path} ({size_mb:.1f}MB)")
        else:
            print(f"    REJECTED: {'; '.join(issues)}")
            os.remove(reel_path)  # Remove invalid reel

    return valid_reels


def run_pipeline(playlist_url, target_reels=30, output_base="processing",
                 captions_dir="captions", skip_videos=None):
    """
    Full efficient pipeline:
      1. Scan playlist via auto-captions
      2. Download & process only blessing segments
      3. Validate every reel
      4. Stop when target reel count is reached
    """
    skip_videos = skip_videos or set()

    # Pass 1: Scan
    hits = scan_playlist(playlist_url, captions_dir)

    # Filter out already-processed or skipped videos
    hits = [h for h in hits if h["video_id"] not in skip_videos]

    print(f"\n{len(hits)} videos to process (target: {target_reels} reels)\n")

    # Pass 2: Process
    all_reels = []
    for hit in hits:
        if len(all_reels) >= target_reels:
            print(f"\nReached target of {target_reels} reels!")
            break

        reels = process_hit(hit, output_base, captions_dir)
        all_reels.extend(reels)
        print(f"\n  Total valid reels so far: {len(all_reels)}/{target_reels}")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"PIPELINE COMPLETE")
    print(f"{'=' * 60}")
    print(f"Total valid reels: {len(all_reels)}")
    for r in all_reels:
        size_mb = os.path.getsize(r) / 1024 / 1024
        print(f"  {r} ({size_mb:.1f}MB)")

    # Save manifest
    manifest = {
        "total_reels": len(all_reels),
        "reels": all_reels,
        "source_videos": [h["video_id"] for h in hits[:len(all_reels)]],
    }
    manifest_path = f"{output_base}/reel_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nManifest saved to {manifest_path}")

    return all_reels


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python efficient_pipeline.py <playlist_url> [target_reels]")
        print("  target_reels: Number of reels to create (default: 30)")
        sys.exit(1)

    playlist_url = sys.argv[1]
    target = int(sys.argv[2]) if len(sys.argv) > 2 else 30

    # Videos already processed (from previous sessions)
    already_done = {
        "h6UijMty_Bo", "Datz3l0R_UM", "rfRyHwiQPF8", "VAt4SnbaS30",
        "lc3OXqV1JAE", "8p5Tw47i6VM", "6lzpKbqnSQE", "C5iW6jevCZk",
        "rGogQJNpT8U", "Bw367BiyUz4",
    }

    run_pipeline(playlist_url, target, skip_videos=already_done)
