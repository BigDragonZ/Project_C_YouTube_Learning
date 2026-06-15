"""Quality gate for transcribe and study outputs.

Enforces quality thresholds defined in config.json.
Computes quality_score based on retention, chinese ratio, completeness.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from config import get_config


@dataclass
class QualityResult:
    passed: bool
    score: int  # 0-100
    checks: Dict[str, dict]
    retry_recommended: bool
    retry_prompt_hint: Optional[str] = None


class QualityGate:
    """Quality gate for pipeline outputs."""

    def __init__(self):
        self.config = get_config()

    def _read_text(self, path: Path) -> str:
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except (IOError, UnicodeDecodeError):
            return ""

    def _chinese_ratio(self, text: str) -> float:
        if not text:
            return 0.0
        chinese_chars = len(re.findall(r'[一-鿿]', text))
        return chinese_chars / len(text)

    def _english_paragraph_ratio(self, text: str) -> float:
        """Detect English-dominant paragraphs."""
        if not text:
            return 0.0
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            return 0.0
        english_count = 0
        for p in paragraphs:
            ascii_chars = len(re.findall(r'[a-zA-Z]', p))
            total_chars = len(p)
            if total_chars > 20 and ascii_chars / total_chars > 0.5:
                english_count += 1
        return english_count / len(paragraphs)

    def _file_size_kb(self, path: Path) -> float:
        if not path.exists():
            return 0.0
        return path.stat().st_size / 1024

    def _line_count(self, path: Path) -> int:
        if path.is_dir():
            total = 0
            for f in path.glob("*.md"):
                text = self._read_text(f)
                total += len([l for l in text.split("\n") if l.strip()])
            return total
        text = self._read_text(path)
        return len([l for l in text.split("\n") if l.strip()])

    def check_transcribe(self, course_dir: Path, raw_text: str = "",
                         refined_text: str = "") -> QualityResult:
        """Check transcribe output quality.

        Args:
            course_dir: Directory containing refined .md files
            raw_text: Original raw text (for retention ratio)
            refined_text: Refined text (for retention ratio)
        """
        checks = {}
        passed = True
        retry_hint = None

        # Check 1: retention ratio
        retention = 1.0
        if raw_text and refined_text:
            retention = len(refined_text) / len(raw_text)
        min_retention = self.config.get("quality", "min_retention_ratio", default=0.70)
        checks["retention_ratio"] = {
            "value": round(retention, 2),
            "threshold": min_retention,
            "passed": retention >= min_retention,
        }
        if not checks["retention_ratio"]["passed"]:
            passed = False
            retry_hint = "retry with stricter prompt"

        # Check 2: chinese ratio
        min_chinese = self.config.get("quality", "min_chinese_ratio", default=0.80)
        chinese = self._chinese_ratio(refined_text)
        checks["chinese_ratio"] = {
            "value": round(chinese, 2),
            "threshold": min_chinese,
            "passed": chinese >= min_chinese,
        }
        if not checks["chinese_ratio"]["passed"]:
            passed = False
            retry_hint = "输出必须为中文"

        # Check 3: english paragraph ratio
        english_ratio = self._english_paragraph_ratio(refined_text)
        checks["english_paragraph_ratio"] = {
            "value": round(english_ratio, 2),
            "threshold": 0.20,
            "passed": english_ratio <= 0.20,
        }
        if not checks["english_paragraph_ratio"]["passed"]:
            passed = False
            retry_hint = "retry with explicit Chinese enforcement"

        # Check 4: contains "精修内容" marker (look in full refined file, not just body)
        full_refined = refined_text
        if course_dir and course_dir.exists():
            # Fallback: check the first .md file if available
            md_files = sorted(course_dir.glob("*.md"))
            if md_files:
                full_refined = self._read_text(md_files[0])
        has_marker = "精修内容" in full_refined or "## 精修" in full_refined
        checks["refined_marker"] = {
            "value": has_marker,
            "passed": has_marker,
        }
        if not has_marker:
            passed = False

        # Check 5: non-empty
        lines = self._line_count(course_dir) if course_dir.exists() else 0
        checks["non_empty"] = {
            "value": lines,
            "threshold": 10,
            "passed": lines >= 10,
        }
        if not checks["non_empty"]["passed"]:
            passed = False

        # Quality score
        score = int(
            retention * 30 +
            min(chinese / min_chinese, 1.0) * 20 +
            (1 - english_ratio) * 20 +
            (min(lines, 100) / 100) * 10 +
            (20 if has_marker else 0)
        )
        score = min(100, max(0, score))

        return QualityResult(
            passed=passed,
            score=score,
            checks=checks,
            retry_recommended=not passed,
            retry_prompt_hint=retry_hint,
        )

    def check_study(self, output_dir: Path, syllabus_path: Optional[Path] = None,
                    moc_path: Optional[Path] = None) -> QualityResult:
        """Check study output quality."""
        checks = {}
        passed = True

        # Check 1: chapter files size
        min_kb = self.config.get("quality", "min_chapter_size_kb", default=10)
        chapter_files = sorted(output_dir.glob("Ch_*.md")) if output_dir.exists() else []
        small_chapters = [f for f in chapter_files if self._file_size_kb(f) < min_kb]
        checks["chapter_size"] = {
            "value": f"{len(chapter_files)} chapters, {len(small_chapters)} under {min_kb}KB",
            "passed": len(small_chapters) == 0 and len(chapter_files) >= 3,
        }
        if not checks["chapter_size"]["passed"]:
            passed = False

        # Check 2: syllabus parsed chapters
        chapter_count = len(chapter_files)
        checks["syllabus_chapters"] = {
            "value": chapter_count,
            "threshold": 3,
            "passed": chapter_count >= 3,
        }
        if not checks["syllabus_chapters"]["passed"]:
            passed = False

        # Check 3: MOC exists
        moc_exists = moc_path.exists() if moc_path else False
        if not moc_exists and output_dir.exists():
            moc_candidates = list(output_dir.glob("*_知识地图_MOC.md")) + list(output_dir.glob("*_MOC.md"))
            moc_exists = len(moc_candidates) > 0
        checks["moc_exists"] = {
            "value": moc_exists,
            "passed": moc_exists,
        }

        # Check 4: Anki exists
        anki_exists = False
        if output_dir.exists():
            anki_candidates = list(output_dir.glob("Anki_*.md"))
            anki_exists = len(anki_candidates) > 0
        checks["anki_exists"] = {
            "value": anki_exists,
            "passed": anki_exists,
        }

        # Quality score
        if chapter_count == 0:
            score = 0
        else:
            completeness = min(chapter_count / 8, 1.0)
            score = int(
                completeness * 30 +
                (20 if moc_exists else 0) +
                (20 if anki_exists else 0) +
                (30 if len(small_chapters) == 0 else max(0, 30 - len(small_chapters) * 5))
            )
        score = min(100, max(0, score))

        return QualityResult(
            passed=passed,
            score=score,
            checks=checks,
            retry_recommended=not passed,
        )

    def check_course_transcribe(self, course_name: str,
                                 project_root: Optional[Path] = None) -> QualityResult:
        """Check all transcribe outputs for a course."""
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent
        course_dir = project_root / "input" / course_name
        return self.check_transcribe(course_dir)

    def check_course_study(self, course_name: str,
                            project_root: Optional[Path] = None) -> QualityResult:
        """Check all study outputs for a course."""
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent
        output_dir = project_root / "output" / course_name
        syllabus = output_dir / f"{course_name}_课程大纲.md"
        moc = output_dir / f"{course_name}_知识地图_MOC.md"
        return self.check_study(output_dir, syllabus, moc)
