"""Tests for validators.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from validators import validate_playlist_url, sanitize_course_name, check_idempotency


def test_validate_playlist_url():
    assert validate_playlist_url("https://www.youtube.com/playlist?list=ABC") is True
    assert validate_playlist_url("https://youtube.com/playlist?list=ABC") is True
    assert validate_playlist_url("https://youtu.be/xyz") is True
    assert validate_playlist_url("https://youtube.com/watch?v=xyz") is True
    assert validate_playlist_url("") is True  # empty allowed
    assert validate_playlist_url("invalid") is False


def test_sanitize_course_name():
    assert sanitize_course_name("Hello World") == "Hello_World"
    assert sanitize_course_name("Test@#$%Name") == "Test_Name"
    assert sanitize_course_name("中文课程") == "中文课程"
    assert sanitize_course_name("  spaced  ") == "spaced"


def test_check_idempotency():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        # Test transcribe
        result = check_idempotency("Test", "transcribe", root)
        assert result["exists"] is False
        # Create file
        (root / "input" / "Test").mkdir(parents=True)
        (root / "input" / "Test" / "01-test.md").write_text("x")
        result = check_idempotency("Test", "transcribe", root)
        assert result["exists"] is True


if __name__ == "__main__":
    test_validate_playlist_url()
    test_sanitize_course_name()
    test_check_idempotency()
    print("test_validators.py: ALL PASSED")
