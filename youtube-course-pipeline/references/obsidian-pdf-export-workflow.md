# Obsidian PDF Export Workflow

## Problem

Markdown files with LaTeX math formulas fail to render correctly when exported to PDF via automated tools (pandoc, Chrome Headless, Playwright). MathJax async rendering causes formulas to appear as raw LaTeX code in the output PDF.

## Root Cause

- **pandoc + weasyprint**: No MathJax support, formulas render as raw text
- **pandoc + Chrome Headless**: MathJax loads asynchronously but Chrome prints before rendering completes
- **pandoc + Playwright**: Can wait for MathJax promise but still fragile across platforms

## Best Practice (Validated May 2026)

**Merge Markdown files → User manually exports PDF via Obsidian**

Obsidian's built-in PDF export uses its own MathJax engine, which renders formulas perfectly. This is the most reliable approach.

## Workflow

### 1. Merge Course Chapters

Use `merge_course_md.py` to combine all `Ch_XX_*.md` files into a single printable document:

```bash
uv run flow/script/merge_course_md.py 01_Permanent/CourseName
```

This generates `01_Permanent/CourseName/CourseName_打印版.md` with:
- Title page with author (DALONG ZHANG)
- Table of contents
- All chapters merged with proper heading levels
- Page break comments between chapters
- Metadata blocks cleaned

### 2. Manual PDF Export in Obsidian

1. Open the merged `.md` file in Obsidian
2. `File → Export to PDF`
3. Obsidian's MathJax engine renders all formulas correctly

## merge_course_md.py Features

### Sorting

Files are sorted by **video range** (extracted from `视频范围: XX-YY` metadata), NOT by filename chapter number. This handles duplicate chapter numbers correctly.

Example sorting:
| File | Filename Ch | Video Range | Sort Order |
|------|------------|-------------|------------|
| Ch_03_弹性分析与福利经济学评价体系.md | 3 | 03 | 1st |
| Ch_03_弹性分析与福利经济学评价.md | 3 | 06-09 | 2nd |

### Content Cleaning

- Removes `> **Metadata**` blocks and subsequent `> - ...` lines
- Removes original H1 title (replaced with merged document heading)
- Shifts all headings down one level (H1→H2, H2→H3)
- Strips `Ch.XX ` prefix from TOC entries to avoid duplication

### Output Structure

```markdown
# Course Name

> **署名**：DALONG ZHANG
> **章节数**：N
> **生成时间**：2026

---

## 目录
- Ch.01 Chapter Title
- Ch.02 Chapter Title
...

---

<!-- pagebreak -->

## Ch.01 Chapter Title

### 一、Core Definitions
...
```

## Pitfalls

### Pitfall: Filename-based Sorting
Sorting by `sorted(glob('Ch_*.md'))` produces incorrect order when:
- Duplicate chapter numbers exist (e.g., two Ch.03 files)
- Filenames use different punctuation (`_` vs `、` vs `：`)

**Fix**: Always extract `视频范围` from file content and sort by video start number.

### Pitfall: Metadata Block Not Fully Removed
Metadata blocks may use Chinese colon `：` instead of English `:`.

**Fix**: Use regex that matches both: `视频范围\s*[:：]\s*(\d+)`

### Pitfall: Heading Level Conflicts
Merged document has its own H1 title. If chapter files also have H1 titles, the outline becomes confusing.

**Fix**: Remove original H1 and shift all headings down one level.

## Script Location

`flow/script/merge_course_md.py` in the all-in-one project.
