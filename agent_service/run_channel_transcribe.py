"""Sequential channel transcribe runner.

Reads a channel playlists manifest, submits transcribe tasks for the first N
playlists, and executes them serially (no daemon, no concurrency).
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "agent_service"))

from executor import Executor
from task_queue import TaskQueue, TaskType


def load_manifest(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def sanitize_course_name(name: str) -> str:
    """Keep Chinese, alphanumerics, spaces, dashes, underscores."""
    import re
    return re.sub(r"[^\w\s\-一-鿿]", "_", name).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="顺序执行频道转录精修")
    parser.add_argument("--manifest", default=str(PROJECT_ROOT / "logs" / "mei_tou_jun_playlists.json"),
                        help="播放列表清单 JSON 路径")
    parser.add_argument("--max-playlists", type=int, default=2,
                        help="最多处理前 N 个播放列表（默认 2，用于测试）")
    parser.add_argument("--max-videos", type=int, default=None,
                        help="每个播放列表最多处理前 N 个视频（默认不限制）")
    parser.add_argument("--type", choices=["transcribe", "study", "anki"],
                        default="transcribe", help="任务类型")
    args = parser.parse_args()

    manifest = load_manifest(Path(args.manifest))
    playlists = manifest.get("playlists", [])[: args.max_playlists]
    if not playlists:
        print("No playlists found in manifest", file=sys.stderr)
        return 1

    print(f"将按顺序处理 {len(playlists)} 个播放列表，每个最多 {args.max_videos} 个视频")

    queue = TaskQueue()
    executor = Executor()
    results = []

    for playlist in playlists:
        course_name = sanitize_course_name(playlist["title"])
        print(f"\n[提交] {course_name} -> {playlist['url']}")
        task = queue.add(
            playlist_url=playlist["url"],
            course_name=course_name,
            task_type=TaskType(args.type),
            priority=2,
            max_videos=args.max_videos,
        )
        print(f"  task_id: {task.task_id}, status: {task.status.value}")

        print(f"[执行] {task.task_id} ...")
        executor.run_task(task)

        refreshed = queue.get(task.task_id)
        status = refreshed.status.value if refreshed else "unknown"
        print(f"[完成] {task.task_id} -> {status}")
        results.append({
            "task_id": task.task_id,
            "course_name": course_name,
            "status": status,
            "url": playlist["url"],
        })

    print("\n=== 执行汇总 ===")
    for r in results:
        print(f"{r['task_id']:<20} {r['status']:<12} {r['course_name']}")

    failed = [r for r in results if r["status"] == "failed"]
    if failed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
