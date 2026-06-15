#!/usr/bin/env python3
"""
Batch generate Anki cards from all input markdown files.
Uses the project's existing Gemini client for LLM calls.
Optimized for long-running background execution with resume support.
Problem files are logged and skipped, retried at the end (max 3 attempts).
Only processes existing input files, ignores new ones added during run.
"""

import os
import sys
import time
import random
import threading
from pathlib import Path
from datetime import datetime

# Add script dir to path for imports
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.gemini_client import generate_content
from google.genai.types import GenerateContentConfig

INPUT_DIR = Path("/Users/naihe/Documents/all-in-one/youtube2note/input")
ANKI_DIR = Path("/Users/naihe/Documents/all-in-one/youtube2note/anki")
PROBLEM_LOG = SCRIPT_DIR / "problem_files.log"
MAX_RETRIES = 3

# Anki card generation prompt (minimal, as per user preference)
ANKI_PROMPT_TEMPLATE = """基于以下课程内容，按顺序总结笔记，提取Anki记忆卡片。

要求：
1. 每张卡片必须严格使用以下格式：

START
问答题
正面: [问题]
背面: [答案]
END

2. 正面是简洁的问题，背面是完整的答案
3. 按课程内容的先后顺序提取知识点
4. 保留老师提到的所有关键概念、案例和数字
5. 使用中文问答

课程内容：
```
{content}
```

请直接输出卡片内容，不要添加额外说明。"""


def sanitize_filename(name: str) -> str:
    """Sanitize filename for filesystem compatibility."""
    name = name.replace(" ", "_").replace("/", "_").replace(":", "_")
    name = name.replace("?", "").replace("*", "").replace("\"", "")
    name = name.replace("<", "").replace(">", "").replace("|", "_")
    if len(name) > 200:
        name = name[:200]
    return name


def get_output_path(input_path: Path) -> Path:
    """Determine output anki file path from input path."""
    relative = input_path.relative_to(INPUT_DIR)
    course_dir = relative.parts[0]
    safe_course = sanitize_filename(course_dir)
    safe_name = sanitize_filename(input_path.stem) + ".md"
    return ANKI_DIR / safe_course / safe_name


class TimeoutException(Exception):
    pass


def _call_with_timeout(func, args=(), kwargs=None, timeout_seconds=120):
    """Call a function with a timeout using threading."""
    kwargs = kwargs or {}
    result_container: list = [None]
    exception_container: list = [None]
    done = threading.Event()

    def target():
        try:
            result_container[0] = func(*args, **kwargs)
        except Exception as e:
            exception_container[0] = e
        finally:
            done.set()

    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    if done.wait(timeout=timeout_seconds):
        if exception_container[0] is not None:
            raise exception_container[0]
        return result_container[0]
    raise TimeoutException(f"Function timed out after {timeout_seconds}s")


def generate_anki_cards(content: str, timeout_seconds: int = 120) -> str:
    """Call Gemini API to generate Anki cards from content with timeout."""
    prompt = ANKI_PROMPT_TEMPLATE.format(content=content[:15000])

    config = GenerateContentConfig(
        temperature=0.1,
        max_output_tokens=8192,
    )

    try:
        response = _call_with_timeout(
            generate_content,
            args=(prompt,),
            kwargs={"config": config},
            timeout_seconds=timeout_seconds,
        )
        return response
    except TimeoutException:
        print(f"[ERROR] Gemini API timed out after {timeout_seconds}s", flush=True)
        return ""
    except Exception as e:
        print(f"[ERROR] Gemini API failed: {e}", flush=True)
        return ""


