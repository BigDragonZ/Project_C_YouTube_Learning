"""Metrics collection and reporting for Agent Service.

Tracks task statistics, success rates, and average durations.
Persists to logs/metrics.json after each task completion.
"""

import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from config import get_config


METRICS_FILE = Path(__file__).resolve().parent.parent / "logs" / "metrics.json"


@dataclass
class TaskMetrics:
    task_id: str
    task_type: str
    status: str
    duration_seconds: float
    created_at: str
    completed_at: str
    quality_score: Optional[int] = None
    error_code: Optional[str] = None


class MetricsCollector:
    """Collect and persist task metrics."""

    def __init__(self):
        self.config = get_config()
        self._tasks: List[TaskMetrics] = []
        self._start_times: Dict[str, float] = {}
        self._load()

    def _load(self) -> None:
        if METRICS_FILE.exists():
            try:
                with open(METRICS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("tasks", []):
                    self._tasks.append(TaskMetrics(**item))
            except (json.JSONDecodeError, TypeError):
                pass

    def _save(self) -> None:
        METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "updated_at": datetime.now().isoformat(),
            "tasks": [asdict(t) for t in self._tasks[-1000:]],  # keep last 1000
        }
        tmp = METRICS_FILE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(METRICS_FILE)

    def start_task(self, task_id: str) -> None:
        self._start_times[task_id] = time.time()

    def finish_task(self, task_id: str, task_type: str, status: str,
                    quality_score: Optional[int] = None,
                    error_code: Optional[str] = None) -> None:
        duration = time.time() - self._start_times.pop(task_id, time.time())
        now = datetime.now().isoformat()
        metric = TaskMetrics(
            task_id=task_id,
            task_type=task_type,
            status=status,
            duration_seconds=round(duration, 2),
            created_at=now,
            completed_at=now,
            quality_score=quality_score,
            error_code=error_code,
        )
        self._tasks.append(metric)
        self._save()

    def get_summary(self) -> dict:
        total = len(self._tasks)
        completed = sum(1 for t in self._tasks if t.status == "completed")
        failed = sum(1 for t in self._tasks if t.status == "failed")

        # Average durations by type
        durations: Dict[str, List[float]] = {}
        for t in self._tasks:
            if t.status == "completed":
                durations.setdefault(t.task_type, []).append(t.duration_seconds)

        avg_durations = {
            task_type: round(sum(vals) / len(vals), 1)
            for task_type, vals in durations.items()
            if vals
        }

        # Quality scores
        scores = [t.quality_score for t in self._tasks if t.quality_score is not None]
        avg_quality = round(sum(scores) / len(scores), 1) if scores else 0

        return {
            "updated_at": datetime.now().isoformat(),
            "total_tasks": total,
            "completed": completed,
            "failed": failed,
            "success_rate": round(completed / total, 2) if total > 0 else 0,
            "avg_duration_by_type": avg_durations,
            "avg_quality_score": avg_quality,
        }

    def format_report(self) -> str:
        s = self.get_summary()
        lines = [
            f"总任务: {s['total_tasks']} | 完成: {s['completed']} | 失败: {s['failed']} | 成功率: {s['success_rate']:.0%}",
        ]
        for task_type, avg in s["avg_duration_by_type"].items():
            mins = avg / 60
            lines.append(f"平均 {task_type} 耗时: {mins:.1f}分钟")
        lines.append(f"平均质量评分: {s['avg_quality_score']}/100")
        return "\n".join(lines)

    def get_metrics(self) -> dict:
        return self.get_summary()
