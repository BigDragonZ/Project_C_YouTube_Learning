"""
Video download operations via yt-dlp.
"""

import subprocess
from pathlib import Path
from typing import Optional

from config.paths import BINARIES

YTDLP = BINARIES["yt_dlp"]


def download_video(
    url: str,
    output_dir: str,
    playlist_items: str = "1",
    video_format: str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    merge_format: str = "mp4",
) -> str:
    """Download video using yt-dlp."""
    args = [
        YTDLP,
        "--cookies-from-browser", "chrome",
        "--playlist-items", playlist_items,
        "--format", video_format,
        "--merge-output-format", merge_format,
        "--output", f"{output_dir}/%(title)s.%(ext)s",
        "--no-warnings",
        url,
    ]

    result = subprocess.run(args, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr[:500]}")

    # Extract destination from output
    for line in result.stdout.split("\n"):
        match = __import__("re").match(r"\[download\] Destination: (.+)", line)
        if match:
            return match.group(1).strip()

    # Fallback: newest file in output dir
    out_path = Path(output_dir)
    files = [f for f in out_path.iterdir() if f.is_file()]
    if not files:
        raise FileNotFoundError("No file found after download")

    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return str(files[0])
