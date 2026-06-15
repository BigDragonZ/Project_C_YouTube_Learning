#!/usr/bin/env python3
"""
Markdown to PDF using Pandoc + MathJax + Playwright.
Waits for MathJax rendering to complete before printing.

Usage:
    uv run flow/script/md_to_pdf_playwright.py input.md [output.pdf]
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

    print(f"[1/3] Running pandoc...")
    result = subprocess.run(pandoc_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        os.unlink(html_path)
        raise RuntimeError(f"Pandoc failed:\n{result.stderr}")

    # Step 2: Use Playwright to render and print PDF
    print(f"[2/3] Rendering with Playwright (waiting for MathJax)...")

    playwright_script = f"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("file://{html_path}")

        # Wait for MathJax to finish rendering
        try:
            await page.wait_for_function("() => typeof MathJax !== 'undefined' && MathJax.startup && MathJax.startup.promise", timeout=5000)
            await page.evaluate("async () => await MathJax.startup.promise")
            await page.wait_for_timeout(500)  # Extra buffer
            print("MathJax rendered successfully")
        except Exception as e:
            print(f"MathJax wait warning: {{e}}")
            await page.wait_for_timeout(3000)  # Fallback wait

        await page.pdf(
            path="{pdf_path}",
            format="A4",
            margin={{"top": "2cm", "bottom": "2cm", "left": "2cm", "right": "2cm"}},
            print_background=True,
        )
        await browser.close()
        print("PDF exported")

asyncio.run(main())
"""

    result = subprocess.run(
        [sys.executable, "-c", playwright_script],
        capture_output=True,
        text=True,
    )

    os.unlink(html_path)

    if result.returncode != 0:
        raise RuntimeError(f"Playwright failed:\n{result.stderr}\n{result.stdout}")

    print(f"[3/3] Done: {pdf_path}")
    return pdf_path


def main():
    if len(sys.argv) < 2:
        print("Usage: md_to_pdf_playwright.py <input.md> [output.pdf]")
        sys.exit(1)

    md_path = sys.argv[1]
    pdf_path = sys.argv[2] if len(sys.argv) > 2 else None
    md_to_pdf(md_path, pdf_path)


if __name__ == "__main__":
    main()
