"""Tests for task_queue.py"""

import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from task_queue import TaskQueue, TaskStatus, TaskType, ErrorCode


def test_add_and_get():
    with tempfile.TemporaryDirectory() as td:
        qf = Path(td) / "queue.json"
        q = TaskQueue(queue_file=qf)
        task = q.add("https://youtube.com/playlist?list=ABC", "TestCourse", TaskType.TRANSCRIBE)
        assert task.course_name == "TestCourse"
        assert task.task_type == TaskType.TRANSCRIBE
        retrieved = q.get(task.task_id)
        assert retrieved is not None
        assert retrieved.task_id == task.task_id


def test_update_status():
    with tempfile.TemporaryDirectory() as td:
        qf = Path(td) / "queue.json"
        q = TaskQueue(queue_file=qf)
        task = q.add("", "C", TaskType.STUDY)
        q.update(task.task_id, status=TaskStatus.RUNNING, progress_pct=50)
        updated = q.get(task.task_id)
        assert updated.status == TaskStatus.RUNNING
        assert updated.progress_pct == 50


def test_list_all():
    with tempfile.TemporaryDirectory() as td:
        qf = Path(td) / "queue.json"
        q = TaskQueue(queue_file=qf)
        q.add("", "C1", TaskType.TRANSCRIBE)
        q.add("", "C2", TaskType.STUDY)
        all_tasks = q.list_all()
        assert len(all_tasks) == 2


def test_next_pending():
    with tempfile.TemporaryDirectory() as td:
        qf = Path(td) / "queue.json"
        q = TaskQueue(queue_file=qf)
        q.add("", "C1", TaskType.TRANSCRIBE, priority=2)
        t2 = q.add("", "C2", TaskType.STUDY, priority=1)
        next_task = q.next_pending()
        assert next_task is not None
        assert next_task.task_id == t2.task_id  # priority 1 first


def test_stats():
    with tempfile.TemporaryDirectory() as td:
        qf = Path(td) / "queue.json"
        q = TaskQueue(queue_file=qf)
        q.add("", "C", TaskType.TRANSCRIBE)
        stats = q.stats()
        assert stats["pending"] == 1


def test_delete():
    with tempfile.TemporaryDirectory() as td:
        qf = Path(td) / "queue.json"
        q = TaskQueue(queue_file=qf)
        task = q.add("", "C", TaskType.ANKI)
        assert q.delete(task.task_id)
        assert q.get(task.task_id) is None


if __name__ == "__main__":
    test_add_and_get()
    test_update_status()
    test_list_all()
    test_next_pending()
    test_stats()
    test_delete()
    print("test_task_queue.py: ALL PASSED")
