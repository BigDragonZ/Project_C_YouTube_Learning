"""YouTube Learning Agent Service.

为 Hermes / Kimi-Word 等 Agent 提供可后台调用的 YouTube 课程服务。
支持任务队列、结构化日志、自动降级和质量门禁。
"""

__version__ = "1.0.0"
__author__ = "DALONG ZHANG"

from .config import get_config, Config
from .task_queue import TaskQueue, Task, TaskStatus, TaskType, ErrorCode
from .logger import TaskLogger, ExecutorLogger, LogRotator
from .validators import validate_playlist_url, sanitize_course_name, check_idempotency
from .quality_gate import QualityGate, QualityResult
from .retry_manager import RetryManager, RetryRecord, RetryAttempt
from .metrics import MetricsCollector, TaskMetrics
from .prompt_registry import PromptRegistry, get_registry
from .executor import Executor, FileLock

__all__ = [
    "Config",
    "TaskQueue",
    "Task",
    "TaskStatus",
    "TaskType",
    "ErrorCode",
    "TaskLogger",
    "ExecutorLogger",
    "LogRotator",
    "validate_playlist_url",
    "sanitize_course_name",
    "check_idempotency",
    "QualityGate",
    "QualityResult",
    "RetryManager",
    "RetryRecord",
    "RetryAttempt",
    "MetricsCollector",
    "TaskMetrics",
    "PromptRegistry",
    "get_registry",
    "Executor",
    "FileLock",
    "get_config",
]
