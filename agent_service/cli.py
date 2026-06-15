"""Agent CLI interface for YouTube Learning Agent Service.

Skill-style commands for Hermes / Kimi-Word integration.
Supports: submit, batch, status, logs, list, daemon.
"""

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "agent_service"))

from task_queue import TaskQueue, TaskType, TaskStatus, ErrorCode
from logger import TaskLogger


def cmd_submit(args):
    q = TaskQueue()
    task_type = TaskType(args.type)
    task = q.add(
        playlist_url=args.url or "",
        course_name=args.name,
        task_type=task_type,
        priority=args.priority,
        max_videos=args.max_videos,
    )
    result = {
        "task_id": task.task_id,
        "status": task.status.value,
        "task_type": task.task_type.value,
        "log_file": task.log_file,
        "position_in_queue": len([t for t in q.list_all(status=TaskStatus.PENDING) if t.task_id != task.task_id]) + 1,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_batch(args):
    q = TaskQueue()
    results = []
    with open(args.file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            url = parts[0]
            name = parts[1] if len(parts) > 1 else f"course_{len(results)+1}"
            task = q.add(playlist_url=url, course_name=name,
                         task_type=TaskType(args.type), priority=args.priority,
                         max_videos=args.max_videos)
            results.append({
                "task_id": task.task_id,
                "course_name": name,
                "task_type": task.task_type.value,
            })
    print(json.dumps({"submitted": len(results), "tasks": results}, ensure_ascii=False, indent=2))


def cmd_status(args):
    q = TaskQueue()
    task = q.get(args.task_id)
    if not task:
        print(f"Error: task {args.task_id} not found", file=sys.stderr)
        sys.exit(1)
    lines = [
        f"任务: {task.task_id} ({task.course_name})",
        f"类型: {task.task_type.value}",
        f"状态: {task.status.value}",
        f"进度: {task.progress_pct}%",
        f"当前阶段: {task.current_phase or 'N/A'}",
        f"质量评分: {task.quality_score or 'N/A'}",
        f"重试次数: {task.retry_count}",
        f"创建时间: {task.created_at}",
        f"更新时间: {task.updated_at}",
    ]
    if task.error_msg:
        lines.append(f"错误信息: {task.error_msg}")
    print("\n".join(lines))


def cmd_logs(args):
    logger = TaskLogger(args.task_id)
    output = logger.tail(args.tail)
    if not output:
        print("(无日志)")
    else:
        print(output)


def cmd_list(args):
    q = TaskQueue()
    status = TaskStatus(args.status) if args.status else None
    tasks = q.list_all(status=status, limit=args.limit)
    if not tasks:
        print("暂无任务")
        return
    lines = [f"{'任务ID':<20} {'类型':<12} {'状态':<12} {'进度':<6} {'课程名'}",
             "-" * 70]
    for t in tasks:
        lines.append(f"{t.task_id:<20} {t.task_type.value:<12} {t.status.value:<12} {t.progress_pct:>5}% {t.course_name}")
    print("\n".join(lines))


def cmd_retry(args):
    q = TaskQueue()
    if args.task_id:
        task = q.get(args.task_id)
        if not task:
            print(f"Error: task {args.task_id} not found", file=sys.stderr)
            sys.exit(1)
        if task.status not in (TaskStatus.FAILED, TaskStatus.RETRYING):
            print(f"Error: task {args.task_id} status is {task.status.value}, not retryable", file=sys.stderr)
            sys.exit(1)
        q.update(args.task_id, status=TaskStatus.PENDING, retry_count=task.retry_count + 1, error_msg=None, error_code=None)
        print(f"Task {args.task_id} reset to pending")
    elif args.filter_error:
        tasks = q.list_all(status=TaskStatus.FAILED)
        matched = [t for t in tasks if t.error_code and t.error_code.value.startswith(args.filter_error)]
        for t in matched[:args.batch_size]:
            q.update(t.task_id, status=TaskStatus.PENDING, retry_count=t.retry_count + 1, error_msg=None, error_code=None)
        print(f"Reset {len(matched[:args.batch_size])} tasks to pending")
    else:
        print("Error: specify --task-id or --filter-error", file=sys.stderr)
        sys.exit(1)


def cmd_metrics(args):
    q = TaskQueue()
    stats = q.stats()
    total = sum(stats.values())
    completed = stats.get(TaskStatus.COMPLETED.value, 0)
    failed = stats.get(TaskStatus.FAILED.value, 0)
    success_rate = completed / total if total > 0 else 0
    lines = [
        f"总任务: {total} | 完成: {completed} | 失败: {failed} | 成功率: {success_rate:.0%}",
        f"进行中: {stats.get(TaskStatus.RUNNING.value, 0)} | 排队: {stats.get(TaskStatus.PENDING.value, 0)} | 重试中: {stats.get(TaskStatus.RETRYING.value, 0)}",
    ]
    print("\n".join(lines))


def cmd_health(args):
    lock_file = PROJECT_ROOT / "logs" / ".daemon.lock"
    health_file = PROJECT_ROOT / "logs" / ".health"
    if not lock_file.exists():
        print("daemon: not running")
        return
    if health_file.exists():
        try:
            with open(health_file, "r") as f:
                data = json.load(f)
            status = data.get("status", "unknown")
            pid = data.get("pid", "N/A")
            current = data.get("current_task", "idle")
            last = data.get("last_heartbeat", "unknown")
            print(f"daemon: {status} (pid={pid})")
            print(f"当前任务: {current}")
            print(f"最后心跳: {last}")
        except (json.JSONDecodeError, IOError):
            print("daemon: running (health file corrupted)")
    else:
        print("daemon: running (no health file)")


def cmd_daemon(args):
    import subprocess
    import signal
    import time
    lock_file = PROJECT_ROOT / "logs" / ".daemon.lock"
    health_file = PROJECT_ROOT / "logs" / ".health"
    pid_file = PROJECT_ROOT / "logs" / ".daemon.pid"

    if args.action == "start":
        # Check if already running
        if lock_file.exists():
            try:
                with open(lock_file, "r") as f:
                    pid = f.read().strip()
                if pid and os.path.exists(f"/proc/{pid}"):
                    print(f"daemon already running (pid={pid})")
                    return
            except (IOError, ValueError):
                pass

        # Start daemon in background
        log_file = PROJECT_ROOT / "logs" / "daemon.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        script = PROJECT_ROOT / "agent_service" / "executor.py"
        cmd = [
            sys.executable, str(script),
            "--interval", str(args.interval),
        ]
        with open(log_file, "a") as out:
            proc = subprocess.Popen(
                cmd,
                stdout=out,
                stderr=subprocess.STDOUT,
                cwd=str(PROJECT_ROOT),
            )
        # Write PID file
        with open(pid_file, "w") as f:
            f.write(str(proc.pid))
        print(f"daemon started (pid={proc.pid}), log: {log_file}")
        # Wait briefly for health file
        for _ in range(10):
            if health_file.exists():
                try:
                    with open(health_file, "r") as f:
                        data = json.load(f)
                    print(f"daemon health: {data.get('status', 'unknown')}")
                    return
                except (json.JSONDecodeError, IOError):
                    pass
            time.sleep(0.3)
        print("daemon starting... (check health in a few seconds)")

    elif args.action == "stop":
        # Try to stop gracefully via health signal
        stopped = False
        if pid_file.exists():
            try:
                with open(pid_file, "r") as f:
                    pid = int(f.read().strip())
                os.kill(pid, signal.SIGTERM)
                print(f"daemon stop signal sent to pid={pid}")
                stopped = True
                # Wait for process to exit
                for _ in range(20):
                    try:
                        os.kill(pid, 0)
                        time.sleep(0.3)
                    except OSError:
                        break
            except (ValueError, OSError, ProcessLookupError):
                pass

        # Clean up lock file if stale
        if lock_file.exists():
            lock_file.unlink()
        if pid_file.exists():
            pid_file.unlink()
        if health_file.exists():
            health_file.unlink()

        if not stopped:
            print("daemon was not running (cleaned up stale lock files)")
        else:
            print("daemon stopped")

    elif args.action == "status":
        cmd_health(args)


def main():
    parser = argparse.ArgumentParser(
        description="YouTube Learning Agent Service CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # submit
    p_submit = sub.add_parser("submit", help="提交单个任务")
    p_submit.add_argument("url", nargs="?", default="", help="YouTube 播放列表 URL")
    p_submit.add_argument("--name", required=True, help="课程名称")
    p_submit.add_argument("--type", choices=["transcribe", "study", "anki"],
                          default="transcribe", help="任务类型")
    p_submit.add_argument("--priority", type=int, choices=[1, 2, 3], default=2,
                          help="优先级: 1=high, 2=normal, 3=low")
    p_submit.add_argument("--max-videos", type=int, default=None,
                          help="最多处理前 N 个视频（用于小范围测试）")
    p_submit.set_defaults(func=cmd_submit)

    # batch
    p_batch = sub.add_parser("batch", help="批量提交任务")
    p_batch.add_argument("--file", required=True, help="播放列表文件，每行一个 URL")
    p_batch.add_argument("--type", choices=["transcribe", "study", "anki"],
                         default="transcribe", help="任务类型")
    p_batch.add_argument("--priority", type=int, choices=[1, 2, 3], default=2)
    p_batch.add_argument("--max-videos", type=int, default=None,
                         help="每个播放列表最多处理前 N 个视频")
    p_batch.set_defaults(func=cmd_batch)

    # status
    p_status = sub.add_parser("status", help="查询任务状态")
    p_status.add_argument("task_id", help="任务 ID")
    p_status.set_defaults(func=cmd_status)

    # logs
    p_logs = sub.add_parser("logs", help="查看任务日志")
    p_logs.add_argument("task_id", help="任务 ID")
    p_logs.add_argument("--tail", type=int, default=50, help="显示最后 N 行")
    p_logs.set_defaults(func=cmd_logs)

    # list
    p_list = sub.add_parser("list", help="列出任务")
    p_list.add_argument("--status", choices=[s.value for s in TaskStatus], help="按状态过滤")
    p_list.add_argument("--limit", type=int, default=20, help="最大数量")
    p_list.set_defaults(func=cmd_list)

    # retry
    p_retry = sub.add_parser("retry", help="重试失败任务")
    p_retry.add_argument("task_id", nargs="?", help="任务 ID")
    p_retry.add_argument("--filter-error", help="按错误类型过滤（如 notebooklm）")
    p_retry.add_argument("--batch-size", type=int, default=10, help="批量重试数量")
    p_retry.set_defaults(func=cmd_retry)

    # metrics
    p_metrics = sub.add_parser("metrics", help="查看系统指标")
    p_metrics.set_defaults(func=cmd_metrics)

    # health
    p_health = sub.add_parser("health", help="检查 daemon 健康状态")
    p_health.set_defaults(func=cmd_health)

    # daemon
    p_daemon = sub.add_parser("daemon", help="后台引擎控制")
    p_daemon.add_argument("action", choices=["start", "stop", "status"])
    p_daemon.add_argument("--interval", type=int, default=5, help="轮询间隔(秒)")
    p_daemon.add_argument("--workers", type=int, default=1, help="worker数量(当前仅支持1)")
    p_daemon.set_defaults(func=cmd_daemon)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
