# Session Log: Multi-Course Batch Processing — May 15-16, 2026

## Context

User provided 10 YouTube playlist URLs and asked to process them sequentially:
"依序学习清单里的课程，另外学习前先检查下之前是否学习过，避免重复学习浪费时间。学完一门课程直接学习下一门，隔一段时间记得查看下任务状态，避免任务卡死。"

## Course List and Resolution

| # | Playlist ID | Resolved Title | Status | Videos | Duration |
|---|-------------|---------------|--------|--------|----------|
| 1 | PLUkh9m2BorqmKaLrNBjKtFDhpdFdi8f7C | Accounting 101 | COMPLETED | 12 | ~2h |
| 2 | PLfGIgQ5MF87B_gFJ5t1ulFop6ZBx7mMbe | Managerial Accounting | COMPLETED | 60 | ~8.5h |
| 3 | PLUl4u3cNGP62EXoZ4B3_Ob7lRRwpGQxkb | MIT 14.02 Principles of Macroeconomics | COMPLETED | 25 | ~20h |
| 4 | PLUkh9m2BorqnKWu0g5ZUps_CbQ-JGtbI9 | Valuation | COMPLETED | 25 | ~6h |
| 5 | PL5_qO7P2XjBd86Pw0SQVTaA88nHTj1I3e | Operations Management | IN PROGRESS | 40 | ~5h |
| 6 | PLesgViD0jhW-Ydpei3GnpoUwUGbLg50-G | Principles of Management | PENDING | - | - |
| 7 | PLuAz-nxZVHKCgTMK9qJVoRnnx5D1EdmUj | MIS | PENDING | - | - |
| 8 | PL1vtGId5rAwVDTs-_FpwHNShhqI1i9Qm8 | Strategic Analysis Masterclass | PENDING | - | - |
| - | PLDf5fbHBojiuz0vz_vkyoX5xPU_lc6FnY | YouTube Tips & Advice | SKIPPED (not a course) | 67 | - |
| - | PLUl4u3cNGP60V7HxLYRaJMbFzP77bzEjb | MIT 14.01 Principles of Microeconomics | SKIPPED (duplicate) | 25 | - |

## Key Workflow Decisions

### 1. Abandoned `note_pipeline.py` Automation

The automated `note_pipeline.py` consistently failed with `RPC GET_NOTEBOOK failed` errors. After 3+ retry attempts across Accounting_101 and Managerial_Accounting, switched to **manual NotebookLM CLI workflow**:

```bash
notebooklm create "CourseName"
notebooklm use <id>
for f in flow/CourseName/*.md; do notebooklm source add "$f"; done
notebooklm ask "Generate syllabus..."
notebooklm ask "Generate chapter notes for Ch X..."
```

This manual approach was used successfully for all 4 completed courses.

### 2. Background Mode for Pipeline 1

User explicitly corrected: "去掉600s的超时限制，任务本身就属于耗时较多的类型"

- Initial attempts used foreground `timeout=600` which hit the hard limit
- Switched to `terminal(background=True, notify_on_complete=True)` for all Pipeline 1 runs
- MIT 14.02 (25 videos, ~20h) took ~2 hours in background mode
- Valuation (25 videos, ~6h) required multiple foreground retries due to timeout, then completed with individual video processing

### 3. Sequential Processing Discipline

Strict one-course-at-a-time execution:
- Pipeline 1 complete → git commit → Pipeline 2 complete → git commit → next course
- No overlapping pipelines
- Git commit after each phase provides rollback points

### 4. Cronjob Health Monitoring

Created `pipeline-health-check` cronjob (job_id: `4aced098c70e`) running every 15 minutes to prevent silent task death during overnight processing.

## NotebookLM Notebook IDs (Active)

| Course | Notebook ID | Status |
|--------|-------------|--------|
| Accounting_101 | 0b01013e-0261-4822-b39e-a9745f5c94bc | Complete |
| Managerial_Accounting | 65c54106-24cf-4aa3-8c5c-99ab9e6fe921 | Complete |
| MIT_14.02_Principles_of_Macroeconomics | 8027dc79-b0c1-4601-8b31-c1261cc782af | Complete |
| Valuation | 8e717db7-cf44-41af-9de3-53e548189e7c | Complete |
| Operations_Management | d5e765e2-caea-4225-94d6-4e48b239e967 | Active |

## Source Upload Anomalies

- Managerial_Accounting: 68 source entries for 60 files (8 duplicates from timeout retries)
- Operations_Management: 40 files uploaded successfully in a single loop (no timeout)
- Upload time varies with file size; larger transcripts (MIT lectures) take longer

## Pipeline 1 Timeout Recovery Pattern

When `run_pipeline.py` times out at 600s with partial completion:

1. Check file count: `ls flow/CourseName/ | wc -l`
2. Check which videos are missing by comparing filename indices
3. Resume with individual video URLs:
   ```bash
   for id in MISSING_ID1 MISSING_ID2 ...; do
     uv run flow/script/run_pipeline.py "https://www.youtube.com/watch?v=$id" "CourseName"
   done
   ```
4. The pipeline skips already-refined files (checks for "精修内容" section)

## User Preferences Observed

- Graduate-level technical density with LaTeX formulas
- Professional software architecture for scripts (config/types/lib/entrypoint separation)
- All Python packages from project .venv, never system Python
- Formal documents signed as DALONG ZHANG
- Git commit after each completed step

## Remaining Work

1. Operations Management: Pipeline 2 in progress (syllabus + Ch_01 + Ch_02 done, Ch_03-09 + MOC + Anki + Next Steps remaining)
2. Principles of Management (playlist ID: PLesgViD0jhW-Ydpei3GnpoUwUGbLg50-G)
3. MIS (playlist ID: PLuAz-nxZVHKCgTMK9qJVoRnnx5D1EdmUj)
4. Strategic Analysis Masterclass (playlist ID: PL1vtGId5rAwVDTs-_FpwHNShhqI1i9Qm8)
