#!/usr/bin/env python3
"""
Transcribe audio file using GCP Vertex AI or Gemini.

Usage:
    python flow/script/transcribe_audio.py <AUDIO_PATH> <COURSE_NAME> <INDEX>

Environment:
    gcp-vertex-key    : GCP Vertex AI API key
    GEMINI_API_KEY    : Gemini standard API key
    TRANSCRIBER       : Explicit backend (gcp-vertex | gemini), null = auto
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from config.paths import course_dir, build_filename
from lib.transcribe import transcribe_audio


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe audio to text")
    parser.add_argument("audio", help="Input audio file path")
    parser.add_argument("course", help="Course name (directory under flow/)")
    parser.add_argument("index", type=int, help="Video sequence number")
    args = parser.parse_args()

    if not Path(args.audio).exists():
        print(f"[ERROR] Audio file not found: {args.audio}", file=sys.stderr)
        return 1

    out_dir = course_dir(args.course)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Audio:  {args.audio}")
    print(f"[INFO] Course: {args.course}")
    print(f"[INFO] Index:  {args.index}")
    print(f"[INFO] Output: {out_dir}")

    try:
        result = transcribe_audio(args.audio)

        filename = build_filename(args.index, f"Transcription {args.course}", "md")
        output_path = out_dir / filename

        content = f"""# Transcription

## 元信息

- **序号**: {args.index}
- **课程**: {args.course}
- **音频**: {args.audio}
- **后端**: {result['backend']}
- **模型**: {result['model']}
- **处理时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 转写内容

{result['text']}
"""

        output_path.write_text(content, encoding="utf-8")

        print(f"[SUCCESS] Transcription saved to: {output_path}")
        print(f"[INFO] Backend: {result['backend']}")
        print(f"[INFO] Model:   {result['model']}")
        print(f"[INFO] Chars:   {len(result['text'])}")
        return 0

    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
