#!/usr/bin/env python3
"""
Generate syllabus directly using Gemini API, bypassing NotebookLM.

Usage:
    uv run flow/script/generate_syllabus_direct.py <course_name>
"""

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.gemini_client import generate_content
from google.genai.types import GenerateContentConfig


def build_syllabus_prompt(course_name: str, video_files: list[Path]) -> str:
    """Build prompt for syllabus generation."""
    video_list = "\n".join(f"{i+1}. {f.stem.split('_', 1)[1] if '_' in f.stem else f.stem}" 
                          for i, f in enumerate(video_files))
    
    prompt = f"""你是一位经济学教授，正在为研究生级别的课程创建详细的大纲。

课程名称: {course_name}

以下是课程包含的视频讲座列表:
{video_list}

请基于这些讲座主题，生成一个结构化的课程大纲。要求:
1. 将相关讲座分组为章节（Chapters）
2. 每个章节包含:
   - 章节编号和标题
   - 涵盖的视频编号范围
   - 3-5个核心学习目标
   - 关键概念列表（用粗体标注）
3. 使用学术性、严谨的语言
4. 包含跨章节联系
5. 输出格式为 Markdown

请直接输出大纲内容，不要添加额外说明。"""
    
    return prompt


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate syllabus with Gemini")
    parser.add_argument("course", help="Course name")
    args = parser.parse_args()

    course_dir = Path("input") / args.course
    if not course_dir.exists():
        print(f"[ERROR] Course directory not found: {course_dir}")
        return 1

    # Get all markdown files
    video_files = sorted(course_dir.glob("*.md"))
    if not video_files:
        print(f"[ERROR] No video files found in {course_dir}")
        return 1

    print(f"[INFO] Found {len(video_files)} videos for {args.course}")
    
    # Build prompt
    prompt = build_syllabus_prompt(args.course, video_files)
    print(f"[INFO] Generating syllabus with Gemini...")
    
    # Generate
    try:
        syllabus = generate_content(
            contents=prompt,
            config=GenerateContentConfig(temperature=0.3, max_output_tokens=8192, top_p=0.95),
        )
    except Exception as e:
        print(f"[ERROR] Gemini failed: {e}")
        return 1

    # Save
    perm_dir = Path("output") / args.course
    perm_dir.mkdir(parents=True, exist_ok=True)
    
    syllabus_path = perm_dir / f"{args.course}_课程大纲.md"
    syllabus_path.write_text(syllabus, encoding="utf-8")
    
    print(f"[OK] Syllabus saved: {syllabus_path}")
    print(f"[INFO] Length: {len(syllabus)} chars")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
