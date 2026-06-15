#!/usr/bin/env python3
"""
Download subtitles for a YouTube playlist using yt-dlp.

Usage:
    uv run flow/script/download_subtitles.py <playlist_url> <course_name> [start] [end]
"""

import argparse
import subprocess
import sys
from pathlib import Path


def download_subtitle(url: str, output_dir: Path, index: int, title: str) -> bool:
    """Download auto-generated subtitle for a single video."""
    safe_title = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in title).strip()
    output_template = str(output_dir / f"{index:02d}-{safe_title}")
    
    cmd = [
        "yt-dlp",
        "--write-auto-sub",
        "--sub-langs", "en",
        "--convert-subs", "srt",
        "--skip-download",
        "--output", output_template,
        url,
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            print(f"  [OK] Downloaded subtitle for {index}: {title}")
            return True
        else:
            print(f"  [WARN] Failed to download subtitle for {index}: {title}")
            print(f"    {result.stderr[:100]}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  [WARN] Timeout downloading subtitle for {index}: {title}")
        return False
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Download subtitles for playlist")
    parser.add_argument("url", help="YouTube playlist URL")
    parser.add_argument("course", help="Course name")
    parser.add_argument("start", nargs="?", type=int, default=1, help="Start index")
    parser.add_argument("end", nargs="?", type=int, help="End index")
    args = parser.parse_args()

    output_dir = Path("input") / args.course
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get playlist info
    print("[INFO] Fetching playlist info...")
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--print", "%(playlist_index)s|%(id)s|%(title)s",
        args.url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    
    if result.returncode != 0:
        print(f"[ERROR] Failed to fetch playlist: {result.stderr}")
        return 1

    videos = []
    for line in result.stdout.strip().split("\n"):
        if "|" in line:
            idx, vid, title = line.split("|", 2)
            videos.append({"index": int(idx), "id": vid, "title": title})

    # Filter range
    target = [v for v in videos if args.start <= v["index"] <= (args.end or len(videos))]
    print(f"[INFO] Processing {len(target)} videos ({args.start}-{args.end or len(videos)})")

    success = 0
    for v in target:
        url = f"https://www.youtube.com/watch?v={v['id']}"
        if download_subtitle(url, output_dir, v["index"], v["title"]):
            success += 1

    print(f"\n[OK] Downloaded {success}/{len(target)} subtitles")
    print(f"[INFO] Files saved to: {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
