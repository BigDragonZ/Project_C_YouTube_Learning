# NotebookLM Batch Upload Script Reference

## Overview

Production-tested Python script for batch-uploading course markdown files to NotebookLM with:
- Resume capability (progress saved per course)
- Duplicate detection (skips already-uploaded files)
- Rate-limit handling with exponential backoff
- Source count verification after upload
- JSON mapping file for notebook ID tracking

## Usage

```bash
# Upload single course
uv run flow/script/batch_upload_notebooklm.py --course 001_Course_Name

# Upload all courses from mapping
uv run flow/script/batch_upload_notebooklm.py --all

# Resume interrupted upload (automatic)
uv run flow/script/batch_upload_notebooklm.py --course 001_Course_Name
# Progress is read from flow/log/upload_progress_{course}.json
```

## Key Implementation Details

### Resume Logic
- Progress saved to `flow/log/upload_progress_{course}.json` after each file
- On restart, reads completed set and skips those files
- Also checks NotebookLM API for existing sources (double verification)

### Rate Limiting
- 1-second sleep between uploads
- 3 retries with exponential backoff on failure
- Special handling for "rate limit" / "too many" error messages

### NotebookLM 100-Source Limit
- Script detects when uploads stall at ~100 files
- Error: `Failed to get SOURCE_ID from registration response`
- Mitigation: Create Part 2 notebook for remaining files

### Mapping File
- `notebooklm_course_mapping.json` at project root
- Format: `{"Course_Name": "notebook-uuid", ...}`
- Updated after creating new notebooks

## File Locations
- Script: `flow/script/batch_upload_notebooklm.py`
- Mapping: `notebooklm_course_mapping.json`
- Progress logs: `flow/log/upload_progress_*.json`
- Summary logs: `flow/log/upload_summary_*.json`

## Batch Creation Pattern

For creating 20+ notebooks at once:

```python
import json, subprocess
from pathlib import Path

project_root = Path.home() / "Documents/all-in-one"
anki_dir = project_root / "youtube2note/anki"
mapping = {}

for course_dir in sorted(anki_dir.iterdir()):
    if course_dir.is_dir():
        result = subprocess.run(
            [str(project_root / ".venv/bin/notebooklm"), "create", course_dir.name],
            capture_output=True, text=True, cwd=project_root
        )
        if "Created notebook:" in result.stdout:
            parts = result.stdout.strip().split("Created notebook: ")[1].split(" - ")
            mapping[course_dir.name] = parts[0]

mapping_file = project_root / "notebooklm_course_mapping.json"
mapping_file.write_text(json.dumps(mapping, indent=2, ensure_ascii=False))
```

## Verified Behavior (June 2026)

- 21 notebooks created successfully in one batch
- 589 files uploaded across all courses
- 100-source limit confirmed per notebook
- Resume works correctly after timeout interruptions
- Shell loop upload also works for small batches:
  ```bash
  for f in youtube2note/anki/Course/*.md; do
    .venv/bin/notebooklm source add --notebook <ID> "$f"
    sleep 1
  done
  ```
