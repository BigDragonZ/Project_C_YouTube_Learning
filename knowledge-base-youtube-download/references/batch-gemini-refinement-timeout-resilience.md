# Batch Gemini Refinement with Timeout Resilience

## Problem

When batch-processing hundreds of videos through Gemini API refinement (e.g., 629 videos across 20 playlists), the `terminal()` foreground mode has a hard 600s timeout. The Python script processing loop will ALWAYS hit this limit before completing. However, the script continues executing API calls in the background even after the terminal session is killed.

## Key Insight

**Timeout does NOT mean failure.** The Python process receives the timeout signal but may have already dispatched API requests that complete asynchronously. The refined markdown files are written to disk as each API call returns. Checking the filesystem reveals the TRUE completion count.

## Pattern: Run-Timeout-Check-Commit-Repeat

```bash
# 1. START the batch refinement (will timeout, this is expected)
terminal(
    command="python3 -c \"import sys; ... refine_markdown(...) ...\"",
    timeout=600  # Will always timeout for large batches
)
# → exit 124 (timeout)

# 2. CHECK actual filesystem progress
ls youtube2note/input/<CourseName>/*.md | wc -l

# 3. COMMIT what was actually completed
git add youtube2note/input/<CourseName>/
git commit -m "feat: <CourseName> partial refine (N/M)"
git push origin main

# 4. REPEAT until all videos processed
# The script auto-skips already-completed files on next run
```

## Critical Implementation Details

### Auto-Skip Already-Completed Files

The refinement script MUST check for existing output files before processing:

```python
out_path = out_dir / build_filename(idx, title, 'md')
if out_path.exists():
    print(f'[{idx}] SKIP: {title}')
    continue
```

This makes the script idempotent — safe to re-run after timeout.

### Filename Matching by Index (NOT Full Title)

YouTube video titles often contain special characters (full-width colons `：`, curly quotes, em-dashes) that get sanitized differently between SRT download and MD filename generation. **NEVER** match by full reconstructed filename.

**Correct approach**: Extract the numeric index from the SRT filename and check if ANY `.md` file with that index prefix exists:

```python
# SRT filename: "12-Fanuc and the Numerical Control Revolution.en.srt"
idx = int(srt_file.stem.split('-', 1)[0])  # → 12

# Check for existing MD by index prefix
md_exists = any(
    f.name.startswith(f"{idx:02d}-") for f in out_dir.glob("*.md")
)
```

**Why this matters**: `build_filename()` may sanitize `:` to `：` or `'` to `'` differently than yt-dlp's output template. Index matching is robust across all character encoding edge cases.

### Delay Between API Calls

Use random sleep (5-15s) between Gemini API calls to avoid rate limiting:

```python
delay = random.uniform(5, 15)
time.sleep(delay)
```

### Git Commit Every N Files

Commit every 6 files to minimize lost work if the process is interrupted:

```python
if success % 6 == 0:
    os.system(f'git add ... && git commit -m "partial ({success}/{total})" && git push')
```

## Complete Inline Script Template

```python
import sys, time, random
sys.path.insert(0, 'youtube2note/input/script')
from lib.youtube import parse_srt
from lib.refine import refine_markdown
from config.paths import course_dir, build_filename
from pathlib import Path
from datetime import datetime

course_name = '<COURSE_NAME>'
course_path = Path('/Users/naihe/Documents/all-in-one/youtube2note/input') / course_name

srt_files = sorted([f for f in course_path.iterdir() if f.suffix == '.srt'])
print(f'=== {course_name}: {len(srt_files)} videos ===')

success = 0
for i, srt_file in enumerate(srt_files, 1):
    parts = srt_file.stem.split('-', 1)
    idx = int(parts[0])
    title = parts[1].replace('.en', '').replace('.', ' ')
    
    out_dir = course_dir(course_name)
    out_path = out_dir / build_filename(idx, title, 'md')
    
    # ROBUST: Check by index prefix, not exact filename
    if any(f.name.startswith(f"{idx:02d}-") for f in out_dir.glob("*.md")):
        print(f'[{idx}] SKIP')
        continue
    
    print(f'[{idx}] {title}')
    try:
        srt_content = srt_file.read_text(encoding='utf-8')
        entries = parse_srt(srt_content)
        transcript = ' '.join([e.text for e in entries])
        refined = refine_markdown(transcript)
        
        header = f"# {title}\n\n## 元信息\n- **序号**: {idx}\n..."
        out_path.write_text(header + refined, encoding='utf-8')
        success += 1
    except Exception as e:
        print(f'  ERROR: {e}')
    
    if i < len(srt_files):
        time.sleep(random.uniform(5, 15))
    
    if success % 6 == 0:
        import os
        os.system(f'cd /Users/naihe/Documents/all-in-one && git add ... && git commit ... && git push')

print(f'[DONE] {success}/{len(srt_files)}')
```

## Finding Missing Files

After a timeout, find which SRT files lack corresponding MD files:

```bash
ls youtube2note/input/<CourseName>/ | grep '\.srt$' | sort | while read f; do
  idx=$(echo "$f" | cut -d'-' -f1)
  if ! ls youtube2note/input/<CourseName>/ | grep -q "^${idx}-.*\.md$"; then
    echo "MISSING: $f"
  fi
done
```

## Progress Tracking for Multi-Playlist Batches

When processing 20+ playlists, maintain a running status:

```bash
for d in $(ls youtube2note/input/ | grep -v script | grep -v '^\.' | sort); do
  s=$(ls youtube2note/input/"$d"/*.srt 2>/dev/null | wc -l | tr -d ' ')
  m=$(ls youtube2note/input/"$d"/*.md 2>/dev/null | wc -l | tr -d ' ')
  if [ "$s" -gt 0 ]; then echo "$s $m $d"; fi
done | sort -k3,3
```

## Lessons from 629-Video Asianometry Batch (June 2026)

1. **Always expect timeout** — For >6 videos, 600s foreground timeout is guaranteed
2. **Filesystem is ground truth** — `ls *.md | wc -l` reveals actual progress, not process exit code
3. **Index-based matching** — Full-title filename matching fails on special characters; use numeric index
4. **Commit every 6 files** — Balances safety vs git noise
5. **Random 5-15s delays** — Prevents Gemini rate limiting across 600+ calls
6. **Pipeline processes 6 videos per 600s window** — Use this to estimate total runtime
7. **User prefers minimal prompts** — Just "基于以下课程内容，按顺序总结笔记" with triple-backtick wrapped content; no elaborate system prompts

## Anti-Patterns

- ❌ Polling `process(action="poll")` every few seconds — wastes iterations, check filesystem instead
- ❌ Matching MD files by full reconstructed title — breaks on special characters
- ❌ Waiting for one playlist to fully complete before starting next — timeouts are expected, pipeline continuously makes progress
- ❌ Using `execute_code` for Gemini API calls — sandbox lacks project venv packages; use `terminal()` + `uv run python` instead
