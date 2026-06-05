"""YouTube operations: playlist info, subtitle download, audio extraction."""

import re
import subprocess
from pathlib import Path
from typing import List, Optional

from ..config import get_config


class YouTubeTool:
    """Wrapper for yt-dlp operations."""

    def __init__(self, yt_dlp_path: Optional[str] = None):
        cfg = get_config()
        self.yt_dlp_path = yt_dlp_path or cfg.get("api", "yt_dlp_path", default=".venv/bin/yt-dlp")

    def _run(self, args: List[str]) -> subprocess.CompletedProcess:
        cmd = [self.yt_dlp_path] + args
        return subprocess.run(cmd, capture_output=True, text=True)

    def get_playlist_info(self, url: str) -> dict:
        """Fetch playlist metadata: title, video count, total duration."""
        result = self._run([
            "--flat-playlist", "--dump-single-json",
            "--cookies-from-browser", "chrome",
            url,
        ])
        if result.returncode != 0:
            raise RuntimeError(f"yt-dlp failed: {result.stderr}")
        import json
        data = json.loads(result.stdout)
        entries = data.get("entries", [])
        total_duration = sum(e.get("duration", 0) for e in entries)
        return {
            "title": data.get("title", "Unknown"),
            "video_count": len(entries),
            "total_duration": total_duration,
            "duration_formatted": f"{total_duration // 3600}h{(total_duration % 3600) // 60}m",
        }

    def download_subtitles(self, url: str, output_dir: Path, lang: str = "en") -> List[Path]:
        """Download auto-generated subtitles to SRT files."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        result = self._run([
            "--cookies-from-browser", "chrome",
            "--write-auto-subs", "--sub-langs", lang,
            "--convert-subs", "srt",
            "--skip-download",
            "--output", str(output_dir / "%(playlist_index)s"),
            url,
        ])
        if result.returncode != 0:
            raise RuntimeError(f"Subtitle download failed: {result.stderr}")
        return sorted(output_dir.glob("*.srt"))

    def download_audio(self, url: str, output_path: Path) -> Path:
        """Download video and extract audio as MP3."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result = self._run([
            "--cookies-from-browser", "chrome",
            "--format", "bestaudio/best",
            "--extract-audio", "--audio-format", "mp3",
            "--audio-quality", "64K",
            "--output", str(output_path.with_suffix("")) + ".%(ext)s",
            url,
        ])
        if result.returncode != 0:
            raise RuntimeError(f"Audio download failed: {result.stderr}")
        return output_path.with_suffix(".mp3")

    def parse_srt(self, srt_path: Path) -> str:
        """Parse SRT file, remove overlaps and duplicates."""
        content = srt_path.read_text(encoding="utf-8")
        blocks = re.split(r"\n\s*\n", content.strip())
        texts = []
        prev_text = None
        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) >= 3:
                text = " ".join(lines[2:])
                text = re.sub(r"<[^>]+>", "", text)
                text = re.sub(r"\[Music\]|♪", "", text).strip()
                # Remove overlap: if text starts with prev_text suffix
                if prev_text:
                    for i in range(min(len(prev_text), len(text)), 0, -1):
                        if prev_text[-i:] == text[:i]:
                            text = text[i:].strip()
                            break
                if text and text != prev_text:
                    texts.append(text)
                    prev_text = text
        return " ".join(texts)
