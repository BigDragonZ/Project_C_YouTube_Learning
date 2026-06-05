"""Tests for retry_manager.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retry_manager import RetryManager
from task_queue import ErrorCode


def test_should_retry_gemini_429():
    rm = RetryManager()
    should, backoff = rm.should_retry("t1", ErrorCode.GEMINI_429, 0)
    assert should is True
    assert backoff >= 2

    should, _ = rm.should_retry("t1", ErrorCode.GEMINI_429, 3)
    assert should is False


def test_should_retry_disk_full():
    rm = RetryManager()
    should, _ = rm.should_retry("t1", ErrorCode.DISK_FULL, 0)
    assert should is False


def test_should_retry_yt_403():
    rm = RetryManager()
    should, backoff = rm.should_retry("t1", ErrorCode.YT_DLP_403, 0)
    assert should is True
    assert backoff >= 10


def test_record_and_unresolved():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        import os
        old_path = RetryManager.RETRY_LOG
        RetryManager.RETRY_LOG = Path(td) / "retry.json"
        rm = RetryManager()
        rm.record("t1", ErrorCode.NOTEBOOKLM_RPC, "test error", phase="study")
        unresolved = rm.get_unresolved()
        assert len(unresolved) == 1
        assert unresolved[0].error_code == "notebooklm_rpc"
        rm.mark_resolved("t1")
        unresolved = rm.get_unresolved()
        assert len(unresolved) == 0
        RetryManager.RETRY_LOG = old_path


def test_generate_retry_script():
    rm = RetryManager()
    script = rm.generate_retry_script(["yl-001", "yl-002"])
    assert "yl-001" in script
    assert "yl-002" in script
    assert "retry" in script


def test_generate_report():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        old_path = RetryManager.RETRY_LOG
        RetryManager.RETRY_LOG = Path(td) / "retry.json"
        rm = RetryManager()
        rm.record("t1", ErrorCode.GEMINI_429, "rate limited", phase="transcribe")
        report = rm.generate_report()
        assert "Unresolved" in report or "未解决" in report or "t1" in report
        RetryManager.RETRY_LOG = old_path


if __name__ == "__main__":
    test_should_retry_gemini_429()
    test_should_retry_disk_full()
    test_should_retry_yt_403()
    test_record_and_unresolved()
    test_generate_retry_script()
    test_generate_report()
    print("test_retry_manager.py: ALL PASSED")
