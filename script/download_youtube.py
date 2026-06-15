#!/usr/bin/env python3
"""
Download a single YouTube video.

Usage:
    python flow/script/download_youtube.py <URL>
"""

import argparse
import sys
from pathlib import Path

from config.paths import PATHS
from lib.download import download_video


def main() -> int:
    parser = argparse.ArgumentParser(description="Download YouTube video")
    parser.add_argument("url", help="YouTube video or playlist URL")
    args = parser.parse_args()

    download_dir = PATHS["download_dir"]
    download_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Target URL: {args.url}")
    print(f"[INFO] Download dir: {download_dir}")

    try:
        saved = download_video(args.url, str(download_dir))
        print(f"[SUCCESS] Saved to: {saved}")
        return 0
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
