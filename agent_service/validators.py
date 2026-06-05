"""Input validation and sanitization for Agent Service."""

import re
from pathlib import Path

VALID_YOUTUBE_DOMAINS = (
    "youtube.com/playlist",
    "youtu.be/",
    "youtube.com/watch",
)


def validate_playlist_url(url: str) -> bool:
    """Validate YouTube playlist URL format."""
    if not url:
        return True  # Empty URL allowed (for study/anki tasks)
    return url.startswith(("https://", "http://")) and any(
        d in url for d in VALID_YOUTUBE_DOMAINS
    )


def sanitize_course_name(name: str) -> str:
    """Sanitize course name for filesystem safety.

    Allows: letters, digits, underscores, hyphens, Chinese characters, spaces.
    Replaces everything else with underscore.
    """
    # Replace invalid chars with underscore
    sanitized = re.sub(r'[^\w\s\-一-鿿]', '_', name)
    # Collapse multiple underscores/spaces
    sanitized = re.sub(r'[_\s]+', '_', sanitized)
    return sanitized.strip('_')


def check_idempotency(course_name: str, task_type: str, project_root: Path) -> dict:
    """Check which outputs already exist for idempotency.

    Returns dict with exists bool and list of existing files.
    """
    result = {"exists": False, "files": []}

    if task_type == "transcribe":
        target_dir = project_root / "input" / course_name
        if target_dir.exists():
            md_files = list(target_dir.glob("*.md"))
            if md_files:
                result["exists"] = True
                result["files"] = [f.name for f in md_files]

    elif task_type == "study":
        target_dir = project_root / "output" / course_name
        if target_dir.exists():
            syllabus = list(target_dir.glob("*_课程大纲.md"))
            chapters = list(target_dir.glob("Ch_*.md"))
            if syllabus or chapters:
                result["exists"] = True
                result["files"] = [f.name for f in (syllabus + chapters)]

    elif task_type == "anki":
        target_dir = project_root / "anki" / course_name
        if target_dir.exists():
            anki_files = list(target_dir.glob("Anki_*.md"))
            if anki_files:
                result["exists"] = True
                result["files"] = [f.name for f in anki_files]

    return result
