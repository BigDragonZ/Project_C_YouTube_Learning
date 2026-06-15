#!/usr/bin/env python3
"""
Convert SRT files to Markdown and refine with Gemini.

Usage:
    uv run flow/script/convert_and_refine.py <course_name> <start_index> <end_index>
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.youtube import parse_srt, to_markdown
from lib.refine import refine_markdown


def convert_srt_to_markdown(srt_path: Path, course_name: str, index: int, title: str) -> str:
    """Convert SRT file to markdown."""
    srt_content = srt_path.read_text(encoding="utf-8")
    entries = parse_srt(srt_content)
    
    video_url = f"https://www.youtube.com/watch?v={title.split('.')[0]}"  # Approximate
    
    markdown = to_markdown(
        entries,
        {
            "title": title,
            "url": video_url,
            "course": course_name,
            "index": index,
        },
    )
    return markdown


def process_file(course_dir: Path, course_name: str, index: int) -> bool:
    """Process a single SRT file: convert and refine."""
    # Find SRT file
    srt_files = list(course_dir.glob(f"{index:02d}-*.en.srt"))
    if not srt_files:
        print(f"  [WARN] No SRT file found for index {index}")
        return False
    
    srt_path = srt_files[0]
    title = srt_path.stem.replace(".en", "").split("-", 1)[1] if "-" in srt_path.stem else srt_path.stem
    
    print(f"\n[{index}] {title}")
    
    # Convert SRT to markdown
    print(f"  [INFO] Converting SRT...")
    try:
        markdown = convert_srt_to_markdown(srt_path, course_name, index, title)
        print(f"  [OK] Converted: {len(markdown)} chars")
    except Exception as e:
        print(f"  [ERROR] Conversion failed: {e}")
        return False
    
    # Extract body for refinement
    if "## 字幕内容" in markdown:
        body = markdown.split("## 字幕内容", 1)[1].strip()
    else:
        body = markdown
    
    # Refine
    print(f"  [INFO] Refining with Gemini...")
    try:
        refined = refine_markdown(body)
    except Exception as e:
        print(f"  [ERROR] Refinement failed: {e}")
        return False
    
    # Save refined file
    output_path = course_dir / f"{index:02d}-{title}.md"
    header = f"""# {title}

## 元信息

- **序号**: {index}
- **课程**: {course_name}
- **处理时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **来源**: 精修版

---

## 精修内容

"""
    output_path.write_text(header + refined, encoding="utf-8")
    print(f"  [OK] Saved: {output_path.name} ({len(refined)} chars)")
    
    # Remove SRT file
    srt_path.unlink()
    print(f"  [INFO] Removed SRT: {srt_path.name}")
    
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert and refine SRT files")
    parser.add_argument("course", help="Course name")
    parser.add_argument("start", type=int, help="Start index")
    parser.add_argument("end", type=int, help="End index")
    args = parser.parse_args()

    course_dir = Path("input") / args.course
    if not course_dir.exists():
        print(f"[ERROR] Course directory not found: {course_dir}")
        return 1

    print(f"=" * 60)
    print(f"Convert & Refine: {args.course}")
    print(f"Videos {args.start} to {args.end}")
    print(f"=" * 60)

    success = 0
    failed = 0

    for index in range(args.start, args.end + 1):
        try:
            if process_file(course_dir, args.course, index):
                success += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  [ERROR] Unexpected error: {e}")
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"Complete: {success}/{args.end - args.start + 1} succeeded, {failed} failed")
    print(f"{'=' * 60}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
