"""Error retry management with backoff strategies and script generation.

Provides per-error-type retry configuration and generates retry scripts.
"""

import json
import random
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from config import get_config
from logger import ExecutorLogger
from task_queue import ErrorCode, TaskStatus


@dataclass
class RetryAttempt:
    timestamp: str
    error_code: str
    error_msg: str
    backoff_seconds: float


@dataclass
class RetryRecord:
    task_id: str
    error_code: str
    error_msg: str
    phase: str
    attempts: List[RetryAttempt]
    notebook_id: Optional[str] = None
    sources_uploaded: int = 0
    resolved: bool = False


# Backoff config per error type: (base_delay, max_retries)
DEFAULT_BACKOFF = {
    ErrorCode.YT_DLP_403: (10, 2),
    ErrorCode.YT_DLP_TIMEOUT: (30, 3),
    ErrorCode.GEMINI_429: (2, 3),
    ErrorCode.GEMINI_CONTENT_FILTER: (5, 2),
    ErrorCode.GEMINI_REMOTE_PROTOCOL: (4, 3),
    ErrorCode.NOTEBOOKLM_RPC: (5, 3),
    ErrorCode.NOTEBOOKLM_ZERO_SOURCE: (0, 1),  # immediate fail
    ErrorCode.NOTEBOOKLM_100_SOURCE: (0, 0),  # no retry, proceed
    ErrorCode.NOTEBOOKLM_TIMEOUT: (10, 3),
    ErrorCode.QUALITY_LOW_RETENTION: (0, 2),
    ErrorCode.QUALITY_ENGLISH_OUTPUT: (0, 2),
    ErrorCode.QUALITY_EMPTY_OUTPUT: (0, 2),
    ErrorCode.DISK_FULL: (0, 0),  # no retry
    ErrorCode.ORPHAN_TASK: (0, 1),
    ErrorCode.TIMEOUT: (0, 1),
    ErrorCode.UNKNOWN: (2, 3),
}


class RetryManager:
    """Manage error retry with per-type backoff strategies."""

    RETRY_LOG = Path(__file__).resolve().parent.parent / "logs" / "retry_log.json"

    def __init__(self):
        self.config = get_config()
        self.logger = ExecutorLogger()
        self._records: Dict[str, RetryRecord] = {}
        self._load()

    def _load(self) -> None:
        if self.RETRY_LOG.exists():
            try:
                with open(self.RETRY_LOG, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    record = RetryRecord(
                        task_id=item["task_id"],
                        error_code=item["error_code"],
                        error_msg=item["error_msg"],
                        phase=item.get("phase", ""),
                        attempts=[RetryAttempt(**a) for a in item.get("attempts", [])],
                        notebook_id=item.get("notebook_id"),
                        sources_uploaded=item.get("sources_uploaded", 0),
                        resolved=item.get("resolved", False),
                    )
                    self._records[record.task_id] = record
            except (json.JSONDecodeError, KeyError):
                pass

    def _save(self) -> None:
        self.RETRY_LOG.parent.mkdir(parents=True, exist_ok=True)
        data = []
        for r in self._records.values():
            d = asdict(r)
            d["attempts"] = [asdict(a) for a in r.attempts]
            data.append(d)
        tmp = self.RETRY_LOG.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(self.RETRY_LOG)

    def record(self, task_id: str, error_code: ErrorCode, error_msg: str,
               phase: str = "", notebook_id: str = None, sources_uploaded: int = 0) -> None:
        if task_id not in self._records:
            self._records[task_id] = RetryRecord(
                task_id=task_id,
                error_code=error_code.value,
                error_msg=error_msg,
                phase=phase,
                attempts=[],
            )
        self._records[task_id].notebook_id = notebook_id
        self._records[task_id].sources_uploaded = sources_uploaded
        self._save()
        self.logger.log("WARN", f"Recorded error for {task_id}: {error_code.value} - {error_msg}")

    def should_retry(self, task_id: str, error_code: ErrorCode,
                     retry_count: int) -> tuple[bool, float]:
        """Return (should_retry, backoff_seconds)."""
        base, max_retries = DEFAULT_BACKOFF.get(error_code, (2, 3))
        if max_retries == 0:
            return False, 0.0
        if retry_count >= max_retries:
            return False, 0.0

        # Exponential backoff with jitter
        jitter_range = self.config.get("retry", "sleep_jitter", default=[0, 2])
        jitter = random.uniform(*jitter_range)
        backoff = (2 ** retry_count) * base + jitter
        return True, backoff

    def log_attempt(self, task_id: str, error_code: ErrorCode,
                    error_msg: str, backoff: float) -> None:
        if task_id in self._records:
            self._records[task_id].attempts.append(RetryAttempt(
                timestamp=datetime.now().isoformat(),
                error_code=error_code.value,
                error_msg=error_msg,
                backoff_seconds=round(backoff, 2),
            ))
            self._save()

    def mark_resolved(self, task_id: str) -> None:
        if task_id in self._records:
            self._records[task_id].resolved = True
            self._save()

    def get_unresolved(self, filter_error: Optional[str] = None) -> List[RetryRecord]:
        results = [r for r in self._records.values() if not r.resolved]
        if filter_error:
            results = [r for r in results if r.error_code.startswith(filter_error)]
        return results

    def generate_retry_script(self, task_ids: List[str]) -> str:
        """Generate a standalone retry script for manual execution."""
        lines = [
            "#!/usr/bin/env python3",
            "\"\"\"Auto-generated retry script.\"\"\"",
            "import subprocess",
            "import sys",
            "",
            "TASK_IDS = [",
        ]
        for tid in task_ids:
            lines.append(f'    "{tid}",')
        lines.extend([
            "]",
            "",
            "for tid in TASK_IDS:",
            '    print(f"Retrying {tid}...")',
            '    result = subprocess.run(',
            '        [sys.executable, "cli.py", "retry", tid, "--force"],',
            '        capture_output=True, text=True,',
            '    )',
            '    print(result.stdout)',
            '    if result.returncode != 0:',
            '        print(f"FAILED: {result.stderr}")',
            "",
            'print("All retries completed.")',
        ])
        return "\n".join(lines)

    def generate_report(self) -> str:
        """Generate human-readable retry status report."""
        unresolved = self.get_unresolved()
        lines = [f"=== Retry Report ({datetime.now().strftime('%Y-%m-%d %H:%M')}) ===", ""]
        lines.append(f"Unresolved errors: {len(unresolved)}")
        lines.append("")
        if unresolved:
            lines.append(f"{'Task ID':<20} {'Error':<25} {'Attempts':<10} {'Phase'}")
            lines.append("-" * 70)
            for r in unresolved:
                attempts = len(r.attempts)
                lines.append(
                    f"{r.task_id:<20} {r.error_code:<25} {attempts:<10} {r.phase}"
                )
        else:
            lines.append("All errors resolved.")
        return "\n".join(lines)
