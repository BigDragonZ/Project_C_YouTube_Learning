"""Tests for config.py"""

import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config, DEFAULT_CONFIG


def test_singleton():
    c1 = Config()
    c2 = Config()
    assert c1 is c2


def test_default_paths():
    c = Config()
    assert c.get("paths", "input") == "./input"
    assert c.get("paths", "output") == "./output"


def test_env_override():
    os.environ["AGS_API_GEMINI_MODEL"] = "test-model"
    # Reset singleton to pick up env var
    Config._instance = None
    c = Config()
    assert c.get("api", "gemini_model") == "test-model"
    del os.environ["AGS_API_GEMINI_MODEL"]
    Config._instance = None  # reset for other tests


def test_timeout_map():
    c = Config()
    assert c.get_timeout("transcribe") == 14400
    assert c.get_timeout("study") == 7200
    assert c.get_timeout("anki") == 1800


def test_retry_config():
    c = Config()
    cfg = c.get_retry_config()
    assert cfg["max_retries"] == 3
    assert cfg["sleep_jitter"] == [0, 2]


def test_path_resolution():
    c = Config()
    p = c.get_path("paths", "input")
    assert p.exists() or str(p).endswith("input")


if __name__ == "__main__":
    test_singleton()
    test_default_paths()
    test_env_override()
    test_timeout_map()
    test_retry_config()
    test_path_resolution()
    print("test_config.py: ALL PASSED")
