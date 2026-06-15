#!/usr/bin/env python3
"""
Refine existing raw markdown files that were not processed.

Usage:
    uv run flow/script/refine_existing.py <course_name> <file_index>
"""

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.refine import refine_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description="Refine existing raw markdown")
    parser.add_argument("course", help="Course name (directory under flow/)")
    parser.add_argument("index", type=int, help="File index to refine")
    args = parser.parse_args()

    course_dir = Path("input") / args.course
    if not course_dir.exists():
        print(f"[ERROR] Course directory not found: {course_dir}")
        return 1

    # Find the file
    files = list(course_dir.glob(f"{args.index:02d}-*.md"))
    if not files:
        print(f"[ERROR] No file found with index {args.index}")
        return 1

    file_path = files[0]
    print(f"[INFO] Processing: {file_path.name}")

    content = file_path.read_text(encoding="utf-8")

    # Extract body
    if "## 字幕内容" in content:
        body = content.split("## 字幕内容", 1)[1].strip()
    elif "## 转写内容" in content:
        body = content.split("## 转写内容", 1)[1].strip()
    else:
        body = content

    print(f"[INFO] Body length: {len(body)} chars")

    # Refine
    try:
        refined = refine_markdown(body)
    except Exception as e:
        print(f"[ERROR] Refinement failed: {e}")
        return 1

    # Build final content
    from datetime import datetime
    title = file_path.stem.split("_", 1)[1] if "_" in file_path.stem else file_path.stem

    header = f"""# {title}

## 元信息

- **序号**: {args.index}
- **课程**: {args.course}
- **处理时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **来源**: 精修版

---

## 精修内容

"""

    # Write refined file
    refined_path = course_dir / f"{args.index:02d}-refined_{title}.md"
    refined_path.write_text(header + refined, encoding="utf-8")
    print(f"[OK] Refined saved: {refined_path.name}")

    # Optionally remove original
    print(f"[INFO] Original file preserved: {file_path.name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
