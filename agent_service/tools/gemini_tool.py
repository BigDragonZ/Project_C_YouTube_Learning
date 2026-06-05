"""Gemini API wrapper with retry, sleep jitter, and Chinese enforcement."""

import random
import time
from pathlib import Path
from typing import List, Optional, Tuple

from ..config import get_config


class GeminiTool:
    """Wrapper for Google Gemini API with production-grade resilience."""

    def __init__(self, api_key: Optional[str] = None, vertexai: bool = True):
        self.config = get_config()
        self.api_key = api_key or self.config.get("api", "gemini_api_key")
        self.vertexai = vertexai
        self._client = None

    def _get_client(self):
        """Lazy-load google.genai client."""
        if self._client is None:
            try:
                from google.genai import Client
                from google.genai.types import HttpOptions
                self._client = Client(
                    vertexai=self.vertexai,
                    api_key=self.api_key,
                    http_options=HttpOptions(api_version="v1"),
                )
            except ImportError:
                raise RuntimeError("google.genai not installed. Run: pip install google-genai")
        return self._client

    def generate(self, prompt: str, model: Optional[str] = None,
                 max_retries: int = 3, sleep_jitter: Tuple[float, float] = (0, 2)) -> str:
        """Generate content with retry and sleep jitter."""
        model = model or self.config.get("api", "gemini_model", default="gemini-2.5-pro")
        client = self._get_client()
        last_error = None

        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                return response.text
            except Exception as e:
                last_error = e
                err_str = str(e)
                # Check for rate limit
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    wait = (2 ** attempt) + random.uniform(*sleep_jitter)
                elif "RemoteProtocolError" in err_str:
                    wait = random.uniform(2, 5)
                else:
                    wait = random.uniform(1, 3)
                time.sleep(wait)

        raise RuntimeError(f"Gemini API failed after {max_retries} retries: {last_error}")

    def refine_transcript(self, raw_text: str, enforce_chinese: bool = True) -> str:
        """Refine transcript with content-preserving optimization."""
        prompt = """这是一段音频转录文本，请进行以下优化"""
        if enforce_chinese:
            prompt += "，输出必须为中文"
        prompt += """：
1. 补全标点符号（句号、逗号等）
2. 修正识别错误的术语、人名、地名
3. 去除口语噪音（"嗯"、"啊"、"那个"等填充词）
4. 按语义分段（每段一个主题）
5. Obsidian 格式化（Markdown 标准格式）
"""
        if enforce_chinese:
            prompt += "6. 所有内容翻译成中文，保留专业术语的英文原文（首次出现可标注英文）\n"
        prompt += "\n请直接输出优化后的文本，不要添加额外说明。\n\n```\n{body}\n```"

        body = raw_text[:300000]  # Truncate if too long
        return self.generate(prompt.format(body=body))

    def generate_syllabus(self, transcripts: List[str], course_name: str = "") -> str:
        """Generate graduate-level syllabus from transcripts."""
        combined = "\n\n".join(transcripts)[:20000]
        prompt = f"""基于以下转录文本，生成研究生级别的课程逻辑大纲，输出必须为中文：

课程名称：{course_name}

要求：
- 按内容自然划分章节（不预设章节数）
- 每章包含：核心命题、视频范围、关键概念、前置知识
- 体现从基础到高阶的完整逻辑链条
- 所有内容用中文输出，专业术语保留英文原文

转录文本：
{combined}
"""
        return self.generate(prompt)

    def generate_chapter(self, transcript: str, chapter_title: str,
                         video_range: str = "") -> str:
        """Generate deep-dive chapter notes."""
        prompt = f"""基于视频{video_range}的内容，请深入分析本章"{chapter_title}"，输出必须为中文：

1. 核心概念与定义（所有关键术语的严格定义）
2. 理论框架与逻辑推导（公式用LaTeX格式）
3. 实务应用与案例分析（真实商业场景）
4. 批判性思考（理论边界、反例、学术争议）
5. 与其他章节的关联（前置知识、后续依赖）

要求：
- 研究生级别的学术深度
- 所有内容用中文输出，专业术语保留英文原文
- 署名：DALONG ZHANG

转录文本：
{transcript[:30000]}
"""
        return self.generate(prompt)

    def generate_anki(self, chapters: List[str], course_name: str = "",
                      count: int = 20) -> str:
        """Generate Anki flashcards from chapter notes."""
        combined = "\n\n".join(chapters)[:20000]
        prompt = f"""基于《{course_name}》的全部课程内容，生成{count}条研究生级别Anki真题卡片，输出必须为中文：

要求：
- 每张覆盖完整推理链条
- 正面：问题/情境
- 背面：多步骤推导 + 公式 + 案例
- 所有内容用中文输出（专业术语保留英文）
- 署名：DALONG ZHANG

课程内容：
{combined}
"""
        return self.generate(prompt)
