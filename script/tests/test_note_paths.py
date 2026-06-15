"""
Unit tests for note_paths configuration.
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from config.note_paths import (
    chapter_note_path,
    moc_path,
    anki_path,
    raw_note_dir,
    permanent_note_dir,
)


def test_raw_note_dir():
    path = raw_note_dir("Valuation")
    assert path.name == "Valuation"
    assert "input" in str(path)
    print("test_raw_note_dir: PASSED")


def test_permanent_note_dir():
    path = permanent_note_dir("Valuation")
    assert path.name == "Valuation"
    assert "output" in str(path)
    print("test_permanent_note_dir: PASSED")


def test_chapter_note_path():
    path = chapter_note_path("Valuation", 1, "估值哲学")
    assert path.name == "Ch_01_估值哲学.md"
    assert "output" in str(path)
    print("test_chapter_note_path: PASSED")


def test_chapter_note_path_special_chars():
    path = chapter_note_path("Valuation", 2, "DCF模型：基础/进阶")
    assert "Ch_02_" in path.name
    assert "/" not in path.name
    print("test_chapter_note_path_special_chars: PASSED")


def test_moc_path():
    path = moc_path("Valuation")
    assert "知识地图_MOC.md" in path.name
    print("test_moc_path: PASSED")


def test_anki_path():
    path = anki_path("Valuation", 20)
    assert "Anki_" in path.name
    assert "20张真题卡.md" in path.name
    print("test_anki_path: PASSED")


if __name__ == "__main__":
    test_raw_note_dir()
    test_permanent_note_dir()
    test_chapter_note_path()
    test_chapter_note_path_special_chars()
    test_moc_path()
    test_anki_path()
    print("\nAll note_paths tests passed.")
