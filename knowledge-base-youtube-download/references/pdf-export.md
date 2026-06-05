# PDF Export for Knowledge Base Notes

Session: 2026-05-15 — Exporting generated markdown notes to A4 PDF for printing.

## Problem

After generating structured markdown notes (syllabus, chapters, MOC, Anki), users need a printable format. Manual conversion is tedious and loses formatting.

## Solution: Pandoc + WeasyPrint Pipeline

A Python script that converts all `.md` files in a directory to a single A4 PDF with proper typography.

### Dependencies

```bash
brew install pandoc
brew install pango gdk-pixbuf libffi  # WeasyPrint system deps on macOS
uv pip install weasyprint             # Python PDF renderer
```

**CRITICAL**: WeasyPrint requires GObject/Pango libraries. On macOS, set `DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH` before running if WeasyPrint fails with `cannot load library 'libgobject-2.0-0'`.

### Script: `flow/script/export_pdf.py`

```python
#!/usr/bin/env python3
"""Export Markdown notes to A4 PDF for printing."""
import sys
from pathlib import Path
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

A4_CSS = """
@page { size: A4; margin: 2cm; @bottom-center { content: counter(page); font-size: 9pt; color: #666; } }
body { font-family: "Noto Serif CJK SC", "Source Han Serif SC", "Songti SC", serif; font-size: 11pt; line-height: 1.8; }
h1 { font-size: 18pt; border-bottom: 2px solid #333; page-break-before: always; }
h1:first-of-type { page-break-before: auto; }
h2 { font-size: 14pt; margin-top: 1.5em; }
h3 { font-size: 12pt; margin-top: 1.2em; }
p { text-align: justify; }
code { font-family: monospace; background: #f4f4f4; padding: 0.1em 0.3em; }
pre { background: #f8f8f8; border: 1px solid #ddd; padding: 0.8em; white-space: pre-wrap; }
blockquote { border-left: 4px solid #ccc; background: #f9f9f9; padding: 0.5em 1em; }
table { width: 100%; border-collapse: collapse; font-size: 10pt; }
th, td { border: 1px solid #ddd; padding: 0.5em; }
th { background: #f0f0f0; }
img { max-width: 100%; height: auto; margin: 1em auto; display: block; }
"""

def md_to_html(md_path: Path) -> str:
    import subprocess
    result = subprocess.run(
        ["pandoc", "-f", "markdown", "-t", "html", "--mathjax", str(md_path)],
        capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode != 0:
        raise RuntimeError(f"pandoc failed: {result.stderr}")
    return result.stdout

def build_combined_html(md_files: list[Path], title: str) -> str:
    bodies = []
    for f in md_files:
        bodies.append(f"<h1>{f.stem}</h1>")
        bodies.append(md_to_html(f))
    return f"<!DOCTYPE html><html><head><meta charset='UTF-8'><title>{title}</title></head><body>{chr(10).join(bodies)}</body></html>"

def main():
    input_dir = Path(sys.argv[1]).resolve()
    output_dir = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else input_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    md_files = sorted(input_dir.glob("*.md"))
    if not md_files:
        print(f"No .md files found in {input_dir}")
        sys.exit(1)

    course_name = input_dir.name
    output_pdf = output_dir / f"{course_name}_打印版.pdf"

    html_content = build_combined_html(md_files, course_name)
    font_config = FontConfiguration()
    HTML(string=html_content).write_pdf(
        str(output_pdf),
        stylesheets=[CSS(string=A4_CSS, font_config=font_config)],
        font_config=font_config
    )
    print(f"Done: {output_pdf} ({output_pdf.stat().st_size / 1024:.1f} KB)")

if __name__ == "__main__":
    main()
```

### Usage

```bash
uv run flow/script/export_pdf.py 01_Permanent/<CourseName>
```

Output: `01_Permanent/<CourseName>/<CourseName>_打印版.pdf`

### Features

- **A4 page size** with 2cm margins
- **Auto page numbering** in footer
- **Page break before each chapter** (each `.md` file starts on a new page)
- **Chinese font support** via Noto Serif CJK SC fallback chain
- **LaTeX math rendering** via pandoc `--mathjax`
- **Code blocks, tables, blockquotes** styled for print readability
- **All files merged** into single PDF for easy printing

## Pitfalls

### Pitfall: WeasyPrint Missing System Libraries

**Error**: `OSError: cannot load library 'libgobject-2.0-0'`

**Fix**:
```bash
brew install pango gdk-pixbuf libffi
export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH
```

### Pitfall: pandoc Not Installed

**Error**: `FileNotFoundError: pandoc`

**Fix**: `brew install pandoc`

### Pitfall: Large File Count

With 20+ markdown files, the combined HTML can be large. WeasyPrint handles this fine but may take 30-60s. No action needed.

### Pitfall: LaTeX Math Rendering Failure in PDF

**Symptoms**: Pandoc converts `$...$` and `$$...$$` to `<span class="math inline">\(...\)</span>` / `<span class="math display">\[...\]</span>`, but WeasyPrint does NOT execute MathJax — it renders the raw LaTeX source as plain text. Formulas like `$$VMPL = P \times MPL$$` appear as unrendered LaTeX code in the PDF.

**Root cause**: WeasyPrint is a static HTML/CSS renderer. It does not execute JavaScript, so MathJax (which is a JS library) never runs. The math markup stays as raw text.

**Fix — Use LaTeX backend (xelatex) instead of WeasyPrint:**

1. **Install MacTeX or BasicTeX**:
   ```bash
   brew install --cask basictex   # ~2GB, recommended
   # OR
   brew install --cask mactex     # ~5GB, full features
   ```

2. **Install required LaTeX packages** (BasicTeX only):
   ```bash
   sudo tlmgr install ctex xecjk fontspec unicode-math amsmath amssymb graphicx geometry hyperref
   ```

3. **Export with xelatex**:
   ```bash
   pandoc input.md -o output.pdf \
     --pdf-engine=xelatex \
     -V CJKmainfont="PingFang SC" \
     -V geometry:margin=2.5cm
   ```

**Why xelatex works**: It natively parses LaTeX math (`$...$`, `$$...$$`) via the `unicode-math` package, producing properly typeset formulas without JavaScript.

**Why WeasyPrint fails**: It only renders HTML+CSS. MathJax requires a browser engine (Chromium, WebKit) to execute JS and render math to DOM/SVG. WeasyPrint has no JS engine.

**Alternative — Browser-based rendering**:
If you cannot install MacTeX, generate an HTML file with MathJax and print from Chrome:
```bash
pandoc input.md -o output.html --mathjax --standalone
# Open in Chrome → Print → Save as PDF
```

**Verification**: After xelatex export, check that formulas like `\frac{MU_x}{P_x}` render as stacked fractions, not raw LaTeX strings.

## Related

- Entry script: `~/Documents/all-in-one/flow/script/export_pdf.py`
- Generated PDF example: `~/Documents/all-in-one/01_Permanent/Principles_of_Microeconomics/Principles_of_Microeconomics_打印版.pdf`
