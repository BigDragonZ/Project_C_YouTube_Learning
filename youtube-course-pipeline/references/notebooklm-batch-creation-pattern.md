# NotebookLM Batch Creation Pattern

## Context

When user has a large library of existing course notes (e.g., 21 courses in `youtube2note/anki/`) and wants to create corresponding NotebookLM projects for all of them.

## Pattern

### 1. Discover Courses

```python
from pathlib import Path
anki_dir = Path("~/Documents/all-in-one/youtube2note/anki")
courses = [d.name for d in sorted(anki_dir.iterdir()) if d.is_dir()]
```

### 2. Create Notebooks in Batch

Use a loop via `execute_code` or `terminal` to avoid manual repetition:

```python
import json, subprocess
from pathlib import Path

project_root = Path.home() / "Documents/all-in-one"
mapping = {}

for course in courses:
    result = subprocess.run(
        [str(project_root / ".venv/bin/notebooklm"), "create", course],
        capture_output=True, text=True, cwd=project_root
    )
    if "Created notebook:" in result.stdout:
        parts = result.stdout.strip().split("Created notebook: ")[1].split(" - ")
        mapping[course] = parts[0]

# Save mapping for later use
mapping_file = project_root / "notebooklm_course_mapping.json"
mapping_file.write_text(json.dumps(mapping, indent=2, ensure_ascii=False))
```

### 3. Upload Sources in Batch

For each course, upload all markdown files with deduplication and resume support:

```python
import json, subprocess, time, sys
from pathlib import Path

project_root = Path.home() / "Documents/all-in-one"
notbooklm = str(project_root / ".venv/bin/notebooklm")

with open(project_root / "notebooklm_course_mapping.json") as f:
    mapping = json.load(f)

for course, nb_id in mapping.items():
    course_dir = project_root / "youtube2note/anki" / course
    md_files = sorted(course_dir.glob("*.md"))
    
    # Get existing sources
    result = subprocess.run(
        [notbooklm, "source", "list", "--notebook", nb_id, "--json"],
        capture_output=True, text=True, timeout=30
    )
    existing = set()
    if result.returncode == 0:
        data = json.loads(result.stdout)
        sources = data.get("sources", [])
        existing = {s.get("name", s.get("title", "")) for s in sources}
    
    # Upload with 1s sleep between files
    for f in md_files:
        if f.name in existing:
            print(f"SKIP: {f.name}")
            continue
        cmd = [notbooklm, "source", "add", "--notebook", nb_id, str(f)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            print(f"OK: {f.name}")
        else:
            print(f"FAIL: {f.name} — {r.stderr[:100]}")
        time.sleep(1)
```

### 4. Resume on Timeout

Large courses (>50 files) will timeout. The script saves progress after each file:

```python
progress_file = log_dir / f"upload_progress_{course}.json"
# ... after each successful upload ...
with open(progress_file, "w") as fp:
    json.dump({"completed": sorted(completed), "notebook_id": nb_id}, fp)
```

On re-run, the script reads the progress file and skips already-uploaded files.

### 5. Verify Completion

```bash
# Count sources per notebook
for id in $(cat notebooklm_course_mapping.json | python -c "import sys,json; d=json.load(sys.stdin); print('\n'.join(d.values()))"); do
  count=$(.venv/bin/notebooklm source list --notebook $id --json 2>/dev/null | python -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('sources',[])))")
  echo "$id: $count sources"
done
```

## Key Lessons (Jun 2026)

1. **Always save mapping**: `notebooklm_course_mapping.json` is essential for later operations
2. **Progress tracking**: Write progress files per course to support resume after timeout
3. **Sleep between uploads**: 1-second sleep prevents rate limiting
4. **Timeout handling**: Large courses (100+ files) will hit the 180s terminal timeout — resume is mandatory
5. **100-source limit**: NotebookLM has a hard limit of ~100 sources per notebook. For courses with >100 files, either merge files or create a second notebook
6. **Batch is faster**: Creating 21 notebooks manually would take 30+ minutes; batch script completes in ~2 minutes

## Reference Script

Full production script: `~/Documents/all-in-one/flow/script/batch_upload_notebooklm.py`
