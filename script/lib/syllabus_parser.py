"""
Parse NotebookLM syllabus output into structured Chapter objects.
"""

import re
from pathlib import Path
from typing import Optional

from models.note import Chapter


_CHINESE_NUMERALS = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
}


def _parse_chapter_number(s: str) -> int:
    """Parse Chinese or Arabic numeral."""
    if s.isdigit():
        return int(s)
    total = 0
    for c in s:
        if c in _CHINESE_NUMERALS:
            total += _CHINESE_NUMERALS[c]
    return total if total > 0 else 0


def parse_syllabus(text: str) -> list[Chapter]:
    """
    Parse NotebookLM syllabus markdown into Chapter objects.

    Expected format:
      ## 第N章：章节标题
      - **核心命题**：...
      - **视频范围**：XX-XX
      - **前置知识**：[[Ch_XX_...]] | ...
      - **本章概要**：...
    """
    chapters: list[Chapter] = []

    # Match both Chinese numerals (第一章) and Arabic (第1章)
    pattern = r'##\s*第([一二三四五六七八九十\d]+)章\s*\uff1a\s*(.+?)(?=\n##\s*第|\Z)'
    matches = re.findall(pattern, text, re.DOTALL)

    for num_str, content in matches:
        idx = _parse_chapter_number(num_str)
        if idx == 0:
            continue

        # Extract title (first line)
        title_match = re.search(r"^(.+?)(?:\n|$)", content.strip())
        title = title_match.group(1).strip() if title_match else f"Chapter {idx}"

        # Extract thesis
        thesis_match = re.search(r"\*\*核心命题\*\*\s*[：:]\s*(.+?)(?:\n|$)", content)
        thesis = thesis_match.group(1).strip() if thesis_match else ""

        # Extract video range
        range_match = re.search(r"\*\*视频范围\*\*\s*[：:]\s*(.+?)(?:\n|$)", content)
        video_range = range_match.group(1).strip() if range_match else ""

        # Extract prerequisites (wikilinks)
        prereq_match = re.search(r"\*\*前置知识\*\*\s*[：:]\s*(.+?)(?:\n|$)", content)
        prerequisites: list[str] = []
        if prereq_match:
            prereq_text = prereq_match.group(1)
            prerequisites = re.findall(r"\[\[(.+?)\]\]", prereq_text)

        # Extract summary
        summary_match = re.search(r"\*\*本章概要\*\*\s*[：:]\s*(.+?)(?=\n##|\Z)", content, re.DOTALL)
        summary = summary_match.group(1).strip() if summary_match else ""

        chapters.append(
            Chapter(
                index=idx,
                title=title,
                thesis=thesis,
                video_range=video_range,
                prerequisites=prerequisites,
                summary=summary,
            )
        )

    return chapters


def save_syllabus(text: str, course_name: str, output_dir: Path) -> Path:
    """Save raw syllabus text to file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{course_name}_课程大纲.md"
    path.write_text(text, encoding="utf-8")
    return path


def load_syllabus(path: Path) -> list[Chapter]:
    """Load and parse syllabus from file."""
    text = path.read_text(encoding="utf-8")
    return parse_syllabus(text)
