"""
YouTube operations: title fetch, subtitle download, SRT parsing, Markdown conversion.
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Any, List, Optional

from config.paths import BINARIES

YTDLP = BINARIES["yt_dlp"]


def _run_ytdlp(args: List[str], timeout: int = 120) -> subprocess.CompletedProcess:
    """Run yt-dlp with given args."""
    cmd = [YTDLP] + args
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def fetch_title(url: str) -> str:
    """Fetch video title from URL."""
    result = _run_ytdlp([
        "--cookies-from-browser", "chrome",
        "--no-warnings",
        "--print", "%(title)s",
        "--skip-download",
        url,
    ])
    if result.returncode != 0:
        raise RuntimeError(f"fetch_title failed: {result.stderr}")
    return result.stdout.strip()


def fetch_playlist(url: str) -> tuple[str, List[dict[str, Any]]]:
    """Fetch playlist title and video list."""
    result = _run_ytdlp([
        "--cookies-from-browser", "chrome",
        "--flat-playlist",
        "-j",
        "--no-warnings",
        url,
    ])
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


def download_subtitle(url: str, temp_base: str) -> str:
    """Download auto-generated English subtitle, return SRT file path."""
    result = _run_ytdlp([
        "--cookies-from-browser", "chrome",
        "--no-warnings",
        "--write-auto-subs",
        "--skip-download",
        "--sub-langs", "en",
        "--convert-subs", "srt",
        "--output", temp_base,
        url,
    ])

    if result.returncode != 0 and "Downloading" not in result.stderr:
        raise RuntimeError(f"yt-dlp exited {result.returncode}: {result.stderr}")

    srt_file = f"{temp_base}.en.srt"
    if Path(srt_file).exists():
        return srt_file

    alt = f"{temp_base}.srt"
    if Path(alt).exists():
        return alt

    raise FileNotFoundError(f"Subtitle file not found: {srt_file}")


class SubtitleEntry:
    def __init__(self, index: int, start: str, end: str, text: str):
        self.index = index
        self.start = start
        self.end = end
        self.text = text


def _remove_overlap(prev: str, curr: str) -> str:
    """Remove overlapping prefix from curr that appears at end of prev."""
    prev = prev.strip()
    curr = curr.strip()
    # Find longest suffix of prev that matches prefix of curr
    for i in range(min(len(prev), len(curr)), 0, -1):
        if prev[-i:].lower() == curr[:i].lower():
            return curr[i:].strip()
    return curr


def parse_srt(content: str) -> List[SubtitleEntry]:
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

        # Remove overlap with previous entry text
        text = _remove_overlap(prev_text, text)
        if not text:
            continue

        prev_text = text
        entries.append(SubtitleEntry(idx, time_match.group(1), time_match.group(2), text))

    return entries


def to_markdown(
    entries: List[SubtitleEntry],
    meta: dict[str, Any],
) -> str:
    """Convert subtitle entries to Markdown."""
    from datetime import datetime

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
