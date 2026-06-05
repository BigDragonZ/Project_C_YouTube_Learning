"""Single-worker serial executor for Agent Service.

Phase 1: skeleton — supports transcribe/study/anki task types.
Integrates with existing run_pipeline.py / note_pipeline.py.
Features: timeout control, orphan recovery, file lock.
"""

import fcntl
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "agent_service"))

from config import get_config
from task_queue import TaskQueue, Task, TaskStatus, TaskType, ErrorCode
from logger import TaskLogger, ExecutorLogger


class FileLock:
    """Process-level file lock to prevent multiple daemon instances."""

    def __init__(self, lock_path: Path):
        self.lock_path = lock_path
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = None

    def acquire(self) -> bool:
        self._fd = open(self.lock_path, "w")
        try:
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._fd.write(str(os.getpid()))
            self._fd.flush()
            return True
        except BlockingIOError:
            self._fd.close()
            return False

    def release(self) -> None:
        if self._fd:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            self._fd.close()
            self._fd = None


class Executor:
    """Serial task executor with retry logic, timeout, and orphan recovery."""

    def __init__(self):
        self.queue = TaskQueue()
        self.exec_logger = ExecutorLogger()
        self.config = get_config()
        self.running = False
        self.current_task: Task | None = None
        self._timer = None

    def recover_orphan_tasks(self) -> int:
        """Scan and recover tasks stuck in running state (daemon crashed)."""
        recovered = 0
        timeout_map = {
            "transcribe": self.config.get_timeout("transcribe"),
            "study": self.config.get_timeout("study"),
            "anki": self.config.get_timeout("anki"),
        }
        for task in self.queue.list_all(status=TaskStatus.RUNNING):
            timeout = timeout_map.get(task.task_type.value, 3600)
            # If updated_at is older than 2x timeout, mark as orphan
            try:
                from datetime import datetime
                updated = datetime.fromisoformat(task.updated_at)
                elapsed = (datetime.now() - updated).total_seconds()
                if elapsed > timeout * 2:
                    self.queue.update(
                        task.task_id,
                        status=TaskStatus.FAILED,
                        error_code=ErrorCode.ORPHAN_TASK,
                        error_msg=f"Orphan task: daemon crashed after {elapsed:.0f}s",
                    )
                    recovered += 1
            except (ValueError, TypeError):
                continue
        if recovered > 0:
            self.exec_logger.log("WARN", f"Recovered {recovered} orphan tasks")
        return recovered

    def _set_timeout(self, task: Task) -> None:
        """Set per-task execution timeout."""
        timeout = self.config.get_timeout(task.task_type.value)

        def _on_timeout():
            self.exec_logger.log("ERROR", f"Task {task.task_id} timeout after {timeout}s")
            self.queue.update(
                task.task_id,
                status=TaskStatus.FAILED,
                error_code=ErrorCode.TIMEOUT,
                error_msg=f"Execution timeout ({timeout}s)",
            )
            # Raise exception in main thread via signal
            os.kill(os.getpid(), signal.SIGUSR1)

        self._timer = threading.Timer(timeout, _on_timeout)
        self._timer.daemon = True
        self._timer.start()

    def _clear_timeout(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def run_task(self, task: Task) -> None:
        """Execute a single task based on its type."""
        logger = TaskLogger(task.task_id)
        self.current_task = task
        self._set_timeout(task)

        try:
            self.queue.update(task.task_id, status=TaskStatus.RUNNING, current_phase="starting")
            logger.info("executor", f"开始执行任务: {task.task_type.value}")

            if task.task_type == TaskType.TRANSCRIBE:
                self._run_transcribe(task, logger)
            elif task.task_type == TaskType.STUDY:
                self._run_study(task, logger)
            elif task.task_type == TaskType.ANKI:
                self._run_anki(task, logger)

            self.queue.update(task.task_id, status=TaskStatus.COMPLETED, progress_pct=100)
            logger.info("executor", "任务完成")

        except Exception as e:
            error_msg = str(e)
            logger.error("executor", f"任务失败: {error_msg}")
            task_data = self.queue.get(task.task_id)
            retry_cfg = self.config.get_retry_config()
            max_retries = retry_cfg.get("max_retries", 3)
            if task_data and task_data.retry_count < max_retries:
                self.queue.update(
                    task.task_id,
                    status=TaskStatus.RETRYING,
                    error_msg=error_msg,
                    retry_count=task_data.retry_count + 1,
                )
            else:
                self.queue.update(
                    task.task_id,
                    status=TaskStatus.FAILED,
                    error_msg=error_msg,
                    error_code=ErrorCode.UNKNOWN,
                )
        finally:
            self._clear_timeout()
            self.current_task = None
            logger.close()

    def _run_transcribe(self, task: Task, logger: TaskLogger) -> None:
        """Phase 1: run_pipeline.py wrapper."""
        logger.info("transcribe", "启动转录流水线")
        # TODO: integrate with run_pipeline.py
        # subprocess.run([...], cwd=PROJECT_ROOT)
        logger.info("transcribe", "转录完成", output_dir=str(PROJECT_ROOT / "input" / task.course_name))

    def _run_study(self, task: Task, logger: TaskLogger) -> None:
        """Phase 2: note_pipeline.py wrapper."""
        logger.info("study", "启动学习流水线")
        # TODO: integrate with note_pipeline.py
        logger.info("study", "学习完成", output_dir=str(PROJECT_ROOT / "output" / task.course_name))

    def _run_anki(self, task: Task, logger: TaskLogger) -> None:
        """Phase 3: Anki generation wrapper."""
        logger.info("anki", "启动 Anki 生成")
        # TODO: integrate with anki generation
        logger.info("anki", "Anki 生成完成", output_dir=str(PROJECT_ROOT / "anki" / task.course_name))

    def run_once(self) -> bool:
        """Process one pending task. Returns True if a task was processed."""
        task = self.queue.next_pending()
        if not task:
            return False
        self.run_task(task)
        return True

    def _write_health(self) -> None:
        """Write daemon heartbeat to health file."""
        health_file = PROJECT_ROOT / "logs" / ".health"
        data = {
            "pid": os.getpid(),
            "status": "running" if self.running else "stopped",
            "current_task": self.current_task.task_id if self.current_task else "idle",
            "last_heartbeat": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        try:
            with open(health_file, "w") as f:
                json.dump(data, f)
        except IOError:
            pass

    def run_loop(self, interval: int = 5) -> None:
        """Main daemon loop — serial worker."""
        # Acquire file lock
        lock_path = Path(self.config.get("daemon", "lock_file", default="./logs/.daemon.lock"))
        if not lock_path.is_absolute():
            lock_path = PROJECT_ROOT / lock_path
        file_lock = FileLock(lock_path)
        if not file_lock.acquire():
            print("Error: Another daemon instance is already running.", file=sys.stderr)
            sys.exit(1)

        # Recover orphan tasks
        self.recover_orphan_tasks()

        self.running = True
        self.exec_logger.log("INFO", "执行引擎启动 (单 worker 串行)")

        try:
            while self.running:
                self._write_health()
                processed = self.run_once()
                if not processed:
                    time.sleep(interval)
        except KeyboardInterrupt:
            self.exec_logger.log("INFO", "执行引擎收到中断信号")
        finally:
            self.running = False
            self._write_health()
            self.exec_logger.log("INFO", "执行引擎停止")
            self.exec_logger.close()
            file_lock.release()

    def stop(self) -> None:
        self.running = False


def main():
    """CLI entry for manual executor run."""
    import argparse
    parser = argparse.ArgumentParser(description="Agent Service Executor")
    parser.add_argument("--once", action="store_true", help="执行一次后退出")
    parser.add_argument("--interval", type=int, default=5, help="轮询间隔(秒)")
    args = parser.parse_args()

    executor = Executor()
    if args.once:
        processed = executor.run_once()
        print(f"Processed: {processed}")
    else:
        executor.run_loop(interval=args.interval)


if __name__ == "__main__":
    main()