def log_problem_file(input_path: Path, reason: str):
    """Append problem file to log with timestamp and reason."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp} | {input_path} | {reason}\n"
    with open(PROBLEM_LOG, "a", encoding="utf-8") as f:
        f.write(line)
    print(f"[LOGGED] Added to {PROBLEM_LOG}", flush=True)


def load_problem_log() -> dict[Path, int]:
    """Load problem file retry counts from log.
    Returns dict mapping path -> attempt count.
    """
    counts: dict[Path, int] = {}
    if not PROBLEM_LOG.exists():
        return counts
    with open(PROBLEM_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(" | ")
            if len(parts) >= 2:
                p = Path(parts[1])
                counts[p] = counts.get(p, 0) + 1
    return counts


def process_file(input_path: Path, attempt: int = 1) -> bool:
    """Process a single input file and generate anki cards.
    Returns True on success or skip, False on failure (to be retried later).
    """
    output_path = get_output_path(input_path)

    if output_path.exists():
        print(f"[SKIP] Already exists: {output_path}", flush=True)
        return True

    try:
        content = input_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"[ERROR] Cannot read {input_path}: {e}", flush=True)
        log_problem_file(input_path, f"read_error_attempt{attempt}")
        return False

    if len(content.strip()) < 100:
        print(f"[SKIP] Too short: {input_path}", flush=True)
        return True

    print(f"[PROCESS] {input_path.name} (attempt {attempt}/{MAX_RETRIES})", flush=True)

    cards = generate_anki_cards(content)
    if not cards:
        log_problem_file(input_path, f"api_empty_attempt{attempt}")
        print(f"[FAIL] attempt {attempt}/{MAX_RETRIES} failed", flush=True)
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)

    header = f"# Anki Cards — {input_path.stem}\n\n---\n\n"

    lines = cards.split("\n")
    processed_lines = []
    for line in lines:
        if line.strip() == "START" and (not processed_lines or not processed_lines[-1].strip().startswith("#anki")):
            processed_lines.append("#anki")
        processed_lines.append(line)

    final_content = header + "\n".join(processed_lines)

    try:
        output_path.write_text(final_content, encoding="utf-8")
        print(f"[DONE] {output_path}", flush=True)
        return True
    except Exception as e:
        print(f"[ERROR] Cannot write {output_path}: {e}", flush=True)
        log_problem_file(input_path, f"write_error_attempt{attempt}")
        return False


def main():
    """Main batch processing loop with resume, problem logging, and retry (max 3)."""
    # Snapshot input files at start — ignore new files added during run
    all_files = []
    for root, dirs, files in os.walk(INPUT_DIR):
        if "script" in root:
            continue
        for f in sorted(files):
            if f.endswith(".md"):
                all_files.append(Path(root) / f)

    print(f"[INFO] Snapshot: {len(all_files)} input files at start", flush=True)

    todo_files = [f for f in all_files if not get_output_path(f).exists()]

    print(f"[INFO] {len(todo_files)} files to process", flush=True)

    if not todo_files:
        print("[INFO] Nothing to do!", flush=True)
        return

    success = 0
    failed = 0
    problem_files: list[Path] = []

    # Phase 1: Process all files, log problems
    for i, input_path in enumerate(todo_files, 1):
        print(f"[{i}/{len(todo_files)}] {input_path.name}", flush=True)

        result = process_file(input_path, attempt=1)
        if result:
            success += 1
        else:
            failed += 1
            problem_files.append(input_path)

        if i % 10 == 0:
            print(f"[PROGRESS] {i}/{len(todo_files)} done. Success: {success}, Failed: {failed}", flush=True)

        if i < len(todo_files):
            delay = random.uniform(2, 5)
            time.sleep(delay)

    # Phase 2: Retry problem files up to MAX_RETRIES-1 more times
    prev_counts = load_problem_log()
    attempt = 2
    while attempt <= MAX_RETRIES and problem_files:
        # Filter out files that have already reached max retries from log
        to_retry = []
        for p in problem_files:
            total_attempts = prev_counts.get(p, 0) + 1  # +1 for the first attempt just done
            if total_attempts < MAX_RETRIES:
                to_retry.append(p)
            else:
                print(f"[SKIP RETRY] {p.name} reached {MAX_RETRIES} attempts", flush=True)

        if not to_retry:
            break

        print(f"\n{'='*50}", flush=True)
        print(f"[RETRY PHASE {attempt}/{MAX_RETRIES}] {len(to_retry)} files", flush=True)

        retry_success = 0
        still_failed: list[Path] = []

        for i, input_path in enumerate(to_retry, 1):
            print(f"[RETRY {i}/{len(to_retry)}] {input_path.name}", flush=True)
            result = process_file(input_path, attempt=attempt)
            if result:
                retry_success += 1
            else:
                still_failed.append(input_path)

            if i < len(to_retry):
                delay = random.uniform(5, 10)
                time.sleep(delay)

        print(f"[RETRY {attempt} SUMMARY] Success: {retry_success}, Still Failed: {len(still_failed)}", flush=True)
        problem_files = still_failed
        attempt += 1

    print(f"\n{'='*50}", flush=True)
    final_failed = len(problem_files)
    print(f"[FINAL SUMMARY] Success: {success}, Failed: {final_failed}, Total: {len(todo_files)}", flush=True)
    if final_failed > 0:
        print(f"[PROBLEM LOG] {PROBLEM_LOG}", flush=True)
        for p in problem_files:
            print(f"  - {p}", flush=True)


if __name__ == "__main__":
    main()
