# Checkpoint-Filesystem Sync Diagnosis

## Problem

The note generation pipeline's checkpoint file (`.checkpoint.json`) can become stale or out of sync with the actual filesystem state. When this happens, the pipeline either:
- Re-runs phases that are already complete
- Fails to resume correctly
- Appears to "fail on command" from the user's perspective

## Diagnostic Steps

When user reports pipeline failure or unexpected re-processing:

### 1. Check checkpoint state
```bash
cat 01_Permanent/{course}/.checkpoint.json
```

Key fields:
- `phase`: current phase (1, 2, or 3)
- `phase1_done`: bool — syllabus generated?
- `phase2_done`: bool — all chapters processed?
- `phase3_done`: bool — MOC/Anki generated?
- `chapters`: list of chapter statuses

### 2. Check filesystem state
```bash
ls -la 01_Permanent/{course}/
```

Look for:
- `{course}_课程大纲.md` → Phase 1 complete
- `Ch_XX_*.md` files → Phase 2 complete
- `{course}_知识地图_MOC.md` → Phase 3 complete
- `Anki_*.md` → Phase 3 complete

### 3. Compare and determine fix

| Checkpoint says | Filesystem shows | Action |
|-----------------|------------------|--------|
| phase1_done=false | Syllabus exists | Delete checkpoint, re-run |
| phase1_done=true, phase2_done=false | Chapters exist | Delete checkpoint, re-run |
| phase2_done=true, phase3_done=false | MOC+Anki exist | Delete checkpoint, re-run |
| All phases false | All files exist | Delete checkpoint, re-run |
| phase3_done=true | All files exist | Pipeline already complete |

## Fix: Force Filesystem Re-detection

```bash
cd ~/Documents/all-in-one
rm 01_Permanent/{course}/.checkpoint.json
uv run flow/script/note_pipeline.py --course "{course}"
```

Without a checkpoint, `detect_phase_from_checkpoint()` scans the filesystem:
1. No syllabus → Phase 1
2. Syllabus + no chapters → Phase 2
3. Syllabus + chapters + no MOC → Phase 3
4. Everything exists → Phase 3 (regenerates capstone)

## Code Reference

From `lib/checkpoint.py`:
```python
def detect_phase_from_checkpoint(course_name: str) -> tuple[int, Optional[PipelineCheckpoint]]:
    cp = load_checkpoint(course_name)
    if cp:
        # Checkpoint EXISTS — prioritize it over filesystem
        if cp.phase3_done:
            return 3, cp
        if cp.phase2_done:
            return 3, cp
        if cp.phase1_done:
            all_done = all(ch.status == "completed" for ch in cp.chapters)
            if all_done:
                return 3, cp
            return 2, cp
        return 1, cp  # <-- Always phase 1 if phase1_done is false

    # No checkpoint — fall back to filesystem detection
    pdir = permanent_note_dir(course_name)
    syllabus_path = pdir / f"{course_name}_课程大纲.md"
    if not syllabus_path.exists():
        return 1, None
    chapter_files = list(pdir.glob("Ch_*.md"))
    if not chapter_files:
        return 2, None
    moc_file = pdir / f"{course_name}_知识地图_MOC.md"
    if not moc_file.exists():
        return 3, None
    return 3, None
```

## Prevention

- Always use `--resume` to resume from a valid checkpoint
- After manual file recovery, delete the stale checkpoint
- Verify checkpoint consistency after any manual `01_Permanent/` changes
- The pipeline commits checkpoint after each successful phase — interruption between file write and checkpoint save causes sync issues
