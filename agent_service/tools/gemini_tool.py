"""Gemini API wrapper with retry, jitter, backend failover, and Chinese enforcement."""

import random
import time
from typing import Optional, Tuple


class GeminiTool:
    """封装 Gemini API 调用，支持内容生成、精修、重试机制、后端故障转移。"""

    def __init__(self, api_key: Optional[str] = None, vertexai: Optional[bool] = None):
        if api_key is None:
            from config import get_config
            cfg = get_config()
            api_key = cfg.get("api", "gemini_api_key", default=None)
        if vertexai is None:
            from config import get_config
            cfg = get_config()
            vertexai = cfg.get("api", "vertexai", default=True)
        self.api_key = api_key
        self.vertexai = vertexai
        self._client = None
        self._fallback_client = None

    def _get_primary_client(self):
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

    def _get_fallback_client(self):
        if self._fallback_client is None:
            try:
                from google.genai import Client
                fallback_key = self._get_fallback_key()
                if not fallback_key:
                    return None
                self._fallback_client = Client(api_key=fallback_key)
            except ImportError:
                return None
        return self._fallback_client

    def _get_fallback_key(self) -> Optional[str]:
        import os
        return os.environ.get("GEMINI_API_KEY")

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_retries: int = 3,
        sleep_jitter: Tuple[float, float] = (0, 2),
    ) -> str:
        """生成内容，内置重试、sleep jitter 和后端故障转移。"""
        from config import get_config
        cfg = get_config()
        model = model or cfg.get("api", "gemini_model", default="gemini-2.5-pro")
        fallback_model = cfg.get("api", "gemini_fallback_model", default="gemini-2.5-flash-lite")

        # Try primary backend
        client = self._get_primary_client()
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
                    print(f"[WARN] Primary backend failed: {e}")

        # Fallback to standard Gemini API
        fallback = self._get_fallback_client()
        if fallback:
            print(f"[INFO] Falling back to standard Gemini API ({fallback_model})...")
            for attempt in range(max_retries):
                try:
                    response = fallback.models.generate_content(
                        model=fallback_model, contents=prompt
                    )
                    return response.text or ""
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait = (2 ** attempt) + random.uniform(*sleep_jitter)
                        time.sleep(wait)
                    else:
                        print(f"[WARN] Fallback backend failed: {e}")

        raise RuntimeError("All Gemini backends failed")

    def generate_with_audio(
        self,
        prompt: str,
        audio_path: str,
        model: Optional[str] = None,
    ) -> str:
        """使用音频文件生成内容（转录），输出强制中文。"""
        from google.genai.types import Part

        with open(audio_path, "rb") as f:
            audio_data = f.read()

        contents = [
            prompt,
            Part.from_bytes(data=audio_data, mime_type="audio/mpeg"),
        ]

        from config import get_config
        cfg = get_config()
        model = model or cfg.get("api", "gemini_model", default="gemini-2.5-pro")

        client = self._get_primary_client()
        try:
            response = client.models.generate_content(
                model=model, contents=contents
            )
            return response.text or ""
        except Exception as e:
            fallback = self._get_fallback_client()
            if fallback:
                fallback_model = cfg.get("api", "gemini_fallback_model", default="gemini-2.5-flash-lite")
                response = fallback.models.generate_content(
                    model=fallback_model, contents=contents
                )
                return response.text or ""
            raise RuntimeError(f"Audio generation failed: {e}")

    def transcribe_audio(self, audio_path: str) -> str:
        """Whisper-style audio transcription via Gemini API. Output forced to Chinese."""
        prompt = (
            "请仔细转写这段音频的内容。要求：\n"
            "1. 保持原文语言，添加标点\n"
            "2. 按语义分段\n"
            "3. 去除语气词和广告词\n"
            "4. 输出必须为中文（如果是英文内容请翻译成中文，专业术语保留英文原文）\n"
            "5. 直接输出纯文本，不要添加额外说明"
        )
        return self.generate_with_audio(prompt=prompt, audio_path=audio_path)

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

规则：
- 不要提炼总结，不要省略原文内容
- 保持原文的完整信息量
- 仅做格式化和语言转换优化

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
        prompt = f"""基于以下转录文本，生成研究生级别课程大纲，输出必须为中文：

要求：
- 每章包含核心命题（Thesis）
- 标注每章对应的原始视频编号范围
- 体现从基础到高阶的完整逻辑链条
- 不预设章节数量，由内容自然决定
- 所有内容用中文输出，专业术语保留英文原文

格式：
## 第N章：章节名
- **核心命题**：...
- **视频范围**：XX-XX
- **关键概念**：...

{combined}"""
        return self.generate(prompt)

    def generate_chapter(self, transcript: str, chapter_title: str) -> str:
        """生成单章深入分析。"""
        prompt = f"""基于视频内容，请深入分析"{chapter_title}"，输出必须为中文：

1. 核心概念与定义（所有关键术语的严格定义）
2. 理论框架与逻辑推导（公式用LaTeX格式）
3. 实务应用与案例分析（真实商业场景）
4. 批判性思考（理论边界、反例、学术争议）
5. 与其他章节的关联（前置知识、后续依赖）

要求：
- 研究生级别的学术深度
- 所有内容用中文输出，专业术语保留英文原文
- 署名：DALONG ZHANG

{transcript[:20000]}"""
        return self.generate(prompt)

    def generate_anki(self, chapters: list[str], count: int = 20) -> str:
        """生成 Anki 卡片。"""
        combined = "\n\n".join(chapters)[:20000]
        prompt = f"""基于全部课程内容，生成{count}条研究生级别Anki真题卡片，输出必须为中文：

要求：
- 每张覆盖完整推理链条（不是简单概念记忆）
- 正面：问题/情境（包含具体数值或场景）
- 背面：多步骤推导 + 关键公式 + 现实案例引用
- 所有内容用中文输出，专业术语保留英文原文

格式：
---
卡片N
正面：...
背面：...
---

{combined}"""
        return self.generate(prompt)
