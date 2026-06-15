"""
Unit tests for syllabus_parser.
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.syllabus_parser import parse_syllabus, save_syllabus, load_syllabus
from models.note import Chapter


SAMPLE_SYLLABUS = """
## 第1章：估值哲学与DCF基础

- **核心命题**：企业价值等于未来自由现金流的折现值
- **视频范围**：01-05
- **前置知识**：无
- **本章概要**：本章从价值投资的哲学基础出发，系统阐述DCF模型的理论根基、关键假设及其在实践中的局限性。

---

## 第2章：财务预测与三张报表

- **核心命题**：准确的财务预测是估值的基石，三张报表的内在一致性决定模型质量
- **视频范围**：06-12
- **前置知识**：[[Ch_01_估值哲学与DCF基础]]
- **本章概要**：深入讲解收入预测、成本结构分析和三张报表联动建模的方法论。

---

## 第3章：风险与折现率

- **核心命题**：CAPM模型在实践中存在系统性偏差，需结合行业特征调整
- **视频范围**：13-18
- **前置知识**：[[Ch_01_估值哲学与DCF基础]] | [[Ch_02_财务预测与三张报表]]
- **本章概要**：探讨WACC计算、Beta估计、市场风险溢价选择等核心问题。
"""


def test_parse_syllabus():
    chapters = parse_syllabus(SAMPLE_SYLLABUS)

    assert len(chapters) == 3

    ch1 = chapters[0]
    assert ch1.index == 1
    assert ch1.title == "估值哲学与DCF基础"
    assert ch1.thesis == "企业价值等于未来自由现金流的折现值"
    assert ch1.video_range == "01-05"
    assert ch1.prerequisites == []

    ch2 = chapters[1]
    assert ch2.index == 2
    assert ch2.prerequisites == ["Ch_01_估值哲学与DCF基础"]

    ch3 = chapters[2]
    assert ch3.index == 3
    assert ch3.prerequisites == ["Ch_01_估值哲学与DCF基础", "Ch_02_财务预测与三张报表"]

    print("test_parse_syllabus: PASSED")


def test_save_and_load_syllabus(tmp_path: Path):
    chapters = parse_syllabus(SAMPLE_SYLLABUS)
    save_path = save_syllabus(SAMPLE_SYLLABUS, "TestCourse", tmp_path)

    assert save_path.exists()
    loaded = load_syllabus(save_path)

    assert len(loaded) == 3
    assert loaded[0].title == "估值哲学与DCF基础"

    print("test_save_and_load_syllabus: PASSED")


def test_parse_empty():
    chapters = parse_syllabus("")
    assert chapters == []
    print("test_parse_empty: PASSED")


def test_parse_no_chapters():
    chapters = parse_syllabus("# Some preamble\n\nNo chapters here.")
    assert chapters == []
    print("test_parse_no_chapters: PASSED")


if __name__ == "__main__":
    test_parse_syllabus()
    test_parse_empty()
    test_parse_no_chapters()

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        test_save_and_load_syllabus(Path(td))

    print("\nAll syllabus_parser tests passed.")
