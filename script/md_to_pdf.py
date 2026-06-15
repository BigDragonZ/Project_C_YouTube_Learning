#!/usr/bin/env python3
"""
Markdown to PDF converter using Pandoc + MathJax + Headless Chrome.
Matches Obsidian's formula rendering exactly.

Usage:
    uv run input/script/md_to_pdf.py input.md [output.pdf]
    uv run input/script/md_to_pdf.py output/CourseName/Ch_01.md
"""

import subprocess
import sys
import tempfile
import os
from pathlib import Path


def md_to_pdf(md_path: str, pdf_path: str | None = None) -> str:
    md_file = Path(md_path).resolve()
    if not md_file.exists():
        raise FileNotFoundError(f"Markdown file not found: {md_file}")

    if pdf_path is None:
        pdf_path = str(md_file.with_suffix(".pdf"))
    else:
        pdf_path = str(Path(pdf_path).resolve())

    # Step 1: Pandoc converts Markdown to HTML with MathJax
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
        html_path = f.name

    pandoc_cmd = [
        "pandoc",
        str(md_file),
        "-o", html_path,
        "--standalone",
        "--mathjax",
        "--css", "https://cdn.jsdelivr.net/npm/github-markdown-css/github-markdown.min.css",
        "-V", "lang=zh-CN",
    ]

    print(f"[1/3] Running pandoc: {' '.join(pandoc_cmd)}")
    result = subprocess.run(pandoc_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        os.unlink(html_path)
        raise RuntimeError(f"Pandoc failed:\n{result.stderr}")

    # Step 2: Inject MathJax config to match Obsidian's behavior
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Replace default MathJax with Obsidian-compatible config
    obsidian_mathjax = """
    <script>
    window.MathJax = {
        tex: {
            inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
            displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
            processEscapes: true,
            processEnvironments: true,
        },
        options: {
            skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre']
        }
    };
    </script>
    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; padding: 40px; max-width: 900px; margin: 0 auto; }
        .math.display { overflow-x: auto; }
    </style>
    """

    # Remove default mathjax script and inject ours
    import re
    html = re.sub(r'<script[^>]*mathjax[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    html = re.sub(r'<script[^>]*tex-chtml[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    html = html.replace("</head>", obsidian_mathjax + "\n</head>")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    # Step 3: Headless Chrome prints HTML to PDF
    # Use --virtual-time-budget to wait for MathJax async rendering
    chrome_cmd = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-software-rasterizer",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=10000",  # 10s for MathJax rendering
        "--print-to-pdf-no-header",
        f"--print-to-pdf={pdf_path}",
        f"file://{html_path}",
    ]

    print(f"[2/3] Rendering with Chrome: {pdf_path}")
    result = subprocess.run(chrome_cmd, capture_output=True, text=True)

    # Cleanup
    os.unlink(html_path)

    if result.returncode != 0:
        raise RuntimeError(f"Chrome failed:\n{result.stderr}")

    print(f"[3/3] Done: {pdf_path}")
    return str(pdf_path)


def main():
    if len(sys.argv) < 2:
        print("Usage: md_to_pdf.py <input.md> [output.pdf]")
        sys.exit(1)

    md_path = sys.argv[1]
    pdf_path = sys.argv[2] if len(sys.argv) > 2 else None

    md_to_pdf(md_path, pdf_path)


if __name__ == "__main__":
    main()
