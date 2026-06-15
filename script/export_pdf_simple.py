#!/usr/bin/env python3
"""
Export course notes to PDF using reportlab (A4 format).

Usage:
    uv run flow/script/export_pdf_simple.py <course_name>
"""

import argparse
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import markdown


def register_fonts():
    """Register Chinese fonts."""
    # Try common macOS Chinese fonts
    font_paths = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
    ]
    
    for font_path in font_paths:
        if Path(font_path).exists():
            try:
                pdfmetrics.registerFont(TTFont('ChineseFont', font_path))
                return 'ChineseFont'
            except:
                continue
    
    # Fallback to Helvetica
    return 'Helvetica'


def md_to_paragraphs(md_text: str, styles) -> list:
    """Convert markdown text to reportlab flowables."""
    md = markdown.Markdown(extensions=['tables'])
    html = md.convert(md_text)
    
    # Simple HTML to paragraph conversion
    elements = []
    lines = md_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            elements.append(Spacer(1, 0.3*cm))
            continue
            
        # Headers
        if line.startswith('# '):
            elements.append(Paragraph(line[2:], styles['Heading1']))
        elif line.startswith('## '):
            elements.append(Paragraph(line[3:], styles['Heading2']))
        elif line.startswith('### '):
            elements.append(Paragraph(line[4:], styles['Heading3']))
        elif line.startswith('#### '):
            elements.append(Paragraph(line[5:], styles['Heading4']))
        # Bullet points
        elif line.startswith('- ') or line.startswith('* '):
            elements.append(Paragraph('• ' + line[2:], styles['BodyText']))
        # Numbered lists
        elif line[0].isdigit() and '. ' in line[:4]:
            elements.append(Paragraph(line, styles['BodyText']))
        # Bold text
        elif '**' in line:
            # Simple bold conversion
            line = line.replace('**', '<b>').replace('**', '</b>', 1)
            elements.append(Paragraph(line, styles['BodyText']))
        else:
            elements.append(Paragraph(line, styles['BodyText']))
    
    return elements


def build_pdf(course_name: str, perm_dir: Path, output_path: Path):
    """Build PDF from markdown files."""
    
    font_name = register_fonts()
    
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
    )
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Update styles with Chinese font
    for style_name in ['Normal', 'BodyText', 'Heading1', 'Heading2', 'Heading3', 'Heading4']:
        if style_name in styles:
            styles[style_name].fontName = font_name
    
    styles['Heading1'].fontSize = 18
    styles['Heading1'].spaceAfter = 12
    styles['Heading2'].fontSize = 14
    styles['Heading2'].spaceAfter = 10
    styles['Heading3'].fontSize = 12
    styles['Heading3'].spaceAfter = 8
    styles['BodyText'].fontSize = 10
    styles['BodyText'].leading = 14
    
    story = []
    
    # Cover page
    story.append(Spacer(1, 8*cm))
    story.append(Paragraph(course_name.replace('_', ' '), styles['Heading1']))
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph("MIT 14.01 Principles of Microeconomics", styles['Heading2']))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("Generated: 2026-05-15", styles['BodyText']))
    story.append(Spacer(1, 4*cm))
    story.append(Paragraph("DALONG ZHANG", styles['BodyText']))
    story.append(PageBreak())
    
    # Collect files
    files = []
    syllabus = perm_dir / f"{course_name}_课程大纲.md"
    if syllabus.exists():
        files.append(("课程大纲", syllabus))
    
    for ch_file in sorted(perm_dir.glob("Ch_*.md")):
        title = ch_file.stem.replace("Ch_", "第").replace("_", " ")
        files.append((title, ch_file))
    
    moc = perm_dir / f"{course_name}_知识地图_MOC.md"
    if moc.exists():
        files.append(("知识地图 MOC", moc))
    
    anki = list(perm_dir.glob("Anki_*.md"))
    if anki:
        files.append(("Anki 记忆卡片", anki[0]))
    
    # Add content
    for title, filepath in files:
        story.append(Paragraph(title, styles['Heading1']))
        story.append(Spacer(1, 0.5*cm))
        
        content = filepath.read_text(encoding="utf-8")
        elements = md_to_paragraphs(content, styles)
        story.extend(elements)
        story.append(PageBreak())
    
    doc.build(story)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export course notes to PDF")
    parser.add_argument("course", help="Course name")
    args = parser.parse_args()

    perm_dir = Path("output") / args.course
    if not perm_dir.exists():
        print(f"[ERROR] Directory not found: {perm_dir}")
        return 1

    output_path = perm_dir / f"{args.course}_打印版.pdf"
    
    print(f"[INFO] Generating PDF for {args.course}...")
    build_pdf(args.course, perm_dir, output_path)
    
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"[OK] PDF saved: {output_path}")
    print(f"[INFO] Size: {size_mb:.1f} MB")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
