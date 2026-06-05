"""YouTube operations: playlist parsing, subtitle download, audio extraction."""

import re
import subprocess
from pathlib import Path
from typing import List, Optional


class YouTubeTool:
    """封装 yt-dlp 调用，支持字幕下载、播放列表解析、视频信息获取。"""

    def __init__(self, yt_dlp_path: str = ".venv/bin/yt-dlp"):
        self.yt_dlp_path = yt_dlp_path

    def get_playlist_info(self, url: str) -> dict:
        """获取播放列表信息（标题、视频数、时长）。"""
        try:
            result = subprocess.run(
                [self.yt_dlp_path, "--flat-playlist", "--dump-single-json", url],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                return {"error": result.stderr}
            import json
            data = json.loads(result.stdout)
            entries = data.get("entries", [])
            total_duration = sum(e.get("duration", 0) for e in entries)
            return {
                "title": data.get("title", "Unknown"),
                "video_count": len(entries),
                "total_duration": total_duration,
            }
        except Exception as e:
            return {"error": str(e)}

    def download_subtitles(self, url: str, output_dir: Path, lang: str = "en") -> List[Path]:
        """下载自动字幕并转换为 srt。"""
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                [
                    self.yt_dlp_path,
                    "--write-auto-subs",
                    "--sub-langs", lang,
                    "--convert-subs", "srt",
                    "--skip-download",
                    "--output", str(output_dir / "%(playlist_index)s"),
                    url,
                ],
                capture_output=True, text=True, timeout=300,
            )
            return sorted(output_dir.glob("*.srt"))
        except Exception:
            return []

    def download_audio(self, url: str, output_path: Path) -> Optional[Path]:
        """下载视频并提取音频。"""
        try:
            subprocess.run(
                [
                    self.yt_dlp_path,
                    "--extract-audio",
                    "--audio-format", "mp3",
                    "--audio-quality", "64K",
                    "--output", str(output_path.with_suffix("")) + ".%(ext)s",
                    url,
                ],
                capture_output=True, text=True, timeout=300,
            )
            mp3 = output_path.with_suffix(".mp3")
            return mp3 if mp3.exists() else None
        except Exception:
            return None

    def parse_srt(self, srt_path: Path) -> str:
        """解析 srt 文件，去除重叠和重复文本。"""
        if not srt_path.exists():
            return ""
        content = srt_path.read_text(encoding="utf-8")
        blocks = re.split(r"\n\s*\n", content.strip())
        texts = []
        prev_text = ""
        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) >= 3:
                text = " ".join(lines[2:])
                text = re.sub(r"\r+", " ", text)
                text = re.sub(r"\s+", " ", text).strip()
                # Overlap removal
                for i in range(min(len(prev_text), len(text)), 0, -1):
                    if prev_text[-i:] == text[:i]:
                        text = text[i:].strip()
                        break
                if text and text not in ("[Music]", ""):
                    texts.append(text)
                    prev_text = text
        return " ".join(texts)
