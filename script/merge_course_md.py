#!/usr/bin/env python3
"""
Merge course Markdown files into a single printable document.
User exports to PDF manually via Obsidian (ensures perfect MathJax rendering).

Files are sorted by video range (extracted from content metadata), not by filename.
This handles duplicate chapter numbers correctly.

Usage:
    uv run input/script/merge_course_md.py <course_dir> [output.md]
    uv run input/script/merge_course_md.py output/Principles_of_Microeconomics
    uv run input/script/merge_course_md.py output/Principles_of_Microeconomics merged.md
"""

import sys
import re
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ChapterFile:
    path: Path
    chapter_num: int
    title: str
    video_start: int  # Sort key: first video number from "视频范围: XX-YY"


def extract_chapter_num(filename: str) -> int:
    """Extract chapter number from filename like Ch_01_Title.md -> 1"""
    match = re.search(r'Ch_(\d+)', filename)
    return int(match.group(1)) if match else 999


def get_video_start(content: str) -> int:
    """Extract starting video number from content metadata.

    Matches patterns like:
      - 视频范围：01
      - 视频范围：06-09
      - 视频范围：14（涵盖原教材Ch10-11）
    """
    # Look for 视频范围 in metadata block
    m = re.search(r'视频范围\s*[:：]\s*(\d+)', content)
    if m:
        return int(m.group(1))
    # Fallback: use chapter number from filename * 100 to preserve rough ordering
    return 99999


def get_title_from_content(content: str) -> str:
    """Extract H1 title from markdown content."""
    for line in content.split('\n'):
        if line.startswith('# '):
            return line[2:].strip()
    return "Untitled"


def clean_content(content: str) -> str:
    """Remove metadata blocks and clean up content."""
    # Remove metadata block: > **Metadata** followed by > lines and ---
    content = re.sub(
        r'^\s*>\s*\*\*Metadata\*\*.*?\n(?:^\s*>\s*.*?\n)*^\s*---\s*\n+',
        '',
        content,
        flags=re.MULTILINE | re.DOTALL
    )

    # Remove any remaining > blockquote lines at the start
    content = re.sub(r'^(?:\s*>\s*.*?\n)+', '', content, flags=re.MULTILINE)

    # Remove the original H1 title line
    content = re.sub(r'^#\s+.+?\n+', '', content, count=1, flags=re.MULTILINE)

    return content


def shift_headings(content: str) -> str:
    """Shift all headings down one level (H1->H2, H2->H3, etc.)."""
    def replace_heading(match: re.Match) -> str:
        hashes = match.group(1)
        text = match.group(2)
        return '#' * (len(hashes) + 1) + ' ' + text

    return re.sub(r'^(#{1,5})\s+(.+)$', replace_heading, content, flags=re.MULTILINE)


def merge_course(course_dir: str, output_path: str | None = None) -> str:
    course_path = Path(course_dir).resolve()
    if not course_path.exists():
        raise FileNotFoundError(f"Course directory not found: {course_path}")

    course_name = course_path.name.replace('_', ' ')

    # Collect chapter files
    chapters: list[ChapterFile] = []
    for md_file in course_path.glob('Ch_*.md'):
        num = extract_chapter_num(md_file.name)
        content = md_file.read_text(encoding='utf-8')
        title = get_title_from_content(content)
        video_start = get_video_start(content)
        chapters.append(ChapterFile(md_file, num, title, video_start))

    # Sort by video range start (not by filename chapter number)
    chapters.sort(key=lambda c: c.video_start)

    if not chapters:
        raise ValueError(f"No Ch_XX.md files found in {course_path}")

    # Build merged content
    lines: list[str] = []

    # Title page
    lines.append(f"# {course_name}")
    lines.append("")
    lines.append(f"> **署名**：DALONG ZHANG")
    lines.append(f"> **章节数**：{len(chapters)}")
    lines.append(f"> **生成时间**：2026")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Table of contents
    lines.append("## 目录")
    lines.append("")
    for ch in chapters:
        # Strip "Ch.XX " prefix from title if present to avoid duplication
        display_title = re.sub(r'^Ch\.\d+\s+', '', ch.title)
        lines.append(f"- Ch.{ch.chapter_num:02d} {display_title}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Merge each chapter
    for ch in chapters:
        content = ch.path.read_text(encoding='utf-8')
        content = clean_content(content)
        content = shift_headings(content)

        # Add page break comment before each chapter
        lines.append("<!-- pagebreak -->")
        lines.append("")
        lines.append(f"## Ch.{ch.chapter_num:02d} {ch.title}")
        lines.append("")
        lines.append(content.strip())
        lines.append("")
        lines.append("---")
        lines.append("")

    # Write output
    if output_path is None:
        output_path = str(course_path / f"{course_path.name}_打印版.md")
    else:
        output_path = str(Path(output_path).resolve())

    merged = '\n'.join(lines)
    Path(output_path).write_text(merged, encoding='utf-8')

    print(f"Merged {len(chapters)} chapters into: {output_path}")
    print(f"Order (by video range): {', '.join(f'Ch.{c.chapter_num:02d}(v{c.video_start})' for c in chapters)}")
    return output_path


def main():
    if len(sys.argv) < 2:
        print("Usage: merge_course_md.py <course_dir> [output.md]")
        print("Example: merge_course_md.py output/Principles_of_Microeconomics")
        sys.exit(1)

    course_dir = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    merge_course(course_dir, output_path)


if __name__ == "__main__":
    main()
