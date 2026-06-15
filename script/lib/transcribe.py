"""
Audio transcription via unified Gemini client.

Backend chain:
  1. GCP Vertex AI (gemini-3.1-pro-preview) - primary
  2. Gemini Standard API (gemini-2.5-flash-lite) - fallback
"""

from typing import Optional

from google.genai.types import GenerateContentConfig

from config.transcribe import load_config
from lib.gemini_client import generate_with_audio

TRANSCRIBE_PROMPT = (
    "请仔细转写这段音频的内容。保持原文语言，添加标点，"
    "按语义分段，去除语气词和广告词，输出纯文本。"
)


def transcribe_audio(
    audio_path: str,
    preferred_backend: Optional[str] = None,
) -> dict[str, str]:
    """
    Transcribe audio file using Gemini.
    Fault-tolerant: Vertex AI -> Gemini fallback.
    """
    cfg = load_config()
    cfg.validate()

    text = generate_with_audio(
        prompt=TRANSCRIBE_PROMPT,
        audio_path=audio_path,
        config=GenerateContentConfig(temperature=0, max_output_tokens=8192),
    )

    # Determine which backend succeeded
    backend = preferred_backend or cfg.transcriber or "gcp-vertex"
    model = cfg.gcp_model if backend == "gcp-vertex" else cfg.gemini_std_model

    return {"text": text, "backend": backend, "model": model}
