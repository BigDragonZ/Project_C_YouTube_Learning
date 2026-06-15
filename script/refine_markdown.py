#!/usr/bin/env python3
"""
Refine a Markdown file using Gemini.

Usage:
    python flow/script/refine_markdown.py <INPUT_MD> [OUTPUT_MD]

Example:
    python flow/script/refine_markdown.py \
        "flow/Valuation_Undergrad_2022/01-Transcription Valuation_Undergrad_2022.md" \
        "flow/Valuation_Undergrad_2022/01-Refined.md"
"""

import argparse
import sys
from pathlib import Path

from lib.refine import refine_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description="Refine Markdown with Gemini")
    parser.add_argument("input", help="Input Markdown file")
    parser.add_argument("output", nargs="?", help="Output file (default: input_refined.md)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] Input not found: {input_path}", file=sys.stderr)
        return 1

    output_path = Path(args.output) if args.output else input_path.with_suffix(".refined.md")

    print(f"[INFO] Input:  {input_path}")
    print(f"[INFO] Output: {output_path}")

    try:
        content = input_path.read_text(encoding="utf-8")
        
        # Extract only the transcription content (after "## 转写内容")
        if "## 转写内容" in content:
            parts = content.split("## 转写内容", 1)
            header = parts[0] + "## 转写内容\n\n"
            body = parts[1].strip()
        else:
            header = ""
            body = content

        refined_body = refine_markdown(body)
        output_path.write_text(header + refined_body, encoding="utf-8")
        print(f"[INFO] Input chars:  {len(body)}")
        print(f"[INFO] Output chars: {len(refined_body)}")
        return 0

    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
