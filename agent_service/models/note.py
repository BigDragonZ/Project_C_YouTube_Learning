"""Domain models for note generation pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prompt_registry import PromptEntry


@dataclass
class VideoInfo:
    """A video in the course."""

    index: int
    title: str
    video_id: str
    url: str


@dataclass
class Chapter:
    """A chapter in the course syllabus."""

    index: int
    title: str
    thesis: str
    video_range: str  # e.g. "01-05"
    prerequisites: list[str]  # [[Ch_XX_...]] links
    summary: str


@dataclass
class ChapterNote:
    """Generated note for a chapter."""

    chapter: Chapter
    content: str
    source_file: Path
    round_count: int  # number of pressure-test rounds applied


@dataclass
class CourseContext:
    """Context for the entire course."""

    course_name: str
    notebook_id: str
    raw_dir: Path
    permanent_dir: Path
    videos: list[VideoInfo]
    chapters: list[Chapter]


@dataclass
class PressureTestRound:
    """A single pressure-test round configuration."""

    name: str
    prompt_template: "PromptEntry"  # Forward ref
    focus: str  # "definition", "derivation", "case", "critique", "cross"
