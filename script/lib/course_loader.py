"""
Load course context from raw transcription directory.

Scans the raw note directory for:
  - Video markdown files (NN-Title.md)
  - _index.md for video metadata
"""

import re
from pathlib import Path
from typing import Optional

from models.note import VideoInfo
from config.note_paths import raw_note_dir, index_path


def _parse_filename(filename: str) -> tuple[Optional[int], str]:
    """Parse index and title from filename like '01-Title.md'."""
    match = re.match(r"^(\d+)[-\s]*(.+)\.md$", filename)
    if match:
        return int(match.group(1)), match.group(2).strip()
    return None, filename


def load_videos(course_name: str) -> list[VideoInfo]:
    """
    Load video list from raw note directory.

    Scans for *.md files (excluding _index.md) and extracts metadata.
    """
    rdir = raw_note_dir(course_name)
    if not rdir.exists():
        raise FileNotFoundError(f"Raw note directory not found: {rdir}")

    videos: list[VideoInfo] = []

    # Try _index.md first for structured metadata
    idx = index_path(course_name)
    if idx.exists():
        # Parse _index.md for video list
        content = idx.read_text(encoding="utf-8")
        # Look for markdown list items with links
        for line in content.splitlines():
            match = re.search(r"(\d+)\.\s*\[([^\]]+)\]\(([^)]+)\)", line)
            if match:
                vidx = int(match.group(1))
                title = match.group(2)
                url = match.group(3)
                # Extract video ID from URL
                vid_match = re.search(r"[?&]v=([a-zA-Z0-9_-]+)", url)
                video_id = vid_match.group(1) if vid_match else ""
                videos.append(VideoInfo(index=vidx, title=title, video_id=video_id, url=url))

    # Fallback: scan directory for markdown files
    if not videos:
        for f in sorted(rdir.glob("*.md")):
            if f.name.startswith("_"):
                continue
            vidx, title = _parse_filename(f.name)
            if vidx is not None:
                videos.append(
                    VideoInfo(
                        index=vidx,
                        title=title,
                        video_id="",
                        url="",
                    )
                )

    videos.sort(key=lambda v: v.index)
    return videos


def count_raw_files(course_name: str) -> int:
    """Count raw markdown files for a course."""
    rdir = raw_note_dir(course_name)
    if not rdir.exists():
        return 0
    return sum(1 for f in rdir.glob("*.md") if not f.name.startswith("_"))
