# NotebookLM Manual Fallback Workflow

## When to Use

Use this when `note_pipeline.py` fails with NotebookLM CLI errors such as:
- `RPC GET_NOTEBOOK failed after Xs`
- `No notebook specified. Use 'notebooklm use <id>' to set context`
- Bulk upload timeouts with 20+ files
- Checkpoint state out of sync with filesystem

## Session Context

This reference documents the exact recovery workflow used on 2026-05-15 for Accounting_101 (12 videos) after automated pipeline failed.

## Step-by-Step Recovery

### 1. Verify NotebookLM Health

```bash
cd ~/Documents/all-in-one
.venv/bin/notebooklm doctor
.venv/bin/notebooklm list
```

Expected: Auth pass, notebook list shows existing projects.

### 2. Clean Up Stale State

```bash
# Delete stale checkpoint if resuming fails
rm -f 01_Permanent/<course>/.checkpoint.json

# Delete orphaned notebook if it was created but upload failed
.venv/bin/notebooklm list
.venv/bin/notebooklm delete -n <partial_id> -y
```

### 3. Create Fresh Notebook

```bash
.venv/bin/notebooklm create "CourseName"
.venv/bin/notebooklm list
# Record the notebook ID (e.g., 0b01013e-0261-4822-b39e-a9745f5c94bc)
```

### 4. Set Context

```bash
.venv/bin/notebooklm use <NOTEBOOK_ID>
.venv/bin/notebooklm status
```

### 5. Upload Sources One-by-One

```bash
for f in flow/CourseName/*.md; do
  echo "Adding: $f"
  .venv/bin/notebooklm source add "$f" 2>&1 | tail -3
  sleep 1
done
```

**Note**: The CLI does NOT support glob patterns in a single command. Each file must be added individually.

### 6. Verify Upload

```bash
.venv/bin/notebooklm source list
```

### 7. Generate Syllabus

```bash
.venv/bin/notebooklm ask "Based on all uploaded sources, generate a comprehensive course syllabus with chapters, key topics per chapter, and learning objectives. Format as markdown with clear hierarchy." 2>&1 | tee /tmp/syllabus_raw.md
```

Save the output:
```bash
cat /tmp/syllabus_raw.md | python3 -c "
import sys
content = sys.stdin.read()
start = content.find('# Course Syllabus')
if start >= 0:
    print(content[start:])
else:
    print(content)
" > 01_Permanent/CourseName/CourseName_课程大纲.md
```

### 8. Generate Chapter Notes

For each chapter identified in the syllabus:

```bash
.venv/bin/notebooklm ask "Generate deep-dive chapter notes for Chapter N: Title. Cover: 1) Definition and Core Concepts, 2) Mathematical Derivations and Formulas, 3) Real-world Case Studies, 4) Critical Analysis and Limitations, 5) Cross-chapter Connections. Use LaTeX for formulas. Graduate-level density." 2>&1 | tee 01_Permanent/CourseName/Ch_NN_Title.md
```

### 9. Generate MOC

```bash
.venv/bin/notebooklm ask "Generate a comprehensive MOC (Map of Content). Include: 1) Core concept hierarchy, 2) Formula reference sheet, 3) Cross-chapter concept map, 4) Key takeaways summary. Use LaTeX for formulas." 2>&1 | tee 01_Permanent/CourseName/CourseName_知识地图_MOC.md
```

### 10. Generate Anki Cards

```bash
.venv/bin/notebooklm ask "Generate 20 Anki flashcards in markdown format. Each card should have a question (Q) and answer (A) covering key concepts, formulas, and critical insights from all chapters. Graduate-level density." 2>&1 | tee 01_Permanent/CourseName/Anki_CourseName_20张真题卡.md
```

### 11. Generate Next Steps

```bash
.venv/bin/notebooklm ask "Generate a Next Steps and Advanced Topics guide. Include: 1) Recommended follow-up courses, 2) Key textbooks and papers, 3) Practical application exercises, 4) Common pitfalls to avoid." 2>&1 | tee 01_Permanent/CourseName/CourseName_Next_Steps.md
```

### 12. Git Commit

```bash
git add 01_Permanent/CourseName/
git commit -m "Pipeline 2 complete: CourseName notes (syllabus, chapters, MOC, Anki, next steps)"
```

## Key Differences from Automated Pipeline

| Aspect | Automated (`note_pipeline.py`) | Manual Fallback |
|--------|-------------------------------|-----------------|
| Upload | Bulk via `upload_sources_dir()` | One-by-one loop |
| Notebook context | `use_notebook()` in adapter | `notebooklm use` + verify |
| Checkpoint | `.checkpoint.json` auto-managed | No checkpoint, manual tracking |
| Error recovery | Retry logic in adapter | Immediate visibility, manual fix |
| Speed | Faster for small courses | Slower but more reliable |
| Best for | <15 videos, stable connection | >15 videos, CLI quirks |

## Time Estimates

For a 12-video course (Accounting_101):
- Upload: ~2 minutes
- Syllabus: ~1 minute
- 6 chapters: ~10 minutes (parallel not possible, sequential only)
- MOC: ~1 minute
- Anki: ~1 minute
- Next steps: ~1 minute
- **Total: ~16 minutes** of active CLI time

## Lessons Learned

1. **The CLIAdapter's `use_notebook()` is unreliable across subprocess calls**. The `notebooklm` CLI stores context in a profile-specific JSON file, but the adapter's `_retry_run` doesn't ensure the state is propagated before the next command.

2. **Bulk upload via `upload_sources_dir()` triggers rate limits**. The adapter calls `source_exists()` before each upload (N+1 API calls), which quickly exhausts the CLI's tolerance.

3. **Manual one-by-one upload with `sleep 1` between files is slower but 100% reliable**. No rate limits, no context loss.

4. **Always `tee` the output of `notebooklm ask`**. The response may contain markdown formatting that needs post-processing (e.g., stripping the "Answer:" prefix).

5. **The `notebooklm ask` output includes conversation IDs** at the bottom. These are not part of the content and should be stripped if saving directly to markdown files.
