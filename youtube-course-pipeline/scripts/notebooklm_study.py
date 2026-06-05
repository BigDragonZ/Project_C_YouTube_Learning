#!/usr/bin/env python3
"""
NotebookLM 后台学习脚本。
自动执行三阶段学习流程：大纲 → 章节深挖 → 知识收拢。

Usage:
    python notebooklm_study.py <course_name> <notebook_id> <phase>
    python notebooklm_study.py <course_name> <notebook_id> all

Example:
    python notebooklm_study.py "Principles_of_Microeconomics" \
        "ec06698d-f388-4b86-be1e-ee76131d59f8" all
"""

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
NOTEBOOKLM_BIN = str(PROJECT_ROOT / ".venv" / "bin" / "notebooklm")


def _run_notebooklm_ask(notebook_id: str, question: str, timeout: int = 180) -> str:
    """Run notebooklm ask and return stdout."""
    cmd = [NOTEBOOKLM_BIN, "ask", "--notebook", notebook_id, question]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        print(f"[WARN] notebooklm ask failed: {result.stderr[:200]}")
        return f"[ERROR] {result.stderr[:500]}"
    return result.stdout


def _git_commit(message: str) -> None:
    """Git add and commit."""
    subprocess.run(["git", "add", "-A"], cwd=PROJECT_ROOT, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=PROJECT_ROOT, capture_output=True)


def _save_file(course: str, filename: str, content: str) -> Path:
    """Save content to 01_Permanent/course/filename."""
    out_dir = PROJECT_ROOT / "01_Permanent" / course
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    path.write_text(content, encoding="utf-8")
    print(f"  [OK] Saved: {path}")
    return path


def parse_syllabus(course: str) -> list[dict]:
    """Parse syllabus file to extract chapter list.
    
    Handles both Arabic numerals (1, 2, 3...) and Chinese numerals (一, 二, 三...).
    This is critical because NotebookLM outputs Chinese numerals in Chinese mode.
    """
    syllabus_file = PROJECT_ROOT / "01_Permanent" / course / f"{course}_课程大纲.md"
    if not syllabus_file.exists():
        print(f"[ERROR] Syllabus not found: {syllabus_file}")
        return []

    content = syllabus_file.read_text(encoding="utf-8")
    chapters = []

    # Map Chinese numerals to Arabic
    chinese_nums = {
        '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
        '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
    }
    
    # Pattern 1: ## 第X章：标题 (Arabic or Chinese numerals)
    pattern1 = r"##\s*第\s*(\d+|[一二三四五六七八九十]+)\s*章\s*[：:]\s*(.+?)(?=\n##|\Z)"
    # Pattern 2: ## Chapter X: Title
    pattern2 = r"##\s*Chapter\s+(\d+)\s*[：:]\s*(.+?)(?=\n##|\Z)"
    
    matches = re.findall(pattern1, content, re.DOTALL)
    if not matches:
        matches = re.findall(pattern2, content, re.DOTALL)
    
    for m in matches:
        num_str = m[0]
        if num_str in chinese_nums:
            num = chinese_nums[num_str]
        else:
            num = int(num_str)
        title = m[1].strip().split("\n")[0].strip()
        # Remove markdown formatting like ** from title
        title = re.sub(r'\*\*', '', title)
        # Extract video range from content near this chapter
        range_match = re.search(r"视频范围[：:]\s*(\d+(?:-\d+)?)", content)
        video_range = range_match.group(1) if range_match else f"{num:02d}"
        chapters.append({
            "num": num,
            "title": title,
            "range": video_range,
        })

    print(f"[OK] Parsed {len(chapters)} chapters from syllabus")
    return chapters


def run_phase1(course: str, notebook_id: str) -> None:
    """Phase 1: Generate syllabus."""
    print(f"\n{'='*60}")
    print(f"PHASE 1: Syllabus Generation")
    print(f"{'='*60}")

    question = (
        "基于全部转录文本，生成研究生级别课程大纲：\n"
        "- 每章包含核心命题（Thesis）\n"
        "- 标注每章对应的原始视频编号范围\n"
        "- 体现从基础到高阶的完整逻辑链条\n"
        "- 使用中文输出\n"
        "格式：## 第X章：章节名\n- **核心命题**：...\n- **视频范围**：XX-XX\n- **关键概念**：..."
    )

    print("[INFO] Generating syllabus...")
    result = _run_notebooklm_ask(notebook_id, question)

    # Wrap with metadata
    header = f"# {course.replace('_', ' ')} — 课程大纲\n\n"
    header += "> **Metadata**\n"
    header += f"> - 课程：{course}\n"
    header += f"> - 生成时间：{time.strftime('%Y-%m-%d')}\n\n---\n\n"

    _save_file(course, f"{course}_课程大纲.md", header + result)
    _git_commit(f"chore: add {course} syllabus")
    print(f"[OK] Phase 1 complete")


