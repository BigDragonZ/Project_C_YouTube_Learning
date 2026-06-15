"""
NotebookLM configuration for note generation pipeline.
"""

import os
from pathlib import Path
from typing import Optional


def _env(key: str, fallback: str = "") -> str:
    return os.environ.get(key, fallback)


class NotebookLMConfig:
    """Configuration for NotebookLM integration."""

    def __init__(self):
        # NotebookLM CLI binary (from project venv)
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        self.notebooklm_bin: str = str(project_root / ".venv" / "bin" / "notebooklm")

        # Default persona for academic note generation
        self.persona: str = _env(
            "NOTEBOOKLM_PERSONA",
            "You are a graduate-level research assistant specializing in "
            "financial economics and quantitative methods. "
            "Produce rigorous, academically dense notes with LaTeX formulas, "
            "critical analysis, and cross-references.",
        )

        # Generation parameters
        self.max_output_tokens: int = int(_env("NOTEBOOKLM_MAX_TOKENS", "8192"))
        self.temperature: float = float(_env("NOTEBOOKLM_TEMPERATURE", "0.3"))

        # Retry policy
        self.max_retries: int = int(_env("NOTEBOOKLM_MAX_RETRIES", "3"))
        self.retry_delay: int = int(_env("NOTEBOOKLM_RETRY_DELAY", "5"))

    def validate(self) -> None:
        """Validate NotebookLM CLI is available."""
        if not Path(self.notebooklm_bin).exists():
            raise RuntimeError(
                f"NotebookLM CLI not found at {self.notebooklm_bin}. "
                "Run: uv pip install notebooklm-py"
            )


def load_config() -> NotebookLMConfig:
    return NotebookLMConfig()
