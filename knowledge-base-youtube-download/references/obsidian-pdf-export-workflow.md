# Obsidian Native PDF Export for MathJax-Heavy Notes

## Problem

Markdown notes with LaTeX math formulas (`$...$` and `$$...$$`) fail to render correctly when exported to PDF via automated tools (pandoc, Chrome Headless, Playwright, WeasyPrint). These tools either:
- Cannot render MathJax asynchronously (Chrome Headless prints before MathJax finishes)
- Lack MathJax support entirely (WeasyPrint)
- Require complex LaTeX toolchain installation (MacTeX/BasicTeX) that the user does not need

## Root Cause

The user's notes contain ~3,400 LaTeX formulas (555 block-level `$$...$$` + 2,830 inline `$...$`) across 110 Markdown files. Automated PDF renderers struggle because:
1. MathJax renders math client-side via JavaScript
2. Headless browsers don't wait for async MathJax before capturing PDF
3. LaTeX-based renderers (xelatex) require full TeX distribution (~2-5GB)

## Verified Solution (May 16, 2026)

**Merge Markdown chapters → User manually exports via Obsidian**

Obsidian's built-in PDF export (`File → Export to PDF`) uses its own MathJax engine and renders formulas perfectly. This is the only reliable path for MathJax-heavy academic notes.

## Workflow

### Step 1: Merge Course Chapters

Use `merge_course_md.py` to combine all `Ch_XX_*.md` files into a single printable document:

```bash
cd ~/Documents/all-in-one
uv run flow/script/merge_course_md.py 01_Permanent/Principles_of_Microeconomics
```

Output: `01_Permanent/Principles_of_Microeconomics/Principles_of_Microeconomics_打印版.md`

The script:
- Collects all `Ch_XX_*.md` files and sorts by chapter number
- Removes Metadata blocks and duplicate H1 titles
- Shifts all headings down one level (H1→H2, H2→H3) to avoid conflict with merged title
- Generates a table of contents
- Inserts `<!-- pagebreak -->` comments between chapters
- Adds title page with DALONG ZHANG attribution

### Step 2: Open in Obsidian and Export

1. Open the merged `.md` file in Obsidian
2. Switch to **Reading mode** (not Edit mode) to ensure MathJax renders
3. `File → Export to PDF`
4. Obsidian handles all formula rendering natively

## What NOT to Do

| Approach | Result | Why |
|----------|--------|-----|
| `pandoc --pdf-engine=xelatex` | Fails | xelatex not installed; requires MacTeX (~5GB) |
| `pandoc --pdf-engine=weasyprint` | Fails | WeasyPrint lacks MathJax; prints raw LaTeX |
| `pandoc --mathjax + Chrome Headless` | Fails | Chrome prints before MathJax async render completes |
| `pandoc --mathjax + Playwright` | Works but complex | Requires playwright install; overkill for this use case |
| Obsidian native export | **Perfect** | Built-in MathJax engine; zero setup |

## Scripts

- `flow/script/merge_course_md.py` — Merge chapters into single MD for Obsidian export
- `flow/script/md_to_pdf.py` — Pandoc + Chrome Headless (backup; MathJax timing issues)
- `flow/script/md_to_pdf_playwright.py` — Pandoc + Playwright with MathJax wait (backup; works but heavy)

## Key Lesson

When the user already has a working native export path (Obsidian), do NOT recommend installing external toolchains. The simplest solution is to prepare the input (merged MD) and let the user's existing tool handle the output.
