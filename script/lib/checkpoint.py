"""
Pipeline checkpoint persistence.

Saves/resumes pipeline state as JSON so long-running jobs can recover
from interruption without manual --notebook-id --phase flags.
"""

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from config.note_paths import permanent_note_dir
from models.note import Chapter


@dataclass
class ChapterCheckpoint:
    """State for a single chapter."""

    index: int
    title: str
    completed_rounds: int = 0
    status: str = "pending"  # pending | running | completed | failed
    error: Optional[str] = None


@dataclass
class PipelineCheckpoint:
    """Full pipeline state."""

    course_name: str
    notebook_id: str
    phase: int = 1
    phase1_done: bool = False
    phase2_done: bool = False
    phase3_done: bool = False
    chapters: list[ChapterCheckpoint] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    total_rounds: int = 5
    anki_count: int = 20

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.strftime("%Y-%m-%d %H:%M:%S")
        self.updated_at = time.strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PipelineCheckpoint":
        chapters = [ChapterCheckpoint(**c) for c in data.pop("chapters", [])]
        return cls(chapters=chapters, **data)


def _checkpoint_path(course_name: str) -> Path:
    return permanent_note_dir(course_name) / ".checkpoint.json"


def save_checkpoint(cp: PipelineCheckpoint) -> Path:
    """Save checkpoint to disk."""
    path = _checkpoint_path(cp.course_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    cp.updated_at = time.strftime("%Y-%m-%d %H:%M:%S")
    path.write_text(json.dumps(cp.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_checkpoint(course_name: str) -> Optional[PipelineCheckpoint]:
    """Load checkpoint if exists."""
    path = _checkpoint_path(course_name)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return PipelineCheckpoint.from_dict(data)


def init_checkpoint(
    course_name: str,
    notebook_id: str,
    chapters: list[Chapter],
    total_rounds: int = 5,
    anki_count: int = 20,
) -> PipelineCheckpoint:
    """Create fresh checkpoint from chapter list."""
    cp = PipelineCheckpoint(
        course_name=course_name,
        notebook_id=notebook_id,
        phase=1,
        chapters=[
            ChapterCheckpoint(index=ch.index, title=ch.title)
            for ch in chapters
        ],
        total_rounds=total_rounds,
        anki_count=anki_count,
    )
    save_checkpoint(cp)
    return cp


def detect_phase_from_checkpoint(course_name: str) -> tuple[int, Optional[PipelineCheckpoint]]:
    """
    Auto-detect phase from checkpoint + filesystem.

    Returns:
        (phase, checkpoint_or_none)
    """
    cp = load_checkpoint(course_name)
    if cp:
        # Resume from checkpoint
        if cp.phase3_done:
            return 3, cp
        if cp.phase2_done:
            return 3, cp
        if cp.phase1_done:
            # Check if all chapters completed
            all_done = all(ch.status == "completed" for ch in cp.chapters)
            if all_done:
                return 3, cp
            return 2, cp
        return 1, cp

    # No checkpoint: fall back to filesystem detection
    pdir = permanent_note_dir(course_name)

    syllabus_path = pdir / f"{course_name}_课程大纲.md"
    if not syllabus_path.exists():
        return 1, None

    chapter_files = list(pdir.glob("Ch_*.md"))
    if not chapter_files:
        return 2, None

    moc_file = pdir / f"{course_name}_知识地图_MOC.md"
    if not moc_file.exists():
        return 3, None

    return 3, None
