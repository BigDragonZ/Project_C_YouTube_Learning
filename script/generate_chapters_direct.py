#!/usr/bin/env python3
"""
Generate chapter notes directly using Gemini API, bypassing NotebookLM.

Usage:
    uv run flow/script/generate_chapters_direct.py <course_name>
"""

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.gemini_client import generate_content
from google.genai.types import GenerateContentConfig


def build_chapter_prompt(course_name: str, chapter_num: int, chapter_title: str, 
                        video_range: str, video_files: list[Path]) -> tuple[str, str]:
    """Build prompt for chapter note generation."""
    
    # Read video content
    contents = []
    for f in video_files:
        text = f.read_text(encoding="utf-8")
        # Extract refined content if exists
        if "## 精修内容" in text:
            text = text.split("## 精修内容", 1)[1].strip()
        contents.append(f"=== {f.stem} ===\n{text[:5000]}\n")  # Limit to 5000 chars per video
    
    combined_content = "\n".join(contents)
    
    prompt = f"""你是一位经济学教授，正在为研究生级别的课程创建深度章节笔记。

课程名称: {course_name}
章节: 第{chapter_num}章 - {chapter_title}
涵盖讲座: {video_range}

以下是该章节涵盖的讲座内容:

{combined_content}

请基于这些内容，生成一份研究生级别的深度章节笔记。要求:

1. **概念定义**: 对每个核心概念给出严格的数学定义和经济学解释
2. **公式推导**: 使用 LaTeX 格式展示关键公式和推导过程
3. **案例分析**: 提供具体的数值例子或现实应用
4. **批判性思考**: 讨论模型的假设、局限性和扩展
5. **跨章节联系**: 指出与其他章节概念的联系
6. **研究生水平**: 内容要有学术深度，避免口语化表达

输出格式:
- 使用 Markdown 格式
- 公式用 $...$ 或 $$...$$ 包裹
- 关键术语用 **粗体** 标注
- 包含章节总结和关键要点

请直接输出笔记内容，不要添加额外说明。"""

    return prompt, chapter_title


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate chapter notes with Gemini")
    parser.add_argument("course", help="Course name")
    args = parser.parse_args()

    course_dir = Path("input") / args.course
    perm_dir = Path("output") / args.course
    
    if not course_dir.exists():
        print(f"[ERROR] Course directory not found: {course_dir}")
        return 1

    perm_dir.mkdir(parents=True, exist_ok=True)

    # Define chapters based on syllabus
    chapters = [
        (1, "消费者理论与市场需求基础", "1-4", [1, 2, 3, 4]),
        (2, "厂商理论：生产、成本与完全竞争", "5-8", [5, 6, 7, 8]),
        (3, "市场均衡、效率与福利经济学", "9-10", [9, 10]),
        (4, "不完全竞争市场", "11-14", [11, 12, 13, 14]),
        (5, "要素市场：劳动与资本", "15-16", [15, 16]),
        (6, "微观经济理论的扩展", "17-21", [17, 18, 19, 20, 21]),
        (7, "市场失灵与政府干预", "22-26", [22, 23, 24, 25, 26]),
    ]

    for ch_num, ch_title, ch_range, ch_indices in chapters:
        print(f"\n{'='*60}")
        print(f"Chapter {ch_num}: {ch_title}")
        print(f"{'='*60}")
        
        # Get video files for this chapter
        video_files = []
        for idx in ch_indices:
            files = list(course_dir.glob(f"{idx:02d}-*.md"))
            if files:
                video_files.append(files[0])
        
        if not video_files:
            print(f"[WARN] No video files found for chapter {ch_num}")
            continue
        
        # Build prompt
        prompt, title = build_chapter_prompt(args.course, ch_num, ch_title, ch_range, video_files)
        
        print(f"[INFO] Generating chapter notes with Gemini...")
        print(f"[INFO] Using {len(video_files)} video files")
        
        # Generate
        try:
            chapter_content = generate_content(
                contents=prompt,
                config=GenerateContentConfig(temperature=0.3, max_output_tokens=8192, top_p=0.95),
            )
        except Exception as e:
            print(f"[ERROR] Gemini failed: {e}")
            continue
        
        # Save
        safe_title = "".join(c if c.isalnum() or c in (' ', '_') else '_' for c in ch_title)
        chapter_path = perm_dir / f"Ch_{ch_num:02d}_{safe_title}.md"
        chapter_path.write_text(chapter_content, encoding="utf-8")
        
        print(f"[OK] Chapter saved: {chapter_path.name}")
        print(f"[INFO] Length: {len(chapter_content)} chars")

    print(f"\n{'='*60}")
    print(f"All chapters complete")
    print(f"Output: {perm_dir}")
    print(f"{'='*60}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
