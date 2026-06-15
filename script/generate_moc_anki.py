#!/usr/bin/env python3
"""
Generate MOC and Anki cards directly using Gemini API.

Usage:
    uv run flow/script/generate_moc_anki.py <course_name>
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.gemini_client import generate_content
from google.genai.types import GenerateContentConfig


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate MOC and Anki cards")
    parser.add_argument("course", help="Course name")
    args = parser.parse_args()

    perm_dir = Path("output") / args.course
    if not perm_dir.exists():
        print(f"[ERROR] Directory not found: {perm_dir}")
        return 1

    # Read all chapter files
    chapter_files = sorted(perm_dir.glob("Ch_*.md"))
    if not chapter_files:
        print(f"[ERROR] No chapter files found")
        return 1

    # Build combined content
    chapters_summary = []
    for f in chapter_files:
        content = f.read_text(encoding="utf-8")
        # Extract first 2000 chars as summary
        summary = content[:2000].replace("#", "##")
        chapters_summary.append(f"=== {f.stem} ===\n{summary}\n")

    combined = "\n".join(chapters_summary)

    # Generate MOC
    print("[INFO] Generating MOC...")
    moc_prompt = f"""基于以下课程章节内容，生成一份知识地图（MOC - Map of Content）。

课程: {args.course}

章节内容摘要:
{combined}

请生成一份结构化的知识地图，要求:
1. 展示所有核心概念及其相互关系
2. 使用思维导图式的层级结构
3. 标注跨章节联系
4. 包含关键公式和定义的快速参考
5. 使用 Markdown 格式，适合 Obsidian 使用

请直接输出 MOC 内容。"""

    moc_content = generate_content(
        contents=moc_prompt,
        config=GenerateContentConfig(temperature=0.3, max_output_tokens=8192),
    )

    moc_path = perm_dir / f"{args.course}_知识地图_MOC.md"
    moc_path.write_text(moc_content, encoding="utf-8")
    print(f"[OK] MOC saved: {moc_path.name}")

    # Generate Anki cards
    print("[INFO] Generating Anki cards...")
    anki_prompt = f"""基于以下课程章节内容，生成 Anki 记忆卡片。

课程: {args.course}

章节内容摘要:
{combined}

请生成 20 张 Anki 卡片，要求:
1. 卡片类型为"基础"（正面问题，背面答案）
2. 问题要考察核心概念的理解，不是简单的事实记忆
3. 答案要详细，包含定义、公式和解释
4. 使用 Markdown 格式
5. 难度适中，适合研究生水平

格式示例:
---
Q: 什么是边际替代率 (MRS)？
A: 边际替代率是指在保持效用水平不变的情况下，消费者愿意用一种商品替代另一种商品的比率。数学上表示为:
$$MRS_{{xy}} = -\\frac{{dy}}{{dx}} = \\frac{{MU_x}}{{MU_y}}$$
其中 $MU_x$ 和 $MU_y$ 分别是商品 x 和 y 的边际效用。
---

请直接输出 20 张卡片。"""

    anki_content = generate_content(
        contents=anki_prompt,
        config=GenerateContentConfig(temperature=0.3, max_output_tokens=8192),
    )

    anki_path = perm_dir / f"Anki_{args.course}_20张真题卡.md"
    anki_path.write_text(anki_content, encoding="utf-8")
    print(f"[OK] Anki cards saved: {anki_path.name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
