"""
Knowledge base automation pipeline.

Orchestrates the full workflow:
  1. Extract playlist from YouTube URL
  2. For each video: subtitle -> audio transcription -> markdown
  3. Refine markdown with Gemini
  4. Keep only final refined output (delete raw after refinement)
"""

import tempfile
from pathlib import Path
from typing import Optional

from config.paths import PATHS, course_dir, build_filename
from lib.youtube import fetch_playlist, fetch_title, download_subtitle, parse_srt, to_markdown
from lib.download import download_video
from lib.audio import extract_audio
from lib.transcribe import transcribe_audio
from lib.refine import refine_markdown


def _try_subtitle(video: dict, course_name: str, index: int) -> Optional[str]:
    """Try to get subtitle. Returns markdown content or None."""
    try:
        out_dir = course_dir(course_name)
        out_dir.mkdir(parents=True, exist_ok=True)

        temp_base = str(out_dir / f"_tmp_{video['id']}")
        srt_file = download_subtitle(video["url"], temp_base)

        srt_content = Path(srt_file).read_text(encoding="utf-8")
        entries = parse_srt(srt_content)
        markdown = to_markdown(
            entries,
            {
                "title": video["title"],
                "url": video["url"],
                "course": course_name,
                "index": index,
            },
        )

        # Cleanup
        Path(srt_file).unlink(missing_ok=True)
        Path(f"{temp_base}.en.srt").unlink(missing_ok=True)

        print(f"  [OK] Subtitle: {len(entries)} entries")
        return markdown

    except Exception as e:
        print(f"  [WARN] Subtitle failed: {str(e)[:100]}")
        return None


def _try_audio_transcription(video: dict, course_name: str, index: int) -> Optional[str]:
    """Fallback: download video, extract audio, transcribe. Returns markdown or None."""
    try:
        download_dir = PATHS["download_dir"]
        download_dir.mkdir(parents=True, exist_ok=True)

        print(f"  [INFO] Downloading video...")
        video_path = download_video(video["url"], str(download_dir))

        print(f"  [INFO] Extracting audio...")
        audio_path = video_path.replace(Path(video_path).suffix, ".mp3")
        extract_audio(video_path, audio_path)

        print(f"  [INFO] Transcribing audio...")
        result = transcribe_audio(audio_path)

        # Build markdown
        from datetime import datetime
        markdown = f"""# {video['title']}

## 元信息

- **序号**: {index}
- **课程**: {course_name}
- **视频ID**: {video['id']}
- **链接**: {video['url']}
- **处理时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **来源**: YouTube 音频转写
- **后端**: {result['backend']}
- **模型**: {result['model']}

---

## 转写内容

{result['text']}
"""

        # Cleanup downloaded files
        Path(video_path).unlink(missing_ok=True)
        Path(audio_path).unlink(missing_ok=True)

        print(f"  [OK] Transcription: {len(result['text'])} chars")
        return markdown

    except Exception as e:
        print(f"  [WARN] Audio transcription failed: {str(e)[:100]}")
        return None


def _save_raw(markdown: str, course_name: str, index: int, title: str) -> Path:
    """Save raw markdown file (temporary, will be deleted after refinement)."""
    out_dir = course_dir(course_name)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = build_filename(index, title, "md")
    path = out_dir / filename
    path.write_text(markdown, encoding="utf-8")
    return path


def _save_refined(raw_path: Path, refined: str, course_name: str, index: int, title: str) -> Path:
    """Save refined markdown file. Replaces raw file."""
    out_dir = course_dir(course_name)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = build_filename(index, title, "md")
    path = out_dir / filename

    # Build final content with metadata header + refined body
    from datetime import datetime
    header = f"""# {title}

## 元信息

- **序号**: {index}
- **课程**: {course_name}
- **处理时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **来源**: 精修版

---

## 精修内容

"""

    # Write to a temp path first, then replace raw
    temp_path = out_dir / f"_refined_{index}.md"
    temp_path.write_text(header + refined, encoding="utf-8")

    # Delete raw file, then rename temp to final
    if raw_path.exists():
        raw_path.unlink()
        print(f"  [INFO] Deleted raw file: {raw_path.name}")

    temp_path.rename(path)

    return path


def process_video(video: dict, course_name: str, index: int) -> tuple[Optional[Path], Optional[Path]]:
    """
    Process a single video through the pipeline.

    Returns:
        (raw_md_path, refined_md_path) or (None, None) on failure
    """
    print(f"\n[{index}] {video['title']}")
    print(f"    URL: {video['url']}")

    # Step 1: Try subtitle
    markdown = _try_subtitle(video, course_name, index)
    source = "subtitle"

    # Step 2: Fallback to audio transcription
    if markdown is None:
        print(f"  [INFO] Falling back to audio transcription...")
        markdown = _try_audio_transcription(video, course_name, index)
        source = "audio"

    if markdown is None:
        print(f"  [ERROR] All methods failed for video {index}")
        return None, None

    # Save raw
    raw_path = _save_raw(markdown, course_name, index, video["title"])
    print(f"  [OK] Raw saved: {raw_path.name}")

    # Step 3: Refine
    try:
        print(f"  [INFO] Refining with Gemini...")
        # Extract body for refinement
        if "## 转写内容" in markdown:
            body = markdown.split("## 转写内容", 1)[1].strip()
        else:
            body = markdown

        refined = refine_markdown(body)
        refined_path = _save_refined(raw_path, refined, course_name, index, video["title"])
        print(f"  [OK] Refined saved: {refined_path.name}")
        return raw_path, refined_path

    except Exception as e:
        print(f"  [WARN] Refinement failed: {str(e)[:100]}")
        return raw_path, None


def run_pipeline(playlist_url: str, course_name: str, max_videos: Optional[int] = None) -> list[tuple[Optional[Path], Optional[Path]]]:
    """
    Run the full pipeline on a YouTube playlist.

    Args:
        playlist_url: YouTube playlist or video URL
        course_name: Output directory name under flow/
        max_videos: Limit number of videos to process (None = all)

    Returns:
        List of (raw_path, refined_path) tuples
    """
    print(f"=" * 60)
    print(f"Pipeline: {course_name}")
    print(f"URL: {playlist_url}")
    print(f"=" * 60)

    # Fetch playlist
    print("\n[INFO] Fetching playlist...")
    playlist_title, videos = fetch_playlist(playlist_url)
    print(f"[OK] Playlist: {playlist_title}")
    print(f"[OK] Videos: {len(videos)}")

    if max_videos:
        videos = videos[:max_videos]
        print(f"[INFO] Limited to first {max_videos} videos")

    # Process each video
    results: list[tuple[Optional[Path], Optional[Path]]] = []
    for video in videos:
        raw, refined = process_video(video, course_name, video["index"])
        results.append((raw, refined))

    # Summary
    success = sum(1 for r in results if r[0] is not None)
    refined = sum(1 for r in results if r[1] is not None)
    print(f"\n{'=' * 60}")
    print(f"Summary: {success}/{len(videos)} videos processed")
    print(f"Refined: {refined}/{len(videos)}")
    print(f"Output: {course_dir(course_name)}")
    print(f"{'=' * 60}")

    return results
