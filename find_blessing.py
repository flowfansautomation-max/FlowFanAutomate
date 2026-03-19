"""
Find the 'Prophetic Blessing' segment in a Flow Church video.

Strategy:
1. Transcribe the audio using faster-whisper with word-level timestamps
2. Search for communion/blessing keywords to locate the segment
3. The blessing always comes AFTER communion
4. Look for "the Lord bless you" as the primary trigger
5. Return start/end timestamps for the blessing segment
"""

import sys
import json
from pathlib import Path
from faster_whisper import WhisperModel


def transcribe_audio(video_path: str, model_size: str = "base") -> dict:
    """Transcribe video/audio and return segments with word timestamps."""
    print(f"Loading Whisper model ({model_size})...")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    print(f"Transcribing {video_path}...")
    print("This may take a while for long videos...")

    segments, info = model.transcribe(
        video_path,
        beam_size=5,
        word_timestamps=True,
        language="en",
    )

    result = {
        "language": info.language,
        "duration": info.duration,
        "segments": [],
    }

    for segment in segments:
        seg_data = {
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip(),
            "words": [],
        }
        if segment.words:
            for word in segment.words:
                seg_data["words"].append({
                    "word": word.word.strip(),
                    "start": word.start,
                    "end": word.end,
                    "probability": word.probability,
                })
        result["segments"].append(seg_data)

        # Print progress every 10 minutes of audio
        if segment.end % 600 < 30:
            hours = int(segment.end // 3600)
            mins = int((segment.end % 3600) // 60)
            print(f"  Progress: {hours}h {mins}m transcribed...")

    return result


def find_blessing_segment(transcript: dict) -> dict:
    """
    Find the Prophetic Blessing segment in the transcript.

    Strategy:
    - The blessing comes AFTER communion
    - Primary triggers: "the Lord bless you", "Lord bless you and keep you"
    - Secondary triggers: "lift your hands", "receive this blessing"
    - Communion keywords: "communion", "body of Christ", "blood of Christ",
      "bread", "cup", "take and eat"
    """

    # Flatten all text with timestamps
    full_text_segments = []
    for seg in transcript["segments"]:
        full_text_segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"].lower(),
            "words": seg.get("words", []),
        })

    # The blessing is in the LAST 20-30 minutes of the prayer meeting,
    # right after communion (body and blood of Christ).
    # Focus search on that window only.

    total_duration = transcript["duration"]

    # Phase 1: Find communion references in the last 45 minutes
    communion_keywords = [
        "communion", "body of christ", "blood of christ",
        "bread and the cup", "take and eat", "do this in remembrance",
        "holy communion", "the lord's supper", "lord's table",
        "body and the blood", "body and blood",
    ]

    search_window_start = max(0, total_duration - 2700)  # last 45 min
    print(f"  Searching last 45 minutes (from {_fmt_time(search_window_start)}) for communion...")

    communion_time = None
    for seg in full_text_segments:
        if seg["start"] < search_window_start:
            continue
        for kw in communion_keywords:
            if kw in seg["text"]:
                communion_time = seg["start"]
                print(f"  Found communion reference at {_fmt_time(seg['start'])}: ...{seg['text'][:80]}...")

    # Phase 2: Find the blessing start (comes right after communion)
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

    # Search after communion if found, otherwise search the last 30 minutes
    search_start = 0
    if communion_time:
        search_start = communion_time
        print(f"  Searching for blessing after communion ({_fmt_time(communion_time)})")
    else:
        search_start = max(0, total_duration - 1800)  # last 30 min
        print(f"  No communion found. Searching last 30 minutes (from {_fmt_time(search_start)})")

    blessing_start = None
    blessing_trigger_text = ""

    for seg in full_text_segments:
        if seg["start"] < search_start:
            continue
        for trigger in blessing_triggers:
            if trigger in seg["text"]:
                blessing_start = seg["start"]
                blessing_trigger_text = seg["text"]
                print(f"  Found blessing trigger at {_fmt_time(seg['start'])}: ...{seg['text'][:80]}...")
                break
        if blessing_start:
            break

    if not blessing_start:
        print("  WARNING: Could not find blessing segment by keywords.")
        print("  Falling back to searching for 'bless' in last 30 minutes...")
        fallback_start = max(0, total_duration - 1800)
        for seg in full_text_segments:
            if seg["start"] < fallback_start and "bless" in seg["text"]:
                blessing_start = seg["start"]
                blessing_trigger_text = seg["text"]
                print(f"  Fallback match at {_fmt_time(seg['start'])}: ...{seg['text'][:80]}...")
                break

    if not blessing_start:
        print("  ERROR: Could not locate blessing segment.")
        return None

    # Phase 3: Find the blessing end
    # The blessing typically ends with "amen" or when there's a long pause
    # or transition to something else. Look for ~5-8 minutes after start.
    blessing_end = None
    end_keywords = ["amen", "god bless you", "in jesus name", "in jesus' name"]

    # Search within 10 minutes after blessing start
    max_end = blessing_start + 600  # 10 minutes max

    last_amen = None
    for seg in full_text_segments:
        if seg["start"] < blessing_start:
            continue
        if seg["start"] > max_end:
            break
        for kw in end_keywords:
            if kw in seg["text"]:
                last_amen = seg["end"]

    if last_amen:
        blessing_end = last_amen + 2  # Add 2 seconds buffer
    else:
        # Default to 5 minutes after start
        blessing_end = blessing_start + 300
        print(f"  No clear ending found. Using 5 minutes from start.")

    duration = blessing_end - blessing_start
    print(f"\n  BLESSING SEGMENT FOUND:")
    print(f"  Start: {_fmt_time(blessing_start)}")
    print(f"  End:   {_fmt_time(blessing_end)}")
    print(f"  Duration: {duration:.0f}s ({duration/60:.1f} min)")

    # Phase 4: Extract word-level timestamps for the blessing segment
    blessing_words = []
    for seg in transcript["segments"]:
        if seg["end"] < blessing_start or seg["start"] > blessing_end:
            continue
        for word in seg.get("words", []):
            if word["start"] >= blessing_start and word["end"] <= blessing_end:
                blessing_words.append(word)

    return {
        "start": blessing_start,
        "end": blessing_end,
        "duration": duration,
        "trigger_text": blessing_trigger_text,
        "communion_time": communion_time,
        "words": blessing_words,
    }


