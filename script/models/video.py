"""
Domain types for video/subtitle processing.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class VideoMeta:
    id: str
    title: str
    url: str
    index: int
    duration: Optional[float] = None


@dataclass
class SubtitleEntry:
    index: int
    start: str
    end: str
    text: str


@dataclass
class CourseConfig:
    name: str
    playlist_url: str
    source: str  # "youtube" | "bilibili"
    lang: str
