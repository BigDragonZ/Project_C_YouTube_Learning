"""Tests for config/transcribe.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.transcribe import TranscribeConfig, load_config


def test_load_config_defaults():
    cfg = load_config()
    assert cfg.gcp_project_id == "gen-lang-client-0385617544"
    assert cfg.gcp_location == "us-central1"
    assert cfg.gcp_model == "gemini-2.5-pro"
    assert cfg.gcs_bucket == "hermes_brain"
    assert cfg.gcs_prefix == "audio_jobs/"
    assert cfg.api_version == "v1"
    assert cfg.gemini_std_model == "gemini-2.5-flash-lite"


def test_validate_no_credentials():
    cfg = TranscribeConfig()
    cfg.gcp_api_key = ""
    cfg.google_api_key = ""
    try:
        cfg.validate()
        assert False, "Should have raised"
    except RuntimeError as e:
        assert "No transcription credentials" in str(e)


def test_validate_with_gcp_key():
    cfg = TranscribeConfig()
    cfg.gcp_api_key = "test-key"
    cfg.google_api_key = ""
    cfg.validate()  # Should not raise


def test_validate_with_gemini_key():
    cfg = TranscribeConfig()
    cfg.gcp_api_key = ""
    cfg.google_api_key = "test-key"
    cfg.validate()  # Should not raise


if __name__ == "__main__":
    test_load_config_defaults()
    test_validate_no_credentials()
    test_validate_with_gcp_key()
    test_validate_with_gemini_key()
    print("transcribe tests: 4 passed")
