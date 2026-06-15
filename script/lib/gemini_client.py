"""
Unified Gemini client with fault-tolerant backend chain.

Architecture:
  1. GCP Vertex AI (gemini-3.1-pro-preview) - primary, project credits
  2. Gemini Standard API (gemini-2.5-flash-lite) - fallback

Uses google-genai Client for both backends.
"""

import os
from typing import Optional

from google.genai import Client
from google.genai.types import GenerateContentConfig, HttpOptions, Part

from config.transcribe import load_config


def _get_vertex_client(cfg) -> Client:
    """Initialize Vertex AI client with API key auth."""
    if not cfg.gcp_api_key:
        raise RuntimeError("gcp-vertex-key not set")
    return Client(
        vertexai=True,
        api_key=cfg.gcp_api_key,
        http_options=HttpOptions(api_version=cfg.api_version),
    )


def _get_gemini_client(cfg) -> Client:
    """Initialize standard Gemini API client."""
    if not cfg.google_api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    return Client(api_key=cfg.google_api_key)


def generate_content(
    contents,
    config: Optional[GenerateContentConfig] = None,
    preferred_backend: Optional[str] = None,
) -> str:
    """
    Generate content with automatic backend failover.

    Args:
        contents: Text string or list of [text, Part]
        config: Generation config
        preferred_backend: "gcp-vertex" or "gemini"

    Returns:
        Generated text string
    """
    cfg = load_config()
    config = config or GenerateContentConfig(temperature=0, max_output_tokens=8192)

    # Determine backend order
    backends: list[str] = []
    if preferred_backend:
        backends.append(preferred_backend)
    elif cfg.transcriber:
        backends.append(cfg.transcriber)
    else:
        if cfg.gcp_api_key:
            backends.append("gcp-vertex")
        if cfg.google_api_key:
            backends.append("gemini")

    if not backends:
        raise RuntimeError("No API credentials available")

    errors: list[str] = []

    for backend in backends:
        try:
            print(f"[INFO] Using GCP Vertex AI ({cfg.gcp_model})...")
            client = _get_vertex_client(cfg)
            response = client.models.generate_content(
                model=cfg.gcp_model,
                contents=contents,
                config=config,
            )
            if response.text:
                return response.text
            # Check if finish_reason indicates token limit
            if response.candidates and hasattr(response.candidates[0], 'finish_reason'):
                fr = response.candidates[0].finish_reason
                if fr and fr.value == 'MAX_TOKENS':
                    raise RuntimeError(f"Response truncated: MAX_TOKENS reached")
            raise RuntimeError("Empty response from Vertex AI")
        except Exception as e:
            msg = f"{backend} failed: {str(e)[:200]}"
            print(f"[WARN] {msg}")
            errors.append(msg)

    raise RuntimeError(f"All backends failed:\n" + "\n".join(errors))


def generate_with_audio(
    prompt: str,
    audio_path: str,
    config: Optional[GenerateContentConfig] = None,
) -> str:
    """Generate content with audio file attachment."""
    with open(audio_path, "rb") as f:
        audio_data = f.read()

    contents = [
        prompt,
        Part.from_bytes(data=audio_data, mime_type="audio/mpeg"),
    ]
    return generate_content(contents, config)
