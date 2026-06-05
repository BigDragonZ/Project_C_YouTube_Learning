"""Input validation and sanitization for Agent Service."""

import re
from urllib.parse import urlparse


def validate_playlist_url(url: str) -> bool:
    """Validate YouTube playlist or video URL."""
    if not url:
        return False
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if domain not in ("youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com"):
        return False
    # Check for playlist or video indicators
    path = parsed.path.lower()
    query = parsed.query.lower()
    return (
        "playlist" in path
        or "list=" in query
        or "/watch" in path
        or "/video" in path
        or len(path) > 1 and path.count("/") <= 2  # youtu.be/xxx
    )


def sanitize_course_name(name: str) -> str:
    """Sanitize course name for filesystem use.

    Allows: letters, digits, underscore, hyphen, Chinese characters, spaces.
    Replaces everything else with underscore.
    """
    # Replace invalid chars with underscore
    sanitized = re.sub(r"[^\w\s\-一-鿿]", "_", name)
    # Collapse multiple underscores/spaces
    sanitized = re.sub(r"[_ ]+", "_", sanitized)
    # Trim underscores from ends
    return sanitized.strip("_").strip()


def check_idempotency(course: str, task_type: str, project_root) -> dict:
    """Check existing files to determine what work is already done.

    Returns dict with:
        - existing_files: list of already processed files
        - missing_count: estimated number of missing items
        - is_complete: whether the task appears fully done
    """
    from pathlib import Path

    result = {
        "existing_files": [],
        "missing_count": 0,
        "is_complete": False,
    }

    if task_type == "transcribe":
        input_dir = Path(project_root) / "input" / course
        if input_dir.exists():
            result["existing_files"] = sorted(
                f.name for f in input_dir.glob("*.md")
                if "精修内容" in f.read_text(encoding="utf-8")[:5000]
            )
    elif task_type == "study":
        output_dir = Path(project_root) / "output" / course
        if output_dir.exists():
            result["existing_files"] = sorted(
                f.name for f in output_dir.glob("Ch_*.md")
            )
            # Check for syllabus
            syllabus = list(output_dir.glob("*_课程大纲.md"))
            if syllabus:
                result["existing_files"].append(syllabus[0].name)
    elif task_type == "anki":
        anki_dir = Path(project_root) / "anki" / course
        if anki_dir.exists():
            result["existing_files"] = sorted(
                f.name for f in anki_dir.glob("Anki_*.md")
            )

    return result
