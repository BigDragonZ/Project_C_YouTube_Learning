"""Audio download operations via yt-dlp."""

import re
import subprocess
from pathlib import Path
from typing import Optional


class DownloadTool:
    """封装 yt-dlp 音频下载（用于音频转录）。"""

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
    ) -> str:
        """下载音频到指定目录，直接输出 mp3。"""
        cmd = self.yt_dlp_path.split() if " " in self.yt_dlp_path else [self.yt_dlp_path]
        if self.use_cookies:
            cmd.extend(["--cookies-from-browser", "chrome"])
        else:
            # Use android client only when not using cookies (cookies conflict with android client)
            cmd.extend(["--extractor-args", "youtube:player_client=android"])
        cmd.extend([
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "64K",
            "--playlist-items", playlist_items,
            "--output", f"{output_dir}/%(title)s.%(ext)s",
            "--no-warnings",
            url,
        ])
        # Use a temp file to capture stdout so we can parse destination lines
        import tempfile as _tf
        with _tf.NamedTemporaryFile(mode='w+', delete=False, suffix='.log') as tmpf:
            tmpf.flush()
            result = subprocess.run(cmd, stdout=tmpf, stderr=subprocess.PIPE, timeout=600)
            tmpf.flush()
        dest = None
        with open(tmpf.name, 'r') as f:
            for line in f:
                match = re.match(r"\[download\] Destination: (.+)", line)
                if match:
                    dest = match.group(1).strip()
                    break
                # Audio extraction writes to a different path
                post_match = re.match(r"\[ExtractAudio\] Destination: (.+)", line)
                if post_match:
                    dest = post_match.group(1).strip()
        Path(tmpf.name).unlink(missing_ok=True)
        if result.returncode == 0:
            if dest and Path(dest).exists():
                return dest
            # Fallback: newest mp3 in output dir
            out_path = Path(output_dir)
            mp3_files = sorted(out_path.glob("*.mp3"), key=lambda f: f.stat().st_mtime, reverse=True)
            if mp3_files:
                return str(mp3_files[0])
        raise RuntimeError(f"yt-dlp failed: {result.stderr.decode('utf-8', errors='replace')[:500]}")
