"""JSON-backed task queue for YouTube Learning Agent Service.

Supports three task types: transcribe, study, anki.
Single-worker serial execution design.
"""

import json
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUEUE_FILE = PROJECT_ROOT / "logs" / "task_queue.json"
QUEUE_LOCK = threading.Lock()


class TaskStatus(str, Enum):
    PENDING = "pending"
    VALIDATING = "validating"
    RUNNING = "running"
    QUALITY_CHECK = "quality_check"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class TaskType(str, Enum):
    TRANSCRIBE = "transcribe"
    STUDY = "study"
    ANKI = "anki"


class ErrorCode(str, Enum):
    """Granular error codes for Agent automation."""
    # YouTube
    YT_DLP_403 = "yt_dlp_403"
    YT_DLP_TIMEOUT = "yt_dlp_timeout"
    YT_DLP_INVALID_URL = "yt_dlp_invalid_url"
    # Gemini
    GEMINI_429 = "gemini_429"
    GEMINI_CONTENT_FILTER = "gemini_content_filter"
    GEMINI_REMOTE_PROTOCOL = "gemini_remote_protocol"
    # NotebookLM
    NOTEBOOKLM_RPC = "notebooklm_rpc"
    NOTEBOOKLM_ZERO_SOURCE = "notebooklm_zero_source"
    NOTEBOOKLM_100_SOURCE = "notebooklm_100_source"
    NOTEBOOKLM_TIMEOUT = "notebooklm_timeout"
    # Quality
    QUALITY_LOW_RETENTION = "quality_low_retention"
    QUALITY_ENGLISH_OUTPUT = "quality_english_output"
    QUALITY_EMPTY_OUTPUT = "quality_empty_output"
    # System
    DISK_FULL = "disk_full"
    ORPHAN_TASK = "orphan_task"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass
class Task:
    task_id: str
    playlist_url: str
    course_name: str
    task_type: TaskType
    priority: int = 2  # 1=high, 2=normal, 3=low
    status: TaskStatus = TaskStatus.PENDING
    progress_pct: int = 0
    current_phase: str = ""
    error_code: Optional[ErrorCode] = None
    error_msg: Optional[str] = None
    log_file: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    video_count: Optional[int] = None
    video_completed: int = 0
    quality_score: Optional[int] = None
    retry_count: int = 0
    max_videos: Optional[int] = None

    def to_dict(self) -> dict:
        result = {
            **asdict(self),
            "task_type": self.task_type.value,
            "status": self.status.value,
        }
        if self.error_code:
            result["error_code"] = self.error_code.value
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        data["task_type"] = TaskType(data.get("task_type", "transcribe"))
        data["status"] = TaskStatus(data.get("status", "pending"))
        raw_err = data.get("error_code")
        if raw_err:
            try:
                data["error_code"] = ErrorCode(raw_err)
            except ValueError:
                data["error_code"] = ErrorCode.UNKNOWN
        else:
            data["error_code"] = None
        # Remove unknown fields for forward compatibility
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


class TaskQueue:
    """Thread-safe JSON-backed task queue."""

    def __init__(self, queue_file: Path = QUEUE_FILE):
        self.queue_file = queue_file
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self.queue_file.exists():
            self._save({"tasks": [], "seq": 0})

    def _load(self) -> dict:
        with QUEUE_LOCK:
            if not self.queue_file.exists():
                return {"tasks": [], "seq": 0}
            try:
                with open(self.queue_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {"tasks": [], "seq": 0}

    def _save(self, data: dict) -> None:
        with QUEUE_LOCK:
            tmp = self.queue_file.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            tmp.replace(self.queue_file)

    def _generate_id(self, data: dict) -> str:
        data["seq"] = data.get("seq", 0) + 1
        today = datetime.now().strftime("%y%m%d")
        return f"yl-{today}-{data['seq']:03d}"

    def add(self, playlist_url: str, course_name: str, task_type: TaskType,
            priority: int = 2, max_videos: Optional[int] = None) -> Task:
        data = self._load()
        task_id = self._generate_id(data)
        log_file = str(PROJECT_ROOT / "logs" / task_id / "main.log")
        task = Task(
            task_id=task_id,
            playlist_url=playlist_url,
            course_name=course_name,
            task_type=task_type,
            priority=priority,
            log_file=log_file,
            max_videos=max_videos,
        )
        data["tasks"].append(task.to_dict())
        self._save(data)
        return task

    def get(self, task_id: str) -> Optional[Task]:
        data = self._load()
        for t in data["tasks"]:
            if t["task_id"] == task_id:
                return Task.from_dict(t)
        return None

    def update(self, task_id: str, **kwargs) -> Optional[Task]:
        data = self._load()
        for t in data["tasks"]:
            if t["task_id"] == task_id:
                for k, v in kwargs.items():
                    if k in t:
                        t[k] = v.value if isinstance(v, Enum) else v
                t["updated_at"] = datetime.now().isoformat()
                self._save(data)
                return Task.from_dict(t)
        return None

    def list_all(self, status: Optional[TaskStatus] = None,
                 limit: int = 100) -> List[Task]:
        data = self._load()
        tasks = [Task.from_dict(t) for t in data["tasks"]]
        if status:
            tasks = [t for t in tasks if t.status == status]
        # Sort by priority (asc) then created_at (asc)
        tasks.sort(key=lambda t: (t.priority, t.created_at))
        return tasks[:limit]

    def next_pending(self) -> Optional[Task]:
        """Get highest-priority pending task."""
        data = self._load()
        pending = [
            Task.from_dict(t) for t in data["tasks"]
            if t["status"] == TaskStatus.PENDING.value
        ]
        if not pending:
            return None
        pending.sort(key=lambda t: (t.priority, t.created_at))
        return pending[0]

    def delete(self, task_id: str) -> bool:
        data = self._load()
        original_len = len(data["tasks"])
        data["tasks"] = [t for t in data["tasks"] if t["task_id"] != task_id]
        if len(data["tasks"]) < original_len:
            self._save(data)
            return True
        return False

    def stats(self) -> Dict[str, int]:
        data = self._load()
        counts = {}
        for t in data["tasks"]:
            s = t["status"]
            counts[s] = counts.get(s, 0) + 1
        return counts
