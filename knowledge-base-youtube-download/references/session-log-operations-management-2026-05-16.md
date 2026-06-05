# Session Log: Operations Management Note Generation

**Date**: 2026-05-16
**Course**: Operations Management (40 videos)
**Status**: COMPLETED (9 chapters + MOC + Anki)

## Issues Encountered and Resolutions

### Issue 1: NotebookLM RPC Timeout on `source_exists()` Loop

**Symptom**: `note_pipeline.py --resume` failed repeatedly with:
```
RuntimeError: notebooklm failed after 3 attempts: RPC GET_NOTEBOOK failed after 1.037s
```

**Root cause**: `CLIAdapter.upload_sources_dir()` calls `source_exists()` before each of 40 files, generating 40+ `source list --json` API calls in rapid succession. NotebookLM backend rate-limits these requests.

**Resolution**: Manual upload via Python script with cached source list:
```python
from lib.adapters.cli import CLIAdapter
a = CLIAdapter()
a.use_notebook('b399259e-8016-40ae-8abc-bd8f6f722629')
existing = {s.get("name") or s.get("title", "") for s in a.list_sources()}
for f in files:
    if f.name not in existing:
        a.add_source(str(f))
```

**Lesson**: For courses with 20+ sources, cache the source list before upload loop. The automated `upload_sources_dir()` only works reliably for small courses.

### Issue 2: `ask()` RPC Timeout After `use_notebook()`

**Symptom**: Even after `adapter.use_notebook()`, `adapter.ask()` failed with:
```
RPC GET_LAST_CONVERSATION_ID failed after 1.472s
RPC GET_NOTEBOOK failed after 0.484s
```

**Root cause**: The `notebooklm` CLI stores context in `~/.notebooklm/profiles/default/storage_state.json`, but subprocess calls may not share this state reliably. The `use` command succeeds but subsequent `ask` calls in a NEW subprocess don't see the updated state.

**Resolution**: Run `notebooklm use <id>` manually in the shell before scripted operations. The Python script then inherits the context:
```bash
notebooklm use b399259e-8016-40ae-8abc-bd8f6f722629
# Then run Python script
```

**Alternative**: Use the Python CLIAdapter directly (same subprocess context):
```python
a = CLIAdapter()
a.use_notebook('b399259e-...')
resp = a.ask('...')  # Works because same process context
```

### Issue 3: Syllabus Parser English Format Mismatch

**Symptom**: Phase 2 loaded 0 chapters despite syllabus existing:
```
[OK] Loaded 0 chapters from saved syllabus
[OK] All 0 chapters processed
```

**Root cause**: NotebookLM output English format (`### Chapter 1: Title`) but parser only matches Chinese (`第1章：标题`).

**Resolution**: Manually reformatted syllabus to Chinese format:
```markdown
## 第1章：Introduction to Operations Management and Strategy
- **核心命题**：...
- **视频范围**：01-02
- **前置知识**：无
- **本章概要**：...
```

**Verification**: After reformatting, parser correctly loaded 9 chapters.

### Issue 4: Course Name Normalization (Spaces vs Underscores)

**Symptom**: `FileNotFoundError: Raw directory not found: /.../flow/Operations Management`

**Root cause**: Checkpoint used `"Operations Management"` (spaces) but directory is `Operations_Management` (underscores).

**Resolution**: Updated checkpoint to use underscore-normalized name and ensured `--course` argument uses underscores.

### Issue 5: Stale Notebook Duplicates

**Symptom**: Multiple notebooks with same name causing confusion:
```
Operations_Management      (2 duplicates)
Operations Management      (1 duplicate)
```

**Resolution**: Deleted stale notebooks via CLI:
```bash
notebooklm delete -n d5e765e2 -y
notebooklm delete -n dda4b504 -y
notebooklm delete -n 355df143 -y
```

## Successful Workflow

1. Created fresh notebook: `notebooklm create "Operations_Management"`
2. Manually uploaded 40 sources using cached source list (Python script)
3. Generated syllabus via `adapter.ask()` (English output)
4. Manually reformatted syllabus to Chinese parser format
5. Updated checkpoint with 9 chapters, phase=2
6. Ran `note_pipeline.py --resume --skip-upload` — Phase 2 processed all 9 chapters
7. Phase 3 auto-generated MOC + Anki
8. Git committed all outputs

## Output Files

```
01_Permanent/Operations_Management/
├── .checkpoint.json
├── Operations_Management_课程大纲.md
├── Ch_01_Introduction to Operations Management and Strategy.md
├── Ch_02_Forecasting and Demand Planning.md
├── Ch_03_Capacity Planning and Location Strategy.md
├── Ch_04_Process Selection and Facility Layout.md
├── Ch_05_Quality Management and Standards.md
├── Ch_06_Continuous Improvement and Statistical Tools.md
├── Ch_07_Inventory Management Systems.md
├── Ch_08_Operational Planning_ Scheduling_ and Lean Systems.md
├── Ch_09_Supply Chain_ Logistics_ and Operational Economics.md
├── Operations_Management_知识地图_MOC.md
└── Anki_Operations_Management_20张真题卡.md
```

## Key Takeaways

1. **Always use underscore-normalized course names** everywhere (directories, checkpoints, CLI args)
2. **For 20+ sources**: Cache source list before upload; don't rely on `upload_sources_dir()`
3. **For NotebookLM context issues**: Run `notebooklm use <id>` manually in shell before scripted operations
4. **Verify syllabus parsing** before Phase 2: `load_syllabus()` must return >0 chapters
5. **Delete stale notebooks** before creating new ones to avoid duplicate confusion
