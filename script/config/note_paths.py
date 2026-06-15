"""
Path configuration for note generation pipeline.
"""

from pathlib import Path

# Project root: three levels up from this file (inside input/script/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

Y2N_ROOT = PROJECT_ROOT

PATHS = {
    "project_root": PROJECT_ROOT,
    "y2n_root": Y2N_ROOT,
    "script_dir": Y2N_ROOT / "script",
    "input_dir": Y2N_ROOT / "input",
    "output_dir": Y2N_ROOT / "output",
    "venv_bin": PROJECT_ROOT.parent / ".venv" / "bin",
}


def raw_note_dir(course_name: str) -> Path:
    """Directory for refined transcription markdown files."""
    return PATHS["input_dir"] / course_name


def permanent_note_dir(course_name: str) -> Path:
    """Directory for NotebookLM-generated knowledge output."""
    return PATHS["output_dir"] / course_name


def chapter_note_path(course_name: str, chapter_index: int, chapter_title: str) -> Path:
    """Path for a chapter note file."""
    safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in chapter_title).strip()
    filename = f"Ch_{chapter_index:02d}_{safe_title}.md"
    return permanent_note_dir(course_name) / filename


def moc_path(course_name: str) -> Path:
    """Path for the Map of Contents (MOC) file."""
    safe_course = "".join(c if c.isalnum() or c in " _-" else "_" for c in course_name).strip()
    return permanent_note_dir(course_name) / f"{safe_course}_知识地图_MOC.md"


def anki_path(course_name: str, card_count: int) -> Path:
    """Path for Anki flashcard file."""
    safe_course = "".join(c if c.isalnum() or c in " _-" else "_" for c in course_name).strip()
    return permanent_note_dir(course_name) / f"Anki_{safe_course}_{card_count}张真题卡.md"


def index_path(course_name: str) -> Path:
    """Path for the index file listing all videos."""
    return raw_note_dir(course_name) / "_index.md"