def run_phase2(course: str, notebook_id: str) -> None:
    """Phase 2: Chapter-wise deep dive."""
    print(f"\n{'='*60}")
    print(f"PHASE 2: Chapter-wise Deep Dive")
    print(f"{'='*60}")

    chapters = parse_syllabus(course)
    if not chapters:
        print("[ERROR] No chapters found. Run Phase 1 first.")
        return

    for ch in chapters:
        print(f"\n[{ch['num']}] {ch['title']} (视频 {ch['range']})")

        # Round 1: Definitions + Derivations
        q1 = (
            f"基于视频{ch['range']}的内容（{ch['title']}），请深入分析：\n"
            "1) 核心概念的数学定义是什么？\n"
            "2) 关键公式的完整推导过程？\n"
            "3) 这些定义和推导的边界条件是什么？\n"
            "请用中文回答，包含LaTeX公式。"
        )
        print("  [INFO] Round 1: Definitions + Derivations...")
        r1 = _run_notebooklm_ask(notebook_id, q1)
        time.sleep(2)

        # Round 2: Critique + Cases
        q2 = (
            f"基于视频{ch['range']}的内容（{ch['title']}），继续深入分析：\n"
            "1) 该理论在什么条件下失效？边界条件是什么？\n"
            "2) 用具体历史案例说明理论与现实的偏差。\n"
            "3) 从学术角度批判主流观点的局限性。\n"
            "请用中文回答，保持学术批判深度。"
        )
        print("  [INFO] Round 2: Critique + Cases...")
        r2 = _run_notebooklm_ask(notebook_id, q2)
        time.sleep(2)

        # Round 3: Cross-chapter links (optional)
        q3 = (
            f"基于视频{ch['range']}的内容（{ch['title']}），分析：\n"
            "1) 本章内容与课程其他章节的逻辑关联？\n"
            "2) 本章理论在后续章节中的延伸应用？\n"
            "请用中文回答。"
        )
        print("  [INFO] Round 3: Cross-chapter links...")
        r3 = _run_notebooklm_ask(notebook_id, q3)

        # Combine into structured note
        note_content = f"# Ch.{ch['num']:02d} {ch['title']}\n\n"
        note_content += "> **Metadata**\n"
        note_content += f"> - 署名：DALONG ZHANG\n"
        note_content += f"> - 课程：{course}\n"
        note_content += f"> - 视频范围：{ch['range']}\n"
        note_content += f"> - 核心命题：[从大纲中提取]\n"
        note_content += f"> - 关联笔记：[[Ch_XX_...]]\n\n"
        note_content += "---\n\n"
        note_content += "## 一、核心定义\n\n" + r1 + "\n\n"
        note_content += "## 二、数理/逻辑推导\n\n[见上文]\n\n"
        note_content += "## 三、学术批判\n\n" + r2 + "\n\n"
        note_content += "## 四、跨笔记链接\n\n" + r3 + "\n\n"
        note_content += "## 五、参考来源\n\n"
        note_content += f"[{ch['range']}] 视频{ch['range']}：{ch['title']}\n"

        safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in ch['title'])
        _save_file(course, f"Ch_{ch['num']:02d}_{safe_title}.md", note_content)
        _git_commit(f"chore: add {course} Ch.{ch['num']} notes")
        print(f"  [OK] Chapter {ch['num']} complete")

    print(f"[OK] Phase 2 complete ({len(chapters)} chapters)")


def run_phase3(course: str, notebook_id: str) -> None:
    """Phase 3: Capstone synthesis."""
    print(f"\n{'='*60}")
    print(f"PHASE 3: Capstone Synthesis")
    print(f"{'='*60}")

    # Generate MOC
    print("[INFO] Generating knowledge map (MOC)...")
    q_moc = (
        "所有章节已完成。请生成知识地图：\n"
        "- 总结全课核心矛盾与底层逻辑\n"
        "- 梳理各章之间的逻辑依赖关系\n"
        "- 标注关键公式和定理的交叉引用\n"
        "- 给出后续进阶学习路径建议\n"
        "- 使用中文输出"
    )
    moc = _run_notebooklm_ask(notebook_id, q_moc)
    header = f"# {course.replace('_', ' ')} — 知识地图 (MOC)\n\n"
    header += f"> 生成时间：{time.strftime('%Y-%m-%d')}\n\n---\n\n"
    _save_file(course, f"{course}_知识地图_MOC.md", header + moc)
    time.sleep(2)

    # Generate Anki cards
    print("[INFO] Generating Anki cards...")
    q_anki = (
        "基于全部课程内容，生成15-20条研究生级别Anki真题卡片：\n"
        "- 每张覆盖完整推理链条（不是简单概念记忆）\n"
        "- 正面：问题/情境（包含具体数值或场景）\n"
        "- 背面：多步骤推导 + 关键公式 + 现实案例引用\n"
        "- 使用中文输出\n"
        "格式：---\n卡片N\n正面：...\n背面：...\n---"
    )
    anki = _run_notebooklm_ask(notebook_id, q_anki)
    header = f"# Anki — {course.replace('_', ' ')} (真题卡)\n\n"
    header += f"> 生成时间：{time.strftime('%Y-%m-%d')}\n\n---\n\n"
    _save_file(course, f"Anki_{course}_15张真题卡.md", header + anki)

    _git_commit(f"chore: add {course} MOC and Anki cards")
    print(f"[OK] Phase 3 complete")


def main() -> int:
    parser = argparse.ArgumentParser(description="NotebookLM background study script")
    parser.add_argument("course", help="Course name (e.g., Principles_of_Microeconomics)")
    parser.add_argument("notebook_id", help="NotebookLM notebook ID")
    parser.add_argument("phase", choices=["1", "2", "3", "all"], help="Phase to run")
    args = parser.parse_args()

    print(f"Course: {args.course}")
    print(f"Notebook: {args.notebook_id}")
    print(f"Phase: {args.phase}")

    if args.phase in ["1", "all"]:
        run_phase1(args.course, args.notebook_id)
    if args.phase in ["2", "all"]:
        run_phase2(args.course, args.notebook_id)
    if args.phase in ["3", "all"]:
        run_phase3(args.course, args.notebook_id)

    print(f"\n{'='*60}")
    print(f"All phases complete!")
    print(f"Output: {PROJECT_ROOT / '01_Permanent' / args.course}")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
