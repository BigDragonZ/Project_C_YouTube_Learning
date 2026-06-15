#!/usr/bin/env python3
"""
Export course notes to PDF (A4 format) for printing.

Usage:
    uv run flow/script/export_pdf.py <course_name>
"""

import argparse
import sys
from pathlib import Path

import markdown
from weasyprint import HTML, CSS


def build_html(course_name: str, perm_dir: Path) -> str:
    """Build combined HTML from all markdown files."""
    
    # Order: syllabus -> chapters -> MOC -> Anki
    files = []
    
    # Syllabus
    syllabus = perm_dir / f"{course_name}_课程大纲.md"
    if syllabus.exists():
        files.append(("课程大纲", syllabus))
    
    # Chapters
    for ch_file in sorted(perm_dir.glob("Ch_*.md")):
        title = ch_file.stem.replace("Ch_", "第").replace("_", " ")
        files.append((title, ch_file))
    
    # MOC
    moc = perm_dir / f"{course_name}_知识地图_MOC.md"
    if moc.exists():
        files.append(("知识地图 MOC", moc))
    
    # Anki
    anki = list(perm_dir.glob("Anki_*.md"))
    if anki:
        files.append(("Anki 记忆卡片", anki[0]))
    
    # Build HTML
    md = markdown.Markdown(extensions=['tables', 'fenced_code', 'toc'])
    
    parts = []
    parts.append(f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{course_name}</title>
<style>
@page {{
    size: A4;
    margin: 2cm;
    @bottom-center {{
        content: counter(page);
        font-size: 10pt;
    }}
}}
body {{
    font-family: "Noto Sans CJK SC", "PingFang SC", "Microsoft YaHei", sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #333;
}}
h1 {{
    font-size: 20pt;
    color: #1a1a1a;
    border-bottom: 2px solid #333;
    padding-bottom: 10px;
    margin-top: 30px;
    page-break-before: always;
}}
h1:first-of-type {{
    page-break-before: avoid;
}}
h2 {{
    font-size: 14pt;
    color: #2a2a2a;
    margin-top: 20px;
    border-bottom: 1px solid #ddd;
    padding-bottom: 5px;
}}
h3 {{
    font-size: 12pt;
    color: #444;
    margin-top: 15px;
}}
strong {{
    color: #000;
    font-weight: bold;
}}
code {{
    background: #f4f4f4;
    padding: 2px 5px;
    border-radius: 3px;
    font-family: "Courier New", monospace;
    font-size: 10pt;
}}
pre {{
    background: #f4f4f4;
    padding: 10px;
    border-radius: 5px;
    overflow-x: auto;
    font-size: 9pt;
}}
blockquote {{
    border-left: 3px solid #666;
    margin-left: 0;
    padding-left: 15px;
    color: #555;
    font-style: italic;
}}
table {{
    border-collapse: collapse;
    width: 100%;
    margin: 15px 0;
    font-size: 10pt;
}}
th, td {{
    border: 1px solid #ddd;
    padding: 8px;
    text-align: left;
}}
th {{
    background: #f0f0f0;
    font-weight: bold;
}}
ul, ol {{
    margin: 10px 0;
    padding-left: 25px;
}}
li {{
    margin: 5px 0;
}}
.page-break {{
    page-break-after: always;
}}
.cover {{
    text-align: center;
    padding-top: 200px;
}}
.cover h1 {{
    font-size: 28pt;
    border: none;
    page-break-before: avoid;
}}
.cover p {{
    font-size: 14pt;
    color: #666;
    margin-top: 30px;
}}
</style>
</head>
<body>
<div class="cover">
    <h1>{course_name.replace('_', ' ')}</h1>
    <p>MIT 14.01 Principles of Microeconomics</p>
    <p>Generated: 2026-05-15</p>
    <p style="margin-top: 100px; font-size: 10pt; color: #999;">DALONG ZHANG</p>
</div>
""")
    
    for title, filepath in files:
        content = filepath.read_text(encoding="utf-8")
        html_content = md.convert(content)
        md.reset()
        
        parts.append(f'<h1>{title}</h1>\n')
        parts.append(html_content)
        parts.append('\n<div class="page-break"></div>\n')
    
    parts.append('</body></html>')
    
    return '\n'.join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export course notes to PDF")
    parser.add_argument("course", help="Course name")
    args = parser.parse_args()

    perm_dir = Path("output") / args.course
    if not perm_dir.exists():
        print(f"[ERROR] Directory not found: {perm_dir}")
        return 1

    print(f"[INFO] Building HTML for {args.course}...")
    html_content = build_html(args.course, perm_dir)

    output_path = perm_dir / f"{args.course}_打印版.pdf"
    
    print(f"[INFO] Generating PDF...")
    HTML(string=html_content).write_pdf(str(output_path))
    
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"[OK] PDF saved: {output_path}")
    print(f"[INFO] Size: {size_mb:.1f} MB")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
