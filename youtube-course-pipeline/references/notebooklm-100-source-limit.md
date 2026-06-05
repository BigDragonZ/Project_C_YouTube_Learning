# NotebookLM 100-Source Hard Limit

## Observation (June 2026)

NotebookLM enforces a hard limit of **exactly 100 sources per notebook**.

## Error Signature

When attempting to upload the 101st file:
```
Error: Failed to get SOURCE_ID from registration response
```

All subsequent uploads fail with the same error. The first 100 sources remain intact and functional.

## Confirmed Scenario

- **Course**: 002_Financial_Accounting
- **Files**: 182 markdown files
- **Result**: First 100 uploaded successfully, files 101-182 all failed
- **Verification**: `source list --json` confirmed exactly 100 sources

## Mitigation Options

### Option 1: Accept 100 Sources (Recommended)

For most courses, 100 sources cover the full curriculum. The remaining files are often:
- Duplicate-naming artifacts (e.g., `01-Title.md` and `01-Title_.md`)
- Supplementary content
- Later chapters that overlap with earlier ones

**When to use**: Course has >100 files but core content is within first 100.

### Option 2: Create Part 2 Notebook

Create a second notebook for remaining files:
```bash
notebooklm create "002_Financial_Accounting_Part2"
# Upload remaining 82 files to new notebook
```

Update mapping file to track both:
```json
{
  "002_Financial_Accounting": "003bf138-...",
  "002_Financial_Accounting_Part2": "new-notebook-id"
}
```

**When to use**: Course genuinely has >100 distinct chapters with no overlap.

### Option 3: Merge Files

Combine multiple short chapters into single files before upload:
```python
# Merge every 2-3 files into one
for i in range(0, len(files), 3):
    chunk = files[i:i+3]
    merged = "\n\n---\n\n".join(f.read_text() for f in chunk)
    output = course_dir / f"merged_{i//3:03d}.md"
    output.write_text(merged)
```

**When to use**: Many short files (<500 words each) that can be logically grouped.

## Prevention

Before uploading, check file count:
```bash
count=$(ls youtube2note/anki/CourseName/*.md | wc -l)
if [ "$count" -gt 100 ]; then
  echo "WARNING: $count files exceeds 100-source limit"
  echo "Consider merging or splitting into multiple notebooks"
fi
```

## Note

This is a **NotebookLM platform limit**, not a CLI bug. No amount of retrying, waiting, or using different upload methods will bypass it. The limit has been stable since at least May 2026.
