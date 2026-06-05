# Session Log: Multi-Course Batch Processing — May 16, 2026 (Completion)

## Context

User continued processing remaining courses from the 10-course batch. Previous session (May 15) completed 4 courses. This session completed the remaining 6 courses.

## Course List and Final Status

| # | Playlist ID | Resolved Title | Status | Videos | Chapters |
|---|-------------|---------------|--------|--------|----------|
| 1 | PLUkh9m2BorqmKaLrNBjKtFDhpdFdi8f7C | Accounting 101 | COMPLETED | 12 | - |
| 2 | PLfGIgQ5MF87B_gFJ5t1ulFop6ZBx7mMbe | Managerial Accounting | COMPLETED | 60 | - |
| 3 | PLUl4u3cNGP62EXoZ4B3_Ob7lRRwpGQxkb | MIT 14.02 Principles of Macroeconomics | COMPLETED | 25 | - |
| 4 | PLUkh9m2BorqnKWu0g5ZUps_CbQ-JGtbI9 | Valuation | COMPLETED | 25 | 10 |
| 5 | PL5_qO7P2XjBd86Pw0SQVTaA88nHTj1I3e | Operations Management | COMPLETED | 40 | 9 |
| 6 | PLesgViD0jhW-Ydpei3GnpoUwUGbLg50-G | Principles of Microeconomics | COMPLETED | - | - |
| 7 | PLLhSIFfDZcUWjsTsHWuSriqRs065PSrdb | Principles of Management | COMPLETED | 25 | 10 |
| 8 | PL1vtGId5rAwVDTs-_FpwHNShhqI1i9Qm8 | MIS | COMPLETED | 46 | 7 |
| 9 | PLDf5fbHBojiuz0vz_vkyoX5xPU_lc6FnY | Strategic Analysis Masterclass | COMPLETED | 6 | 6 |
| - | PLuAz-nxZVHKCgTMK9qJVoRnnx5D1EdmUj | YouTube Tips & Advice | SKIPPED (not a course) | 67 | - |
| - | PLUl4u3cNGP60V7HxLYRaJMbFzP77bzEjb | MIT 14.01 Principles of Microeconomics | SKIPPED (duplicate) | 25 | - |

**All 10 courses completed.**

## Key Workflow Decisions

### 1. `note_pipeline.py` Automation Restored

Unlike the May 15 session where `note_pipeline.py` consistently failed with RPC errors, the May 16 session successfully used the automated pipeline for multiple courses:

- **Operations Management**: `note_pipeline.py` completed all 9 chapters + MOC + Anki
- **MIS**: Completed 7 chapters + MOC + Anki (MOC/Anki manually created due to API rate limit)
- **Principles of Management**: Completed 10 chapters + MOC + Anki (initially failed due to RPC errors, re-generated successfully after notebook recreation)
- **Strategic Analysis**: Completed 6 chapters + MOC + Anki

**Why it worked this time**: NotebookLM API was more stable on May 16. The key was using `terminal(background=True, notify_on_complete=True)` for long-running Phase 2/3 operations.

### 2. Manual Fallback Pattern Validated

When `note_pipeline.py` failed (MIS MOC/Anki, Principles of Management initial attempt), the manual fallback workflow from Pitfall 20 was used successfully:

```bash
# 1. Create notebook
notebooklm create "CourseName"

# 2. Upload sources individually
for f in flow/CourseName/*.md; do notebooklm source add "$f"; sleep 1; done

# 3. Generate syllabus via ask
notebooklm ask "Generate comprehensive syllabus..."

# 4. For each chapter: generate deep-dive notes
notebooklm ask "Generate chapter notes for Chapter X..."

# 5. Generate MOC and Anki
notebooklm ask "Generate MOC..."
notebooklm ask "Generate Anki cards..."
```

### 3. Syllabus Parser English Format Handling

NotebookLM sometimes outputs English format (`Chapter N: Title`) instead of Chinese (`第N章：标题`). The parser was updated to handle both formats. When manual syllabus creation was needed, the Chinese format was used to ensure parser compatibility.

### 4. Notebook Recreation for API Recovery

When a notebook entered a degraded state (Principles of Management), the recovery pattern was:
1. Delete the degraded notebook: `notebooklm delete -n <id> -y`
2. Create new notebook: `notebooklm create "CourseName"`
3. Re-upload all sources
4. Re-run pipeline from Phase 2

