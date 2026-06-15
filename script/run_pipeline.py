#!/usr/bin/env python3
"""
Knowledge base automation pipeline.

Usage:
    python flow/script/run_pipeline.py <PLAYLIST_URL> <COURSE_NAME> [MAX_VIDEOS]

Example:
    python flow/script/run_pipeline.py \
        "https://www.youtube.com/playlist?list=PLUl4u3cNGP63WbdFHhuCevwudurE1N2mV" \
        "Valuation_Undergrad_2022" 3
"""

import argparse
import sys

from lib.pipeline import run_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Knowledge base pipeline")
    parser.add_argument("url", help="YouTube playlist or video URL")
    parser.add_argument("course", help="Course name (directory under flow/)")
    parser.add_argument("max", nargs="?", type=int, help="Max videos to process")
    args = parser.parse_args()

    try:
        results = run_pipeline(args.url, args.course, args.max)
        success = sum(1 for r in results if r[0] is not None)
        return 0 if success > 0 else 1
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
