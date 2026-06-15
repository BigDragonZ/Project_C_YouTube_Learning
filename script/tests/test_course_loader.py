"""
Unit tests for course_loader.
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.course_loader import _parse_filename, load_videos, count_raw_files
from models.note import VideoInfo


def test_parse_filename():
    idx, title = _parse_filename("01-Introduction to DCF.md")
    assert idx == 1
    assert title == "Introduction to DCF"
    print("test_parse_filename: PASSED")


def test_parse_filename_no_index():
    idx, title = _parse_filename("README.md")
    assert idx is None
    assert title == "README.md"
    print("test_parse_filename_no_index: PASSED")


def test_parse_filename_with_spaces():
    idx, title = _parse_filename("05  Financial Statements.md")
    assert idx == 5
    assert title == "Financial Statements"
    print("test_parse_filename_with_spaces: PASSED")


def test_load_videos_from_index(tmp_path: Path):
    # Create mock raw dir structure
    course_dir = tmp_path / "TestCourse"
    course_dir.mkdir()

    # Create _index.md
    index = course_dir / "_index.md"
    index.write_text("""
# Test Course

1. [Introduction](https://youtube.com/watch?v=abc123)
2. [Advanced Topics](https://youtube.com/watch?v=def456)
""")

    # Monkey-patch raw_note_dir and index_path for test
    import lib.course_loader as cl
    original_raw = cl.raw_note_dir
    original_idx = cl.index_path
    cl.raw_note_dir = lambda name: course_dir
    cl.index_path = lambda name: course_dir / "_index.md"

    try:
        videos = cl.load_videos("TestCourse")
        assert len(videos) == 2
        assert videos[0].index == 1
        assert videos[0].title == "Introduction"
        assert videos[0].video_id == "abc123"
        assert videos[1].index == 2
        assert videos[1].video_id == "def456"
        print("test_load_videos_from_index: PASSED")
    finally:
        cl.raw_note_dir = original_raw
        cl.index_path = original_idx


def test_load_videos_from_files(tmp_path: Path):
    course_dir = tmp_path / "TestCourse2"
    course_dir.mkdir()

    (course_dir / "01-Intro.md").write_text("test")
    (course_dir / "02-Advanced.md").write_text("test")
    (course_dir / "_index.md").write_text("no list here")

    import lib.course_loader as cl
    original_raw = cl.raw_note_dir
    original_idx = cl.index_path
    cl.raw_note_dir = lambda name: course_dir
    cl.index_path = lambda name: course_dir / "_index.md"

    try:
        videos = cl.load_videos("TestCourse2")
        assert len(videos) == 2
        assert videos[0].index == 1
        assert videos[1].index == 2
        print("test_load_videos_from_files: PASSED")
    finally:
        cl.raw_note_dir = original_raw
        cl.index_path = original_idx


if __name__ == "__main__":
    test_parse_filename()
    test_parse_filename_no_index()
    test_parse_filename_with_spaces()

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        test_load_videos_from_index(Path(td))
        test_load_videos_from_files(Path(td))

    print("\nAll course_loader tests passed.")
