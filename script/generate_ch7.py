#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.gemini_client import generate_content
from google.genai.types import GenerateContentConfig

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
course_dir = PROJECT_ROOT / "input" / "MIT_14.01_Principles_of_Microeconomics"
perm_dir = PROJECT_ROOT / "output" / "MIT_14.01_Principles_of_Microeconomics"

# Chapter 7: videos 22-26
video_files = []
for idx in [22, 23, 24, 25, 26]:
    files = list(course_dir.glob(f"{idx:02d}-*.md"))
    if files:
        video_files.append(files[0])

print(f"Found {len(video_files)} videos for chapter 7")

# Read content
contents = []
for f in video_files:
    text = f.read_text(encoding="utf-8")
    if "## 精修内容" in text:
        text = text.split("## 精修内容", 1)[1].strip()
    contents.append(f"=== {f.stem} ===\n{text[:4000]}\n")

combined = "\n".join(contents)

prompt = f"""你是一位经济学教授，正在为研究生级别的课程创建深度章节笔记。

课程名称: MIT_14.01_Principles_of_Microeconomics
章节: 第7章 - 市场失灵与政府干预
涵盖讲座: 22-26

以下是该章节涵盖的讲座内容:

{combined}

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

print("Generating chapter 7...")
chapter_content = generate_content(
    contents=prompt,
    config=GenerateContentConfig(temperature=0.3, max_output_tokens=8192, top_p=0.95),
)

# Save
chapter_path = perm_dir / "Ch_07_市场失灵与政府干预.md"
chapter_path.write_text(chapter_content, encoding="utf-8")

print(f"Saved: {chapter_path}")
print(f"Length: {len(chapter_content)} chars")
