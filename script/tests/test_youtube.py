"""Tests for lib/youtube.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.youtube import parse_srt, to_markdown


def test_parse_srt_basic():
    srt = """1
00:00:01,000 --> 00:00:03,000
Hello world

2
00:00:04,000 --> 00:00:05,000
Second line
"""
    entries = parse_srt(srt)
    assert len(entries) == 2
    assert entries[0].index == 1
    assert entries[0].start == "00:00:01,000"
    assert entries[0].text == "Hello world"


def test_parse_srt_strips_html():
    srt = """1
00:00:01,000 --> 00:00:02,000
<b>Bold</b> text
"""
    entries = parse_srt(srt)
    assert entries[0].text == "Bold text"


def test_parse_srt_strips_music():
    srt = """1
00:00:01,000 --> 00:00:02,000
[Music] playing ♪
"""
    entries = parse_srt(srt)
    assert entries[0].text == "playing"


def test_parse_srt_skips_empty():
    srt = """1
00:00:01,000 --> 00:00:02,000

2
00:00:03,000 --> 00:00:04,000
Real text
"""
    entries = parse_srt(srt)
    assert len(entries) == 1
    assert entries[0].text == "Real text"


def test_to_markdown_metadata():
    from lib.youtube import SubtitleEntry
    entries = [SubtitleEntry(1, "00:00:01,000", "00:00:02,000", "Hello")]
    md = to_markdown(entries, {
        "title": "Test Video",
        "url": "https://example.com",
        "course": "Test_Course",
        "index": 5,
    })
    assert "# Test Video" in md
    assert "**序号**: 5" in md
    assert "**课程**: Test_Course" in md
    assert "https://example.com" in md
    assert "**条目数**: 1" in md


def test_to_markdown_entries():
    from lib.youtube import SubtitleEntry
    entries = [
        SubtitleEntry(1, "00:00:01,000", "00:00:02,000", "First"),
        SubtitleEntry(2, "00:00:03,000", "00:00:04,000", "Second"),
    ]
    md = to_markdown(entries, {
        "title": "Test",
        "url": "https://example.com",
        "course": "Course",
        "index": 1,
    })
    assert "**[00:00:01,000 - 00:00:02,000]** First" in md
    assert "**[00:00:03,000 - 00:00:04,000]** Second" in md


if __name__ == "__main__":
    test_parse_srt_basic()
    test_parse_srt_strips_html()
    test_parse_srt_strips_music()
    test_parse_srt_skips_empty()
    test_to_markdown_metadata()
    test_to_markdown_entries()
    print("youtube tests: 6 passed")
