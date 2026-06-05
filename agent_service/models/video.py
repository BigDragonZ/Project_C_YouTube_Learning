"""Domain types for video/subtitle processing."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class VideoMeta:
    """YouTube video metadata."""

    id: str
    title: str
    url: str
    index: int
    duration: Optional[float] = None


@dataclass
class SubtitleEntry:
    """SRT subtitle entry with timestamps."""

    index: int
    start: str
    end: str
    text: str


@dataclass
class CourseConfig:
    """Course pipeline configuration."""

    name: str
    playlist_url: str
    source: str  # "youtube" | "bilibili"
    lang: str
