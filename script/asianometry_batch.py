#!/usr/bin/env python3
"""
Asianometry batch transcription and refinement pipeline.
Processes all remaining playlists sequentially with fault tolerance.
"""

import json
import os
import sys
import time
import random
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.youtube import parse_srt, to_markdown
from lib.gemini_client import generate_content
from google.genai.types import GenerateContentConfig
from config.paths import course_dir, build_filename

INPUT_DIR = Path("/Users/naihe/Documents/all-in-one/youtube2note/input")
PROGRESS_FILE = INPUT_DIR / ".asianometry_progress.json"
RETRY_FILE = INPUT_DIR / ".asianometry_retry.json"

REFINE_PROMPT = """这是一段音频转录文本，请进行以下优化，输出必须为中文：

1. 补全标点符号（句号、逗号等）
2. 修正识别错误的术语、人名、地名
3. 去除口语噪音（"嗯"、"啊"、"那个"等填充词）
4. 按语义分段（每段一个主题）
5. Obsidian 格式化（Markdown 标准格式）
6. 所有内容翻译成中文，保留专业术语的英文原文（如首次出现可标注英文）

请直接输出优化后的中文文本，不要添加额外说明。"""


def load_progress():
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {"completed": [], "in_progress": None, "pending": []}


def save_progress(data):
    PROGRESS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_retry():
    if RETRY_FILE.exists():
        return json.loads(RETRY_FILE.read_text())
    return {"failed": [], "retried": []}


def save_retry(data):
    RETRY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def log_fail(course_name, video_idx, title, reason):
    data = load_retry()
    data["failed"].append({
        "course": course_name,
        "index": video_idx,
        "title": title,
        "reason": reason,
        "time": datetime.now().isoformat(),
    })
    save_retry(data)


def refine_text(text: str, max_chars: int = 15000) -> str:
    """Refine transcript text with Gemini API."""
    prompt = REFINE_PROMPT + text[:max_chars]
    config = GenerateContentConfig(temperature=0.2, max_output_tokens=8192, top_p=0.95)
    return generate_content(contents=prompt, config=config)


def process_srt_file(srt_path: Path, course_name: str, index: int, title: str) -> bool:
    """Process a single SRT file: parse -> refine -> save markdown."""
    out_dir = course_dir(course_name)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / build_filename(index, title, "md")

    if out_path.exists():
        print(f"  [SKIP] Already exists: {out_path.name}")
        return True

    try:
        # Parse SRT
        srt_content = srt_path.read_text(encoding="utf-8")
        entries = parse_srt(srt_content)
        if not entries:
            print(f"  [WARN] No entries parsed from {srt_path.name}")
            log_fail(course_name, index, title, "no_entries")
            return False

        # Build raw markdown
        raw_md = to_markdown(
            entries,
            {"title": title, "url": "", "course": course_name, "index": index},
        )

        # Extract transcript text for refinement
        texts = [e.text for e in entries]
        transcript = " ".join(texts)

        # Refine with Gemini
        print(f"  [INFO] Refining ({len(transcript)} chars)...")
        refined = refine_text(transcript)

        # Build final markdown
        header = f"""# {title}

## 元信息

- **序号**: {index}
- **课程**: {course_name}
- **处理时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **来源**: 精修版

---

## 精修内容

"""
        out_path.write_text(header + refined, encoding="utf-8")
        print(f"  [OK] Saved: {out_path.name} ({len(refined)} chars)")
        return True

    except Exception as e:
        err = str(e)[:200]
        print(f"  [ERROR] {err}")
        log_fail(course_name, index, title, err)
        return False


def process_course(course_name: str) -> tuple[int, int]:
    """Process all SRT files in a course directory. Returns (success, fail) counts."""
    course_path = INPUT_DIR / course_name
    if not course_path.exists():
        print(f"[ERROR] Course directory not found: {course_path}")
        return 0, 0

    srt_files = sorted([f for f in course_path.iterdir() if f.suffix == ".srt"])
    print(f"[INFO] Found {len(srt_files)} SRT files in {course_name}")

    success = 0
    failed = 0

    for i, srt_file in enumerate(srt_files, 1):
        # Extract index and title from filename: 01-Title.en.srt
        stem = srt_file.stem  # e.g. "01-Title.en"
        parts = stem.split("-", 1)
        try:
            idx = int(parts[0])
        except ValueError:
            idx = i
        title = parts[1].replace(".en", "").replace(".", " ") if len(parts) > 1 else stem

        print(f"\n[{idx}] {title}")
        result = process_srt_file(srt_file, course_name, idx, title)
        if result:
            success += 1
        else:
            failed += 1

        # Delay between videos to avoid rate limiting
        if i < len(srt_files):
            delay = random.uniform(5, 15)
            print(f"  [WAIT] {delay:.1f}s...")
            time.sleep(delay)

    return success, failed


def main():
    # Find all directories with .srt files but fewer .md files (partially processed)
    todo_courses = []
    for item in INPUT_DIR.iterdir():
        if not item.is_dir() or item.name in ("script",):
            continue
        srt_files = list(item.glob("*.srt"))
        md_files = list(item.glob("*.md"))
        if srt_files and len(md_files) < len(srt_files):
            todo_courses.append(item.name)

    if not todo_courses:
        print("[INFO] No unprocessed SRT courses found.")
        return

    print(f"[INFO] Courses to process: {todo_courses}")

    for course_name in todo_courses:
        print(f"\n{'='*60}")
        print(f"[START] Processing: {course_name}")
        print(f"{'='*60}")

        success, failed = process_course(course_name)

        print(f"\n{'='*60}")
        print(f"[DONE] {course_name}: {success} succeeded, {failed} failed")
        print(f"{'='*60}")

        # Git commit after each course
        try:
            os.system(f'cd /Users/naihe/Documents/all-in-one && git add youtube2note/input/{course_name}/ && git commit -m "feat: Asianometry {course_name} - {success} videos refined" && git push origin main')
        except Exception as e:
            print(f"[WARN] Git commit failed: {e}")

        # Update progress
        progress = load_progress()
        # Find the playlist number for this course if known
        # For now just mark as completed
        progress["completed"] = list(set(progress.get("completed", []) + [course_name]))
        if progress.get("in_progress") == course_name:
            progress["in_progress"] = None
        save_progress(progress)

        # Delay between courses
        if course_name != todo_courses[-1]:
            delay = random.uniform(10, 20)
            print(f"[WAIT] {delay:.1f}s before next course...")
            time.sleep(delay)

    print("\n[COMPLETE] All courses processed!")


if __name__ == "__main__":
    main()
