"""Audio extraction and processing via ffmpeg."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional


class AudioTool:
    """封装 ffmpeg 音频提取和元数据探测。"""

    def __init__(self, ffmpeg_path: Optional[str] = None, ffprobe_path: Optional[str] = None):
        if ffmpeg_path is None:
            try:
                import imageio_ffmpeg
                ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            except ImportError:
                ffmpeg_path = None
        self.ffmpeg = ffmpeg_path or shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
        if ffprobe_path is None:
            try:
                import imageio_ffmpeg
                ffprobe_path = imageio_ffmpeg.get_ffmpeg_exe().replace("ffmpeg", "ffprobe")
                # imageio_ffmpeg may only include ffmpeg, not ffprobe
                if not Path(ffprobe_path).exists():
                    ffprobe_path = None
            except ImportError:
                ffprobe_path = None
        self.ffprobe = ffprobe_path or shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"

    def extract(
        self,
        input_path: str,
        output_path: str,
        sample_rate: int = 22050,
        channels: int = 1,
        bitrate: str = "64k",
        audio_format: str = "mp3",
    ) -> str:
        """从视频中提取音频。"""
        cmd = [
            self.ffmpeg,
            "-y",
            "-i", input_path,
            "-vn",
            "-ar", str(sample_rate),
            "-ac", str(channels),
            "-b:a", bitrate,
            "-f", audio_format,
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg exited {result.returncode}: {result.stderr[:500]}")
        if not Path(output_path).exists():
            raise FileNotFoundError(f"ffmpeg did not produce output: {output_path}")
        return output_path

    def probe(self, path: str) -> dict[str, any]:
        """获取媒体文件元数据。"""
        cmd = [
            self.ffprobe,
            "-v", "error",
            "-show_entries", "format=duration,bit_rate",
            "-show_entries", "stream=codec_name,sample_rate",
            "-of", "json",
            path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr}")
        data = json.loads(result.stdout)
        fmt = data.get("format", {})
        stream = (data.get("streams") or [{}])[0]
        return {
            "duration": float(fmt.get("duration", 0)),
            "bitrate": int(fmt.get("bit_rate", 0)),
            "codec": stream.get("codec_name", "unknown"),
            "sample_rate": int(stream.get("sample_rate", 0)) if stream.get("sample_rate") else None,
        }
