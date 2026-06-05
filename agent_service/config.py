"""Centralized configuration management for Agent Service.

Supports: config.json (project) + config_local.json (user) + env vars.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "config.json"
LOCAL_CONFIG_FILE = PROJECT_ROOT / "config_local.json"


DEFAULT_CONFIG = {
    "paths": {
        "input": "./input",
        "output": "./output",
        "anki": "./anki",
        "notes": "./notes",
        "logs": "./logs",
    },
    "api": {
        "gemini_model": "gemini-2.5-pro",
        "gemini_fallback_model": "gemini-2.5-flash-lite",
        "notebooklm_timeout": 180,
        "yt_dlp_path": ".venv/bin/yt-dlp",
    },
    "quality": {
        "min_retention_ratio": 0.70,
        "min_chinese_ratio": 0.80,
        "min_chapter_size_kb": 10,
    },
    "retry": {
        "max_retries": 3,
        "sleep_jitter": [0, 2],
    },
    "timeout": {
        "transcribe": 14400,
        "study": 7200,
        "anki": 1800,
    },
    "daemon": {
        "poll_interval": 5,
        "lock_file": "./logs/.daemon.lock",
    },
}


class Config:
    """Thread-safe singleton config with layered loading."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._data = {}
            cls._instance._load()
        return cls._instance

    def _load(self) -> None:
        """Load config with priority: default < config.json < config_local.json < env."""
        self._data = self._deep_copy(DEFAULT_CONFIG)

        # Layer 1: project config.json
        if CONFIG_FILE.exists():
            self._merge(self._load_json(CONFIG_FILE))

        # Layer 2: user config_local.json
        if LOCAL_CONFIG_FILE.exists():
            self._merge(self._load_json(LOCAL_CONFIG_FILE))

        # Layer 3: environment variables (AGS_PATHS_INPUT, AGS_API_GEMINI_MODEL, etc.)
        self._load_from_env()

    def _load_json(self, path: Path) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _merge(self, override: dict, target: dict = None) -> None:
        """Deep merge override into target."""
        if target is None:
            target = self._data
        for key, val in override.items():
            if isinstance(val, dict) and key in target and isinstance(target[key], dict):
                self._merge(val, target[key])
            else:
                target[key] = val

    def _load_from_env(self) -> None:
        """Load AGS_* environment variables."""
        prefix = "AGS_"
        for key, val in os.environ.items():
            if not key.startswith(prefix):
                continue
            parts = key[len(prefix):].lower().split("_", 1)
            if len(parts) != 2:
                continue
            section, subkey = parts
            if section not in self._data:
                continue
            # Convert types
            if isinstance(self._data[section].get(subkey), bool):
                val = val.lower() in ("1", "true", "yes")
            elif isinstance(self._data[section].get(subkey), int):
                try:
                    val = int(val)
                except ValueError:
                    continue
            elif isinstance(self._data[section].get(subkey), float):
                try:
                    val = float(val)
                except ValueError:
                    continue
            self._data[section][subkey] = val

    def get(self, *keys: str, default: Any = None) -> Any:
        """Get config value by dotted path: config.get('paths', 'input')."""
        node = self._data
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def set(self, *keys: str, value: Any) -> None:
        """Set config value by dotted path."""
        node = self._data
        for key in keys[:-1]:
            if key not in node:
                node[key] = {}
            node = node[key]
        node[keys[-1]] = value

    def get_path(self, *keys: str) -> Path:
        """Get resolved Path from config."""
        raw = self.get(*keys)
        if raw is None:
            raise KeyError(f"Config path not found: {'.'.join(keys)}")
        path = Path(raw)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()

    def get_timeout(self, task_type: str) -> int:
        """Get timeout in seconds for task type."""
        return self.get("timeout", task_type, default=3600)

    def get_retry_config(self) -> Dict[str, Any]:
        """Get retry configuration dict."""
        return self.get("retry", default={"max_retries": 3, "sleep_jitter": [0, 2]})

    def to_dict(self) -> dict:
        return self._deep_copy(self._data)

    @staticmethod
    def _deep_copy(d: dict) -> dict:
        return json.loads(json.dumps(d))


def get_config() -> Config:
    """Factory for Config singleton."""
    return Config()


# Create default config.json if not exists
def ensure_default_config() -> None:
    if not CONFIG_FILE.exists():
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    ensure_default_config()
    cfg = get_config()
    print(f"Input path: {cfg.get_path('paths', 'input')}")
    print(f"Gemini model: {cfg.get('api', 'gemini_model')}")
    print(f"Transcribe timeout: {cfg.get_timeout('transcribe')}s")
