"""
Markdown content refinement via unified Gemini client.

Backend chain:
  1. GCP Vertex AI (gemini-3.1-pro-preview) - primary
  2. Gemini Standard API (gemini-2.5-flash-lite) - fallback

Tasks:
  1. Text cleaning & restructuring
  2. Terminology & math correction (LaTeX)
  3. Key concept bolding
"""

from google.genai.types import GenerateContentConfig

from lib.gemini_client import generate_content

REFINE_PROMPT = """这是一段音频转录文本，请进行以下优化，输出必须为中文：

1. 补全标点符号（句号、逗号等）
2. 修正识别错误的术语、人名、地名
3. 去除口语噪音（"嗯"、"啊"、"那个"等填充词）
4. 按语义分段（每段一个主题）
5. Obsidian 格式化（Markdown 标准格式）
6. 所有内容翻译成中文，保留专业术语的英文原文（如首次出现可标注英文）

请直接输出优化后的中文文本，不要添加额外说明。"""


def refine_markdown(content: str) -> str:
    """
    Refine markdown content using Gemini.
    Fault-tolerant: Vertex AI -> Gemini fallback.
    """
    print(f"[INFO] Refining content ({len(content)} chars)...")

    text = generate_content(
        contents=REFINE_PROMPT + content,
        config=GenerateContentConfig(temperature=0.2, max_output_tokens=8192, top_p=0.95),
    )

    if not text:
        raise RuntimeError("Empty response from Gemini during refinement")

    print(f"[INFO] Refined to {len(text)} chars")
    return text
