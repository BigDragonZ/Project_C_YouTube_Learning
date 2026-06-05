"""Structured JSON Lines logger for Agent Service.

Each task gets an isolated log directory.
Global executor log for daemon-level events.
"""

import json
import os
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
LOG_RETAIN_DAYS = 7


class LogRotator:
    """Handle log rotation by size and date with retention policy."""

    @staticmethod
    def rotate_by_size(log_file: Path) -> None:
        """Rotate log if size exceeds MAX_LOG_SIZE."""
        if not log_file.exists() or log_file.stat().st_size < MAX_LOG_SIZE:
            return
        # Find next available suffix
        suffix = 1
        while (log_file.parent / f"{log_file.name}.{suffix}").exists():
            suffix += 1
        rotated = log_file.parent / f"{log_file.name}.{suffix}"
        shutil.move(str(log_file), str(rotated))

    @staticmethod
    def rotate_by_date(log_file: Path) -> None:
        """Rotate log if last modified date differs from today."""
        if not log_file.exists():
            return
        mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
        today = datetime.now()
        if mtime.date() != today.date():
            archive_name = f"{log_file.stem}.{mtime.strftime('%Y-%m-%d')}.log"
            archive_path = log_file.parent / archive_name
            # Handle duplicate archive names
            counter = 1
            while archive_path.exists():
                archive_name = f"{log_file.stem}.{mtime.strftime('%Y-%m-%d')}.{counter}.log"
                archive_path = log_file.parent / archive_name
                counter += 1
            shutil.move(str(log_file), str(archive_path))

    @staticmethod
    def cleanup_old_logs(logs_dir: Path, pattern: str = "*.log*") -> None:
        """Delete log files older than LOG_RETAIN_DAYS."""
        cutoff = datetime.now() - timedelta(days=LOG_RETAIN_DAYS)
        for f in logs_dir.glob(pattern):
            if f.is_file() and datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                f.unlink()


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
            LogRotator.rotate_by_size(self.main_log)
            LogRotator.cleanup_old_logs(self.task_log_dir)
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
            LogRotator.rotate_by_date(self.log_file)
            LogRotator.rotate_by_size(self.log_file)
            LogRotator.cleanup_old_logs(LOGS_DIR, "executor.*.log")
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
