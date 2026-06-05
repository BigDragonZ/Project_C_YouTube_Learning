"""Tests for quality_gate.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quality_gate import QualityGate


def test_chinese_ratio():
    qg = QualityGate()
    assert qg._chinese_ratio("这是一段中文文本") > 0.5
    assert qg._chinese_ratio("This is English") == 0.0
    assert qg._chinese_ratio("") == 0.0


def test_english_paragraph_ratio():
    qg = QualityGate()
    text = "This is an English paragraph.\n\n这是中文段落。"
    ratio = qg._english_paragraph_ratio(text)
    assert 0 < ratio < 1.0


def test_check_transcribe_pass():
    qg = QualityGate()
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        course_dir = Path(td)
        # Create a test file so non_empty check passes
        test_file = course_dir / "01-test.md"
        test_file.write_text("line1\n" * 15, encoding="utf-8")
        raw = "这是一段很长的音频转录文本，包含很多内容。" * 50
        refined = "## 精修内容\n\n" + raw  # 100% retention with marker
        result = qg.check_transcribe(course_dir, raw, refined)
        assert result.passed is True
        assert result.score > 70


def test_check_transcribe_fail_retention():
    qg = QualityGate()
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        course_dir = Path(td)
        raw = "x" * 1000
        refined = "x" * 10  # Very low retention
        result = qg.check_transcribe(course_dir, raw, refined)
        assert result.passed is False
        assert result.retry_recommended is True


def test_check_study_empty():
    qg = QualityGate()
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        output_dir = Path(td)
        result = qg.check_study(output_dir)
        assert result.passed is False
        assert result.score == 0


if __name__ == "__main__":
    test_chinese_ratio()
    test_english_paragraph_ratio()
    test_check_transcribe_pass()
    test_check_transcribe_fail_retention()
    test_check_study_empty()
    print("test_quality_gate.py: ALL PASSED")
