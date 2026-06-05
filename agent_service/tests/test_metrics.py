"""Tests for metrics.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from metrics import MetricsCollector, METRICS_FILE


def test_start_and_finish():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        old_path = METRICS_FILE
        import metrics
        metrics.METRICS_FILE = Path(td) / "metrics.json"
        m = MetricsCollector()
        m.start_task("t1")
        import time
        time.sleep(0.01)
        m.finish_task("t1", "transcribe", "completed", quality_score=85)
        summary = m.get_summary()
        assert summary["total_tasks"] == 1
        assert summary["completed"] == 1
        assert summary["success_rate"] == 1.0
        metrics.METRICS_FILE = old_path


def test_failed_task():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        old_path = METRICS_FILE
        import metrics
        metrics.METRICS_FILE = Path(td) / "metrics.json"
        m = MetricsCollector()
        m.start_task("t2")
        m.finish_task("t2", "study", "failed", error_code="notebooklm_rpc")
        summary = m.get_summary()
        assert summary["failed"] == 1
        assert summary["success_rate"] == 0.0
        metrics.METRICS_FILE = old_path


def test_report_format():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        old_path = METRICS_FILE
        import metrics
        metrics.METRICS_FILE = Path(td) / "metrics.json"
        m = MetricsCollector()
        m.start_task("t1")
        m.finish_task("t1", "transcribe", "completed")
        report = m.format_report()
        assert "总任务" in report or "total" in report.lower()
        assert "成功率" in report or "success" in report.lower()
        metrics.METRICS_FILE = old_path


if __name__ == "__main__":
    test_start_and_finish()
    test_failed_task()
    test_report_format()
    print("test_metrics.py: ALL PASSED")
