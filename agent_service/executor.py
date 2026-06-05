"""Single-worker serial executor for Agent Service.

Phase 1: skeleton — supports transcribe/study/anki task types.
Integrates with existing run_pipeline.py / note_pipeline.py.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "agent_service"))

from task_queue import TaskQueue, Task, TaskStatus, TaskType
from logger import TaskLogger, ExecutorLogger


class Executor:
    """Serial task executor with retry logic."""

    def __init__(self):
        self.queue = TaskQueue()
        self.exec_logger = ExecutorLogger()
        self.running = False
        self.current_task: Task | None = None

    def run_task(self, task: Task) -> None:
        """Execute a single task based on its type."""
        logger = TaskLogger(task.task_id)
        self.current_task = task

        try:
            self.queue.update(task.task_id, status=TaskStatus.RUNNING)
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
            if task_data and task_data.retry_count < 3:
                self.queue.update(
                    task.task_id,
                    status=TaskStatus.RETRYING,
                    error_msg=error_msg,
                    retry_count=task_data.retry_count + 1,
                )
            else:
                self.queue.update(task.task_id, status=TaskStatus.FAILED, error_msg=error_msg)
        finally:
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

    def run_loop(self, interval: int = 5) -> None:
        """Main daemon loop — serial worker."""
        self.running = True
        self.exec_logger.log("INFO", "执行引擎启动 (单 worker 串行)")

        try:
            while self.running:
                processed = self.run_once()
                if not processed:
                    time.sleep(interval)
        except KeyboardInterrupt:
            self.exec_logger.log("INFO", "执行引擎收到中断信号")
        finally:
            self.running = False
            self.exec_logger.log("INFO", "执行引擎停止")
            self.exec_logger.close()

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
