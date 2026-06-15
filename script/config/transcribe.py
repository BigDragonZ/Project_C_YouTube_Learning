"""
Transcription service configuration.
Fault-tolerant chain: gcp-vertex -> gemini
"""

import os
from typing import Literal, Optional

TranscriberBackend = Literal["gcp-vertex", "gemini"]


def _env(key: str, fallback: str = "") -> str:
    return os.environ.get(key, fallback)


class TranscribeConfig:
    """Configuration loaded from environment."""

    def __init__(self):
        explicit = _env("TRANSCRIBER")
        self.transcriber: Optional[TranscriberBackend] = None
        if explicit in ("gcp-vertex", "gemini"):
            self.transcriber = explicit  # type: ignore[assignment]

        # GCP Vertex AI
        self.gcp_project_id = _env("GCP_PROJECT_ID", "gen-lang-client-0385617544")
        self.gcp_location = _env("GCP_LOCATION", "us-central1")
        self.gcp_model = _env("GCP_MODEL", "gemini-2.5-pro")
        self.gcs_bucket = _env("GCS_BUCKET", "hermes_brain")
        self.gcs_prefix = _env("GCS_PREFIX", "audio_jobs/")
        self.api_version = _env("API_VERSION", "v1")
        self.gcp_api_key = _env("gcp-vertex-key", "")

        # Gemini Standard API (fallback)
        self.gemini_std_model = _env("GEMINI_STD_MODEL", "gemini-2.5-flash-lite")
        self.google_api_key = _env("GEMINI_API_KEY", "")

    def validate(self) -> None:
        """Validate that at least one backend has credentials."""
        if not self.gcp_api_key and not self.google_api_key:
            raise RuntimeError(
                "No transcription credentials found. "
                "Set gcp-vertex-key or GEMINI_API_KEY environment variable."
            )


def load_config() -> TranscribeConfig:
    return TranscribeConfig()