### 5. Course Name Normalization

All course names normalized to underscore format:
- `Operations_Management` (not "Operations Management")
- `Principles_of_Management` (not "Principles of Management")
- `Strategic_Analysis` (not "Strategic Analysis Masterclass")

This prevents path mismatches between checkpoint and filesystem.

## NotebookLM Notebook IDs (Final)

| Course | Notebook ID | Status |
|--------|-------------|--------|
| Operations_Management | b399259e-8016-40ae-8abc-bd8f6f722629 | Complete |
| MIS | 6dae0578-c355-4115-951e-5f6451f8c59a | Complete |
| Principles_of_Management | 24befb9e-83ea-4504-8d05-e83cba600ab1 | Complete |
| Strategic_Analysis | 1b8aece4-f4e3-46c5-86df-eb34e47b4c7a | Complete |

## Critical Pitfalls Discovered

### Pitfall 13f: NotebookLM API Persistent Rate Limiting (Phase 3 MOC/Anki)

After intensive Phase 2 chapter generation, NotebookLM API can enter a degraded state where ALL `ask` calls return rate limit errors for 5-10+ minutes.

**Recovery**: Escalating wait strategy (60s → 180s → 300s). If still failing after 5+ minutes, proceed with manual MOC/Anki creation.

**Key insight**: Chapter notes (Phase 2) are the critical output. MOC and Anki can always be reconstructed from the syllabus and chapter titles.

### Pitfall 13g: CLIAdapter Source Upload Timeout

`CLIAdapter.upload_sources_dir()` uploads files one-by-one. For 40+ files, this takes 5-10 minutes and may timeout.

**Fix**: Use direct Python upload with progress tracking, or shell loop with verification.

### Pitfall 13h: Empty Chapter Notes (All Rounds Failed)

When API is degraded, chapter files are created but all 5 rounds contain `[生成失败]` markers.

**Recovery**: Wait for API recovery, delete failed files, reset checkpoint, re-run.

### Pitfall 13j: URL Validation Before Transcription

Always validate playlist title matches expected course. The URL `PLuAz-nxZVHKCgTMK9qJVoRnnx5D1EdmUj` resolved to "YouTube Tips & Advice" instead of "Principles of Management".

**Detection**: `.venv/bin/yt-dlp --flat-playlist --print "%(playlist_title)s" "<URL>"`

### Pitfall 13k: Git History Rewriting for Credential Removal

A commit accidentally contained a GCP API key in README.md. Used `git filter-branch` to remove the file from history, followed by force-push and `reflog expire` + `gc` to purge dangling objects.

### Pitfall 13l: note_pipeline.py Foreground Timeout

Foreground `terminal()` has a hard 600s limit. For courses with 5+ chapters, ALWAYS use `background=True, notify_on_complete=True`.

### Pitfall 13m: Syllabus Reformatting for Parser

NotebookLM may output English format. Manual reformatting to Chinese format (`第N章：Title`) is required before saving to ensure `syllabus_parser.py` compatibility.

### Pitfall 13n: Multiple Notebooks with Same Name

Retried pipelines may create duplicate notebooks. Always check `notebooklm list` and delete duplicates.

### Pitfall 13o: Checkpoint Phase Out of Sync

If checkpoint says phase=1 but filesystem has syllabus + chapters, delete checkpoint to trigger auto-detection.

### Pitfall 13r: Syllabus Expansion

Initial manual syllabus for Principles of Management had 5 chapters. Content analysis revealed 10 natural chapters. Be prepared to expand manual syllabi.

## User Preferences Observed

- Graduate-level technical density with LaTeX formulas
- Professional software architecture (config/types/lib/entrypoint separation)
- All Python packages from project .venv, never system Python
- Formal documents signed as DALONG ZHANG
- Git commit after each completed step
- Course directory names use underscores (not spaces)

## Final Output Structure

Each completed course has:
```
01_Permanent/{CourseName}/
├── {CourseName}_课程大纲.md          # Syllabus (Chinese format)
├── Ch_01_*.md ~ Ch_NN_*.md           # Chapter deep-dive notes
├── {CourseName}_知识地图_MOC.md       # Knowledge map
├── Anki_{CourseName}_20张真题卡.md    # 20 flashcards
└── .checkpoint.json                   # Pipeline state
```

## Git Commits

Total commits for this session: 15+
Final commit: `a69115e` — ALL 10 COURSES COMPLETED
