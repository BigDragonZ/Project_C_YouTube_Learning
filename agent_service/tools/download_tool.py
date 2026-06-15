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
        video_format: str = "best",
        merge_format: str = "mp4",
    ) -> str:
        """下载视频到指定目录。"""
        cmd = self.yt_dlp_path.split() if " " in self.yt_dlp_path else [self.yt_dlp_path]

        # Try different configurations: with format and merge, without restrictions
        configs = [
            # Config 1: with format and merge format
            (["--format", video_format, "--merge-output-format", merge_format] if video_format and merge_format else []),
            # Config 2: no format restrictions
            [],
        ]

        for cfg in configs:
            run_args = cmd.copy()
            if self.use_cookies:
                run_args.extend(["--cookies-from-browser", "chrome"])
            else:
                # Use android client only when not using cookies (cookies conflict with android client)
                run_args.extend(["--extractor-args", "youtube:player_client=android"])
            run_args.extend(cfg)
            run_args.extend([
                "--playlist-items", playlist_items,
                "--output", f"{output_dir}/%(title)s.%(ext)s",
                "--no-warnings",
                url,
            ])
            # Use a temp file to capture stdout so we can parse destination lines
            import tempfile as _tf
            with _tf.NamedTemporaryFile(mode='w+', delete=False, suffix='.log') as tmpf:
                tmpf.flush()
                result = subprocess.run(run_args, stdout=tmpf, stderr=subprocess.PIPE, timeout=300)
                tmpf.flush()
            # Parse destination from temp file
            dest = None
            with open(tmpf.name, 'r') as f:
                for line in f:
                    match = re.match(r"\[download\] Destination: (.+)", line)
                    if match:
                        dest = match.group(1).strip()
                        break
            # Cleanup temp file
            Path(tmpf.name).unlink(missing_ok=True)
            if result.returncode == 0 and dest:
                return dest
            if result.returncode == 0:
                # Fallback: newest file in output dir
                out_path = Path(output_dir)
                files = [f for f in out_path.iterdir() if f.is_file()]
                if files:
                    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
                    return str(files[0])
            # If returncode != 0, try next config
        else:
            raise RuntimeError(f"yt-dlp failed: {result.stderr.decode('utf-8', errors='replace')[:500]}")