def _fmt_time(seconds: float) -> str:
    """Format seconds as HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def main():
    if len(sys.argv) < 2:
        print("Usage: python find_blessing.py <video_path> [model_size]")
        print("  model_size: tiny, base, small, medium, large-v2 (default: base)")
        sys.exit(1)

    video_path = sys.argv[1]
    model_size = sys.argv[2] if len(sys.argv) > 2 else "base"

    if not Path(video_path).exists():
        print(f"Error: {video_path} not found")
        sys.exit(1)

    # Step 1: Transcribe
    print("=" * 60)
    print("STEP 1: Transcribing audio")
    print("=" * 60)
    transcript = transcribe_audio(video_path, model_size)

    # Save full transcript
    transcript_path = Path(video_path).with_suffix(".transcript.json")
    with open(transcript_path, "w") as f:
        json.dump(transcript, f, indent=2)
    print(f"\nFull transcript saved to {transcript_path}")

    # Step 2: Find blessing
    print("\n" + "=" * 60)
    print("STEP 2: Finding blessing segment")
    print("=" * 60)
    blessing = find_blessing_segment(transcript)

    if blessing:
        # Save blessing data
        blessing_path = Path(video_path).with_suffix(".blessing.json")
        with open(blessing_path, "w") as f:
            json.dump(blessing, f, indent=2)
        print(f"\nBlessing data saved to {blessing_path}")
    else:
        print("\nFailed to find blessing segment.")
        sys.exit(1)


if __name__ == "__main__":
    main()
