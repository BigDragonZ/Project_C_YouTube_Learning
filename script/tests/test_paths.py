"""Tests for config/paths.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.paths import PATHS, BINARIES, course_dir, build_filename, PROJECT_ROOT


def test_project_root():
    assert "all-in-one" in str(PROJECT_ROOT)


def test_paths_defined():
    assert isinstance(PATHS["project_root"], Path)
    assert isinstance(PATHS["input_dir"], Path)


def test_binaries_ytdlp():
    assert "yt-dlp" in BINARIES["yt_dlp"]


def test_course_dir():
    d = course_dir("Test_Course")
    assert "input/Test_Course" in str(d)


def test_build_filename():
    assert build_filename(3, "Hello: World?", "md") == "03-Hello_ World_.md"
    assert build_filename(1, "Title", "mp3") == "01-Title.mp3"
    assert build_filename(12, "Title", "md") == "12-Title.md"


if __name__ == "__main__":
    test_project_root()
    test_paths_defined()
    test_binaries_ytdlp()
    test_course_dir()
    test_build_filename()
    print("paths tests: 5 passed")
