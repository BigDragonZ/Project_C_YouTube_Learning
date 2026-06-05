"""YouTube operations: playlist parsing, subtitle download, audio extraction, SRT parsing."""

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional


@dataclass
class SubtitleEntry:
    """Structured subtitle entry with timestamps."""

    index: int
    start: str
    end: str
    text: str


class YouTubeTool:
    """封装 yt-dlp 调用，支持字幕下载、播放列表解析、视频信息获取。"""

    def __init__(self, yt_dlp_path: Optional[str] = None, use_cookies: bool = True):
        if yt_dlp_path is None:
            # Lazy import to avoid circular dependency
            from config import get_config
            cfg = get_config()
            yt_dlp_path = cfg.get("api", "yt_dlp_path", default=".venv/bin/yt-dlp")
        self.yt_dlp_path = yt_dlp_path
        self.use_cookies = use_cookies

    def _run(self, args: List[str], timeout: int = 120) -> subprocess.CompletedProcess:
        """Run yt-dlp with optional cookies."""
        cmd = [self.yt_dlp_path]
        if self.use_cookies:
            cmd.extend(["--cookies-from-browser", "chrome"])
        cmd.extend(["--no-warnings"] + args)
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    def fetch_title(self, url: str) -> str:
        """获取视频标题。"""
        result = self._run([
            "--print", "%(title)s",
            "--skip-download",
            url,
        ])
        if result.returncode != 0:
            raise RuntimeError(f"fetch_title failed: {result.stderr}")
        return result.stdout.strip()

    def get_playlist_info(self, url: str) -> dict:
        """获取播放列表信息（标题、视频数、时长）。"""
        try:
            result = subprocess.run(
                [self.yt_dlp_path, "--flat-playlist", "--dump-single-json", url],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                return {"error": result.stderr}
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

    def fetch_playlist(self, url: str) -> tuple[str, List[dict[str, Any]]]:
        """获取播放列表标题和视频列表（去重）。"""
        result = self._run([
            "--flat-playlist",
            "-j",
            "--skip-download",
            url,
        ], timeout=60)
        if result.returncode != 0 or not result.stdout.strip():
            raise RuntimeError(f"fetch_playlist failed: {result.stderr[:200]}")

        lines = result.stdout.strip().split("\n")
        first = json.loads(lines[0])
        playlist_title = first.get("playlist_title", "Unknown")
        seen: set[str] = set()
        videos: List[dict[str, Any]] = []

        for line in lines:
            if not line:
                continue
            data = json.loads(line)
            video_url = data.get("url") or data.get("webpage_url", "")
            if not video_url or video_url in seen:
                continue
            seen.add(video_url)
            videos.append({
                "id": data.get("id", ""),
                "title": data.get("title", "Unknown"),
                "url": video_url,
                "index": len(videos) + 1,
            })

        return playlist_title, videos

    def download_subtitles(self, url: str, output_dir: Path, lang: str = "en") -> List[Path]:
        """下载自动字幕并转换为 srt。"""
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._run([
                "--write-auto-subs",
                "--sub-langs", lang,
                "--convert-subs", "srt",
                "--skip-download",
                "--output", str(output_dir / "%(playlist_index)s"),
                url,
            ], timeout=300)
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

    @staticmethod
    def _remove_overlap(prev: str, curr: str) -> str:
        """Remove overlapping prefix from curr that appears at end of prev."""
        prev = prev.strip()
        curr = curr.strip()
        for i in range(min(len(prev), len(curr)), 0, -1):
            if prev[-i:].lower() == curr[:i].lower():
                return curr[i:].strip()
        return curr

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

    def parse_srt_entries(self, content: str) -> List[SubtitleEntry]:
        """Parse SRT content into structured entries with overlap deduplication."""
        blocks = content.strip().split("\n\n")
        entries: List[SubtitleEntry] = []
        prev_text = ""

        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) < 3:
                continue

            try:
                idx = int(lines[0].strip())
            except ValueError:
                continue

            time_match = re.match(
                r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})",
                lines[1],
            )
            if not time_match:
                continue

            text = (
                " ".join(lines[2:])
                .replace("\r", "")
                .replace("<b>", "").replace("</b>", "")
                .replace("<i>", "").replace("</i>", "")
                .replace("<u>", "").replace("</u>", "")
                .replace("[music]", "").replace("[Music]", "")
                .replace("[音楽]", "").replace("♪", "")
                .strip()
            )

            if not text:
                continue

            text = self._remove_overlap(prev_text, text)
            if not text:
                continue

            prev_text = text
            entries.append(SubtitleEntry(idx, time_match.group(1), time_match.group(2), text))

        return entries

    @staticmethod
    def to_markdown(
        entries: List[SubtitleEntry],
        meta: dict[str, Any],
    ) -> str:
        """Convert subtitle entries to Markdown with timestamps."""
        lines = [
            f"# {meta['title']}",
            "",
            "## 元信息",
            "",
            f"- **序号**: {meta['index']}",
            f"- **课程**: {meta['course']}",
            f"- **链接**: {meta['url']}",
            f"- **处理时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "- **来源**: YouTube 自动生成字幕",
            f"- **条目数**: {len(entries)}",
            "",
            "---",
            "",
            "## 字幕内容",
            "",
        ]

        for entry in entries:
            lines.append(f"**[{entry.start} - {entry.end}]** {entry.text}")
            lines.append("")

        return "\n".join(lines)
