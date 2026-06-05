# Batch Playlist Processing Pattern

## Context

This reference documents the workflow for processing ALL playlists from a YouTube channel (e.g., `@Asianometry`) — 33 playlists, 1676 videos, ~504 hours. The standard `run_pipeline.py` approach is unsuitable for this scale due to terminal timeout limits (60s) and the need for fine-grained error handling.

## Workflow Overview

```
1. Fetch all playlists from channel
2. Filter out empty/non-original playlists
3. Sort by video count (ascending) — build confidence with small playlists first
4. For each playlist:
   a. Download subtitles (yt-dlp --write-auto-subs)
   b. Parse SRT → Markdown (with deduplication)
   c. Refine with Gemini (3-4s sleep between calls)
   d. Git commit
   e. On failure: log to retry file, continue to next playlist
5. After all playlists: retry failed items
```

## Step 1: Fetch Channel Playlists

```bash
.venv/bin/yt-dlp --cookies-from-browser chrome \
  --flat-playlist --dump-single-json \
  "https://www.youtube.com/@Asianometry/playlists" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
for e in d.get('entries', []):
    print(f\"{e.get('playlist_count', 0):4d} | {e.get('id')} | {e.get('title')}\")
"
```

**Filter criteria**:
- `playlist_count > 0` (skip empty playlists)
- Not a "Liked videos" / "Watch later" auto-generated list
- Original content only (not curated collections of other channels' videos)

## Step 2: Get Playlist Stats

```bash
.venv/bin/yt-dlp --flat-playlist --dump-single-json \
  "https://www.youtube.com/playlist?list=<PLAYLIST_ID>" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
entries = d.get('entries', [])
total = sum(e.get('duration', 0) or 0 for e in entries)
print(f'{len(entries)} videos, {total//3600}h{(total%3600)//60}m')
"
```

## Step 3: Download Subtitles

```bash
cd ~/Documents/all-in-one
.venv/bin/yt-dlp --cookies-from-browser chrome \
  --write-auto-subs --sub-langs en --convert-subs srt \
  --skip-download \
  --output "/tmp/india_%(playlist_index)s" \
  "https://www.youtube.com/playlist?list=<PLAYLIST_ID>"
```

## Step 4: SRT → Markdown with Deduplication

YouTube auto-generated subtitles have heavy duplication (same text across 3-5 consecutive timestamp blocks). Deduplication reduces text size by 40-60%.

```python
import re
from pathlib import Path

def parse_srt_deduped(srt_path: Path) -> str:
    content = srt_path.read_text(encoding='utf-8')
    blocks = re.split(r'\n\s*\n', content.strip())
    texts = []
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            text = ' '.join(lines[2:])
            text = re.sub(r'\r+', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            if text and text not in ['[Music]', '']:
                texts.append(text)
    # Deduplicate consecutive identical lines
    deduped = []
    prev = None
    for t in texts:
        if t != prev:
            deduped.append(t)
            prev = t
    return ' '.join(deduped)
```

## Step 5: Gemini Refinement with Rate Limiting

```python
from google.genai import Client
from google.genai.types import HttpOptions
import os, time

client = Client(
    vertexai=True,
    api_key=os.environ.get('GOOGLE_API_KEY', ''),
    http_options=HttpOptions(api_version='v1')
)

REFINE_PROMPT = """这是一段音频转录文本，请进行以下优化：
1. 补全标点符号（句号、逗号等）
2. 修正识别错误的术语、人名、地名
3. 去除口语噪音（"嗯"、"啊"、"那个"等填充词）
4. 按语义分段（每段一个主题）
5. Obsidian 格式化（Markdown 标准格式）
请直接输出优化后的文本，不要添加额外说明。

```
{body}
```
"""

def refine_file(md_path: Path) -> str:
    content = md_path.read_text(encoding='utf-8')
    body = content.split('## 字幕内容', 1)[1].strip()
    prompt = REFINE_PROMPT.format(body=body[:300000])
    response = client.models.generate_content(
        model='gemini-2.5-flash-lite',
        contents=prompt
    )
    return response.text

# Process all files with 3-4s sleep
for f in sorted(input_dir.glob('*.md')):
    try:
        refined = refine_file(f)
        # Write refined output...
    except Exception as e:
        if '429' in str(e) or 'RESOURCE_EXHAUSTED' in str(e):
            print(f"Rate limited on {f.name}")
            failed.append(f.name)
        else:
            raise
    time.sleep(3)
```

## Step 6: Progress Tracking

**JSON progress file**: `youtube2note/input/.batch_progress.json`

```json
{
  "batch_name": "Asianometry",
  "total_playlists": 33,
  "completed": [1, 2, 3, 4],
  "in_progress": 5,
  "pending": [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33],
  "failed": []
}
```

**Retry file**: `youtube2note/input/.batch_retry.json`

```json
{
  "failed": [
    {"playlist_index": 5, "title": "India", "file": "05-Title.md", "error": "429 RESOURCE_EXHAUSTED"}
  ],
  "retried": []
}
```

## Step 7: Git Commit After Each Playlist

```bash
git add youtube2note/input/<CourseName>/
git commit -m "feat: Asianometry #N <CourseName> - X videos transcribed and refined"
git push origin main
```

## Key Lessons

1. **Sort by video count ascending** — Process small playlists first to validate the pipeline before tackling large ones (e.g., 647-video playlist).
2. **3-4s sleep between Gemini calls** — Prevents most 429 errors. Retry failed files after batch completes.
3. **SRT deduplication is critical** — Auto-generated subtitles have 40-60% duplicate text.
4. **Log-and-continue on failure** — Never stop the batch for one playlist. Log and retry later.
5. **Manual step-by-step > unified pipeline** — For 30+ playlists, manual orchestration is more reliable than `run_pipeline.py`.
