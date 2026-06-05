# Manual Pipeline 2 Workflow (NotebookLM CLI Fallback)

## When to Use

When `note_pipeline.py` fails with NotebookLM CLI errors and automated recovery doesn't work. This manual workflow was validated during the May 15, 2026 batch processing session.

## Context

The `note_pipeline.py` script uses `CLIAdapter` which calls `notebooklm` subprocess commands. However:
- `notebooklm use <id>` context doesn't persist across subprocess calls
- Bulk upload via `source add` in a loop times out for >15 files
- RPC errors (`GET_NOTEBOOK failed`) occur intermittently

## Manual Workflow

### Step 1: Create NotebookLM Project

```bash
cd ~/Documents/all-in-one
.venv/bin/notebooklm create "CourseName"
# Record the notebook ID from output
```

### Step 2: Upload Sources (Individual or Small Batches)

**For small courses (<20 files)**:
```bash
.venv/bin/notebooklm use <NOTEBOOK_ID>
for f in flow/CourseName/*.md; do
  echo "Adding: $(basename "$f")"
  .venv/bin/notebooklm source add "$f" 2>&1 | tail -2
  sleep 1
done
```

**For large courses (20+ files)** - the loop may timeout but often succeeds partially:
```bash
# Run the loop - it may timeout at 300s but files continue uploading in background
for f in flow/CourseName/*.md; do
  .venv/bin/notebooklm source add "$f" 2>&1 | tail -2
done

# Verify afterward
.venv/bin/notebooklm source list | grep -c "ready"
# If count < expected, upload remaining files individually
```

### Step 3: Generate Syllabus

```bash
.venv/bin/notebooklm ask "Based on all uploaded sources, generate a comprehensive course syllabus with chapters, key topics per chapter, and learning objectives. Format as markdown with clear hierarchy." 2>&1 | tee /tmp/syllabus_raw.md
```

Extract and save:
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

### Step 4: Generate Chapter Notes (One per Chapter)

For each chapter identified in the syllabus:
```bash
.venv/bin/notebooklm ask "Generate deep-dive chapter notes for Chapter X: [Title]. Cover: 1) Definition and Core Concepts, 2) Mathematical Derivations and Formulas, 3) Real-world Case Studies, 4) Critical Analysis and Limitations, 5) Cross-chapter Connections. Use LaTeX for formulas. Graduate-level density." 2>&1 | tee 01_Permanent/CourseName/Ch_XX_Title.md
```

### Step 5: Generate MOC

```bash
.venv/bin/notebooklm ask "Generate a comprehensive MOC (Map of Content) for [CourseName]. Include: 1) Core concept hierarchy, 2) Formula reference sheet, 3) Cross-chapter concept map, 4) Key takeaways summary. Use LaTeX for formulas." 2>&1 | tee 01_Permanent/CourseName/CourseName_知识地图_MOC.md
```

### Step 6: Generate Anki Cards

```bash
.venv/bin/notebooklm ask "Generate 20 Anki flashcards for [CourseName] in markdown format. Each card should have a question (Q) and answer (A) covering key concepts, formulas, and critical insights from all chapters. Graduate-level density." 2>&1 | tee 01_Permanent/CourseName/Anki_CourseName_20张真题卡.md
```

### Step 7: Generate Next Steps

```bash
.venv/bin/notebooklm ask "Generate a Next Steps and Advanced Topics guide for [CourseName]. Include: 1) Recommended follow-up courses, 2) Key textbooks and papers, 3) Practical application exercises, 4) Common pitfalls to avoid." 2>&1 | tee 01_Permanent/CourseName/CourseName_Next_Steps.md
```

### Step 8: Git Commit

```bash
git add 01_Permanent/CourseName/
git commit -m "Pipeline 2 complete: CourseName notes (syllabus, chapters, MOC, Anki, next steps)"
```

## Time Estimates

| Step | Time |
|------|------|
| Upload sources (60 files) | 10-15 min |
| Generate syllabus | 2-3 min |
| Generate chapters (10-15) | 20-30 min |
| Generate MOC | 2-3 min |
| Generate Anki | 2-3 min |
| Generate Next Steps | 2-3 min |
| **Total** | **40-60 min** |

## Validation

This workflow was used successfully for:
- Accounting 101 (12 videos) - May 15, 2026
- Managerial Accounting (60 videos) - May 15, 2026
