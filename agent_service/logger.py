"""Structured JSON Lines logger for Agent Service.

Each task gets an isolated log directory.
Global executor log for daemon-level events.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"


class TaskLogger:
    """Per-task structured logger."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.task_log_dir = LOGS_DIR / task_id
        self.task_log_dir.mkdir(parents=True, exist_ok=True)
        self.main_log = self.task_log_dir / "main.log"
        self._fh = None

    def _open(self):
        if self._fh is None or self._fh.closed:
            self._fh = open(self.main_log, "a", encoding="utf-8")

    def _close(self):
        if self._fh and not self._fh.closed:
            self._fh.close()

    def _write(self, level: str, phase: str, msg: str, meta: Optional[Dict[str, Any]] = None):
        self._open()
        record = {
            "ts": datetime.now().isoformat(),
            "level": level,
            "task_id": self.task_id,
            "phase": phase,
            "msg": msg,
        }
        if meta:
            record["meta"] = meta
        self._fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._fh.flush()

    def info(self, phase: str, msg: str, **meta):
        self._write("INFO", phase, msg, meta or None)

    def warn(self, phase: str, msg: str, **meta):
        self._write("WARN", phase, msg, meta or None)

    def error(self, phase: str, msg: str, **meta):
        self._write("ERROR", phase, msg, meta or None)

    def close(self):
        self._close()

    def tail(self, n: int = 50) -> str:
        """Return last N lines of main log."""
        if not self.main_log.exists():
            return ""
        lines = []
        with open(self.main_log, "r", encoding="utf-8") as f:
            for line in f:
                lines.append(line.rstrip("\n"))
        return "\n".join(lines[-n:])


class ExecutorLogger:
    """Global daemon-level logger."""

    def __init__(self):
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        self.log_file = LOGS_DIR / "executor.log"
        self._fh = None

    def _open(self):
        if self._fh is None or self._fh.closed:
            self._fh = open(self.log_file, "a", encoding="utf-8")

    def log(self, level: str, msg: str, **meta):
        self._open()
        record = {
            "ts": datetime.now().isoformat(),
            "level": level,
            "msg": msg,
        }
        if meta:
            record["meta"] = meta
        self._fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._fh.flush()

    def close(self):
        if self._fh and not self._fh.closed:
            self._fh.close()


def get_logger(task_id: Optional[str] = None) -> TaskLogger:
    """Factory: returns TaskLogger for task_id, or ExecutorLogger if None."""
    if task_id:
        return TaskLogger(task_id)
    return ExecutorLogger()
