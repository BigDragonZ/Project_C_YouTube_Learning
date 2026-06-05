# Batch Processing Recovery Patterns

## Problem

When resuming a long-running batch task (e.g., 33 playlists), progress tracking files may be missing, empty, or stale. The agent must recover without blocking on metadata reconstruction.

## Pattern 1: Filesystem-Derived Progress

When `.asianometry_progress.json` is empty `{}` or missing:

```python
import json
from pathlib import Path

progress_file = Path('youtube2note/input/.asianometry_progress.json')

# Derive progress from filesystem state
completed = []
for d in Path('youtube2note/input').iterdir():
    if d.is_dir() and d.name not in ('script',):
        md_count = len(list(d.glob('*.md')))
        srt_count = len(list(d.glob('*.srt')))
        if md_count > 0 and md_count == srt_count:
            completed.append(d.name)

progress = {
    'completed': completed,
    'in_progress': None,
    'pending': []
}
progress_file.write_text(json.dumps(progress, indent=2))
```

## Pattern 2: Retry File Recovery

When `.asianometry_retry.json` is missing:

```python
retry_file = Path('youtube2note/input/.asianometry_retry.json')
if not retry_file.exists():
    retry_file.write_text(json.dumps({'failed': [], 'retried': []}, indent=2))
```

## Pattern 3: Batch Config Recovery

When `.asianometry_batch_config.json` is missing:

```python
# Option A: Re-fetch from YouTube
.venv/bin/yt-dlp --cookies-from-browser chrome \
  --flat-playlist --dump-single-json \
  "https://www.youtube.com/@Asianometry/playlists" > /tmp/playlists.json

# Option B: Use hardcoded fallback (if channel structure is stable)
PLAYLISTS = [
    {"title": "About the Overseas Chinese", "id": "PLKtxx9TnH76R0a_bKjqyaHOP5rUkvKdfH", "count": 4},
    # ... etc
]
```

## Key Rule

**Never block batch processing on missing metadata files.** Always derive state from filesystem + re-fetch from source as fallback.
