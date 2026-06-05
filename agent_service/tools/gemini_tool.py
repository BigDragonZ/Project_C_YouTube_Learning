"""Gemini API wrapper with retry, jitter, and Chinese enforcement."""

import random
import time
from typing import Optional, Tuple


class GeminiTool:
    """封装 Gemini API 调用，支持内容生成、精修、重试机制。"""

    def __init__(self, api_key: Optional[str] = None, vertexai: bool = True):
        self.api_key = api_key
        self.vertexai = vertexai
        self._client = None

    def _get_client(self):
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
                raise RuntimeError("google.genai SDK not installed")
        return self._client

    def generate(
        self,
        prompt: str,
        model: str = "gemini-2.5-pro",
        max_retries: int = 3,
        sleep_jitter: Tuple[float, float] = (0, 2),
    ) -> str:
        """生成内容，内置重试和 sleep jitter。"""
        client = self._get_client()
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=model, contents=prompt
                )
                return response.text or ""
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = (2 ** attempt) + random.uniform(*sleep_jitter)
                    time.sleep(wait)
                else:
                    raise RuntimeError(f"Gemini failed after {max_retries} attempts: {e}")
        return ""

    def refine_transcript(self, raw_text: str, enforce_chinese: bool = True) -> str:
        """精修转录文本，可选强制中文输出。"""
        prompt = """这是一段音频转录文本，请进行以下优化"""
        if enforce_chinese:
            prompt += """，输出必须为中文"""
        prompt += """：
1. 补全标点符号（句号、逗号等）
2. 修正识别错误的术语、人名、地名
3. 去除口语噪音（"嗯"、"啊"、"那个"等填充词）
4. 按语义分段（每段一个主题）
5. Obsidian 格式化（Markdown 标准格式）"""
        if enforce_chinese:
            prompt += """
6. 所有内容翻译成中文，保留专业术语的英文原文（首次出现可标注英文）"""
        prompt += """

请直接输出优化后的文本，不要添加额外说明。

```
{body}
```
"""
        body = raw_text[:300000]  # Limit to ~300K chars
        return self.generate(prompt.format(body=body))

    def generate_syllabus(self, transcripts: list[str]) -> str:
        """基于转录文本生成课程大纲。"""
        combined = "\n\n".join(transcripts)[:20000]
        prompt = f"""Based on these transcripts, generate a graduate-level syllabus in Chinese with 4-8 chapters.
Each chapter: core thesis, video range, key concepts. Format: Markdown.

{combined}"""
        return self.generate(prompt)

    def generate_chapter(self, transcript: str, chapter_title: str) -> str:
        """生成单章深入分析。"""
        prompt = f"""基于以下内容，请深入分析"{chapter_title}"，输出必须为中文：
1. 核心概念与定义
2. 理论框架与逻辑推导
3. 实务应用与案例分析
4. 批判性思考

{transcript[:20000]}"""
        return self.generate(prompt)

    def generate_anki(self, chapters: list[str], count: int = 20) -> str:
        """生成 Anki 卡片。"""
        combined = "\n\n".join(chapters)[:20000]
        prompt = f"""基于以下内容，生成{count}条研究生级别Anki真题卡片，输出必须为中文：
- 每张覆盖完整推理链条
- 正面：问题/情境
- 背面：多步骤推导+公式+案例

{combined}"""
        return self.generate(prompt)
