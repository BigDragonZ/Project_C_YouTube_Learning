#!/usr/bin/env python3
"""
Batch process YouTube playlist videos with subtitle extraction and refinement.

Usage:
    uv run flow/script/batch_refine.py <playlist_url> <course_name> <start_index> <end_index>

Example:
    uv run flow/script/batch_refine.py \
        "https://www.youtube.com/playlist?list=..." \
        "MIT_14.01_Principles_of_Microeconomics" 3 10
"""

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.pipeline import process_video
from lib.youtube import fetch_playlist


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch process videos")
    parser.add_argument("url", help="YouTube playlist URL")
    parser.add_argument("course", help="Course name")
    parser.add_argument("start", type=int, help="Start index (1-based)")
    parser.add_argument("end", type=int, help="End index (inclusive)")
    args = parser.parse_args()

    print(f"=" * 60)
    print(f"Batch Processing: {args.course}")
    print(f"Videos {args.start} to {args.end}")
    print(f"=" * 60)

    # Fetch playlist
    print("\n[INFO] Fetching playlist...")
    playlist_title, videos = fetch_playlist(args.url)
    print(f"[OK] Playlist: {playlist_title}")
    print(f"[OK] Total videos: {len(videos)}")

    # Filter videos in range
    target_videos = [v for v in videos if args.start <= v["index"] <= args.end]
    print(f"[INFO] Processing {len(target_videos)} videos")

    # Process each
    success = 0
    failed = 0

    for video in target_videos:
        try:
            raw, refined = process_video(video, args.course, video["index"])
            if refined:
                success += 1
            elif raw:
                print(f"  [WARN] Video {video['index']}: raw saved but refinement failed")
                failed += 1
            else:
                print(f"  [ERROR] Video {video['index']}: completely failed")
                failed += 1
        except Exception as e:
            print(f"  [ERROR] Video {video['index']}: {e}")
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"Batch Complete: {success}/{len(target_videos)} succeeded, {failed} failed")
    print(f"{'=' * 60}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
