#!/usr/bin/env python3
"""
Extract audio from video file using ffmpeg.

Usage:
    python flow/script/extract_audio.py <VIDEO_PATH> [OUTPUT_PATH]
"""

import argparse
import sys
from pathlib import Path

from lib.audio import extract_audio, probe_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract audio from video")
    parser.add_argument("video", help="Input video file path")
    parser.add_argument("output", nargs="?", help="Output audio path (default: input.mp3)")
    args = parser.parse_args()

    video_path = args.video
    if not Path(video_path).exists():
        print(f"[ERROR] Input file not found: {video_path}", file=sys.stderr)
        return 1

    out_path = args.output or video_path.replace(Path(video_path).suffix, ".mp3")

    print(f"[INFO] Input:  {video_path}")
    print(f"[INFO] Output: {out_path}")

    try:
        print("[INFO] Probing input file...")
        info = probe_file(video_path)
        print(f"[INFO] Duration: {info['duration']:.2f}s, Codec: {info['codec']}")

        print("[INFO] Extracting audio...")
        result = extract_audio(
            input_path=video_path,
            output_path=out_path,
            sample_rate=22050,
            channels=1,
            bitrate="64k",
            audio_format="mp3",
        )

        out_info = probe_file(result)
        size_mb = Path(result).stat().st_size / (1024 * 1024)

        print(f"[SUCCESS] Audio saved to: {result}")
        print(f"[INFO] Size: {size_mb:.2f} MB")
        print(f"[INFO] Duration: {out_info['duration']:.2f}s")
        print(f"[INFO] Bitrate: {out_info['bitrate']} bps")
        return 0

    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
