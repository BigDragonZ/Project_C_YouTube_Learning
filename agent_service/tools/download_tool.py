"""Video download operations via yt-dlp."""

import re
import subprocess
from pathlib import Path
from typing import Optional

class DownloadTool:
    """封装 yt-dlp 视频下载。"""

    def __init__(self, yt_dlp_path: Optional[str] = None, use_cookies: bool = True):
        if yt_dlp_path is None:
            # Lazy import to avoid circular dependency
            from config import get_config
            cfg = get_config()
            yt_dlp_path = cfg.get("api", "yt_dlp_path", default=".venv/bin/yt-dlp")
        self.yt_dlp_path = yt_dlp_path
        self.use_cookies = use_cookies

    def download(
        self,
        url: str,
        output_dir: str,
        playlist_items: str = "1",
        video_format: str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        merge_format: str = "mp4",
    ) -> str:
        """下载视频到指定目录。"""
        args = [
            self.yt_dlp_path,
            "--playlist-items", playlist_items,
            "--format", video_format,
            "--merge-output-format", merge_format,
            "--output", f"{output_dir}/%(title)s.%(ext)s",
            "--no-warnings",
            url,
        ]
        if self.use_cookies:
            args.insert(1, "chrome")
            args.insert(1, "--cookies-from-browser")

        result = subprocess.run(args, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"yt-dlp failed: {result.stderr[:500]}")

        # Extract destination from output
        for line in result.stdout.split("\n"):
            match = re.match(r"\[download\] Destination: (.+)", line)
            if match:
                return match.group(1).strip()

        # Fallback: newest file in output dir
        out_path = Path(output_dir)
        files = [f for f in out_path.iterdir() if f.is_file()]
        if not files:
            raise FileNotFoundError("No file found after download")
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        return str(files[0])
