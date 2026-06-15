"""Single-worker serial executor for Agent Service.

Phase 2: Full pipeline integration for transcribe/study/anki.
Features: timeout control, orphan recovery, file lock, quality gate,
retry manager, checkpoint resume, idempotency.
"""

import fcntl
import json
import os
import random
import shutil
import signal
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "agent_service"))

from config import get_config
from task_queue import TaskQueue, Task, TaskStatus, TaskType, ErrorCode
from logger import TaskLogger, ExecutorLogger
from validators import validate_playlist_url, sanitize_course_name, check_idempotency
from tools import YouTubeTool, GeminiTool, NotebookLMTool, AudioTool, DownloadTool
from quality_gate import QualityGate
from retry_manager import RetryManager
from metrics import MetricsCollector
from prompt_registry import get_registry


class FileLock:
    """Process-level file lock to prevent multiple daemon instances."""

    def __init__(self, lock_path: Path):
        self.lock_path = lock_path
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = None

    def acquire(self) -> bool:
        self._fd = open(self.lock_path, "w")
        try:
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._fd.write(str(os.getpid()))
            self._fd.flush()
            return True
        except BlockingIOError:
            self._fd.close()
            return False

    def release(self) -> None:
        if self._fd:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            self._fd.close()
            self._fd = None


class Executor:
    """Serial task executor with retry logic, timeout, and orphan recovery."""

    def __init__(self):
        self.queue = TaskQueue()
        self.exec_logger = ExecutorLogger()
        self.config = get_config()
        self.running = False
        self.current_task: Task | None = None
        self._timer = None
        self.quality_gate = QualityGate()
        self.retry_manager = RetryManager()
        self.metrics = MetricsCollector()
        self.prompt_registry = get_registry()
        # Tools
        yt_dlp = self.config.get("api", "yt_dlp_path", default=".venv/bin/yt-dlp")
        self.yt_tool = YouTubeTool(yt_dlp_path=yt_dlp)
        self.gemini = GeminiTool()
        self.notebooklm = NotebookLMTool()
        self.audio_tool = AudioTool()
        self.download_tool = DownloadTool(yt_dlp_path=yt_dlp)

    def recover_orphan_tasks(self) -> int:
        """Scan and recover tasks stuck in running state (daemon crashed)."""
        recovered = 0
        timeout_map = {
            "transcribe": self.config.get_timeout("transcribe"),
            "study": self.config.get_timeout("study"),
            "anki": self.config.get_timeout("anki"),
        }
        for task in self.queue.list_all(status=TaskStatus.RUNNING):
            timeout = timeout_map.get(task.task_type.value, 3600)
            try:
                from datetime import datetime
                updated = datetime.fromisoformat(task.updated_at)
                elapsed = (datetime.now() - updated).total_seconds()
                if elapsed > timeout * 2:
                    self.queue.update(
                        task.task_id,
                        status=TaskStatus.FAILED,
                        error_code=ErrorCode.ORPHAN_TASK,
                        error_msg=f"Orphan task: daemon crashed after {elapsed:.0f}s",
                    )
                    recovered += 1
            except (ValueError, TypeError):
                continue
        if recovered > 0:
            self.exec_logger.log("WARN", f"Recovered {recovered} orphan tasks")
        return recovered

    def _set_timeout(self, task: Task) -> None:
        timeout = self.config.get_timeout(task.task_type.value)

        def _on_timeout():
            self.exec_logger.log("ERROR", f"Task {task.task_id} timeout after {timeout}s")
            self.queue.update(
                task.task_id,
                status=TaskStatus.FAILED,
                error_code=ErrorCode.TIMEOUT,
                error_msg=f"Execution timeout ({timeout}s)",
            )
            try:
                os.kill(os.getpid(), signal.SIGUSR1)
            except (OSError, ValueError):
                pass

        self._timer = threading.Timer(timeout, _on_timeout)
        self._timer.daemon = True
        self._timer.start()

    def _clear_timeout(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def run_task(self, task: Task) -> None:
        logger = TaskLogger(task.task_id)
        self.current_task = task
        self._set_timeout(task)
        self.metrics.start_task(task.task_id)

        try:
            self.queue.update(task.task_id, status=TaskStatus.RUNNING, current_phase="starting")
            logger.info("executor", f"开始执行任务: {task.task_type.value}")

            # Validate URL for transcribe tasks
            if task.task_type == TaskType.TRANSCRIBE and task.playlist_url:
                if not validate_playlist_url(task.playlist_url):
                    raise ValueError(f"Invalid playlist URL: {task.playlist_url}")

            # Check idempotency
            idem = check_idempotency(task.course_name, task.task_type.value, PROJECT_ROOT)
            if idem["exists"] and idem["files"]:
                logger.info("executor", f"幂等性检查: 跳过已存在的 {len(idem['files'])} 个文件")

            if task.task_type == TaskType.TRANSCRIBE:
                self._run_transcribe(task, logger)
            elif task.task_type == TaskType.STUDY:
                self._run_study(task, logger)
            elif task.task_type == TaskType.ANKI:
                self._run_anki(task, logger)

            self.queue.update(task.task_id, status=TaskStatus.COMPLETED, progress_pct=100)
            logger.info("executor", "任务完成")
            self.metrics.finish_task(task.task_id, task.task_type.value, "completed")

        except Exception as e:
            error_msg = str(e)
            logger.error("executor", f"任务失败: {error_msg}")
            self._handle_error(task, error_msg, logger)
        finally:
            self._clear_timeout()
            self.current_task = None
            logger.close()

    def _handle_error(self, task: Task, error_msg: str, logger: TaskLogger) -> None:
        """Handle task error with retry logic."""
        task_data = self.queue.get(task.task_id)
        retry_cfg = self.config.get_retry_config()
        max_retries = retry_cfg.get("max_retries", 3)

        # Map error message to ErrorCode
        error_code = self._classify_error(error_msg)

        self.retry_manager.record(
            task.task_id, error_code, error_msg,
            phase=task.current_phase or "unknown",
        )

        if task_data and task_data.retry_count < max_retries:
            should_retry, backoff = self.retry_manager.should_retry(
                task.task_id, error_code, task_data.retry_count
            )
            if should_retry and backoff > 0:
                logger.info("executor", f"将在 {backoff:.1f} 秒后重试 (第 {task_data.retry_count + 1} 次)")
                time.sleep(backoff)
            if should_retry:
                self.retry_manager.log_attempt(task.task_id, error_code, error_msg, backoff)
                self.queue.update(
                    task.task_id,
                    status=TaskStatus.RETRYING,
                    error_msg=error_msg,
                    error_code=error_code,
                    retry_count=task_data.retry_count + 1,
                )
            else:
                self.queue.update(
                    task.task_id,
                    status=TaskStatus.FAILED,
                    error_msg=error_msg,
                    error_code=error_code,
                )
                self.metrics.finish_task(task.task_id, task.task_type.value, "failed", error_code=error_code.value)
        else:
            self.queue.update(
                task.task_id,
                status=TaskStatus.FAILED,
                error_msg=error_msg,
                error_code=error_code,
            )
            self.metrics.finish_task(task.task_id, task.task_type.value, "failed", error_code=error_code.value)

    def _classify_error(self, error_msg: str) -> ErrorCode:
        msg = error_msg.lower()
        if "403" in msg:
            return ErrorCode.YT_DLP_403
        if "timeout" in msg:
            if "notebooklm" in msg:
                return ErrorCode.NOTEBOOKLM_TIMEOUT
            return ErrorCode.TIMEOUT
        if "429" in msg or "rate limit" in msg:
            return ErrorCode.GEMINI_429
        if "content filter" in msg:
            return ErrorCode.GEMINI_CONTENT_FILTER
        if "remote protocol" in msg or "server disconnected" in msg:
            return ErrorCode.GEMINI_REMOTE_PROTOCOL
        if "rpc" in msg and "notebooklm" in msg:
            return ErrorCode.NOTEBOOKLM_RPC
        if "zero source" in msg or "0 sources" in msg:
            return ErrorCode.NOTEBOOKLM_ZERO_SOURCE
        if "100 source" in msg or "source_id" in msg:
            return ErrorCode.NOTEBOOKLM_100_SOURCE
        if "retention" in msg or "too short" in msg:
            return ErrorCode.QUALITY_LOW_RETENTION
        if "english" in msg and "output" in msg:
            return ErrorCode.QUALITY_ENGLISH_OUTPUT
        if "empty" in msg:
            return ErrorCode.QUALITY_EMPTY_OUTPUT
        if "disk full" in msg or "no space" in msg:
            return ErrorCode.DISK_FULL
        if "orphan" in msg:
            return ErrorCode.ORPHAN_TASK
        return ErrorCode.UNKNOWN

    def _run_transcribe(self, task: Task, logger: TaskLogger) -> None:
        """Phase 1: Download subtitles, parse, refine with Gemini."""
        logger.info("transcribe", "启动转录流水线")
        course_dir = PROJECT_ROOT / "input" / sanitize_course_name(task.course_name)
        course_dir.mkdir(parents=True, exist_ok=True)

        if not task.playlist_url:
            raise ValueError("Transcribe task requires playlist_url")

        # Get playlist info
        logger.info("transcribe", "获取播放列表信息...")
        info = self.yt_tool.get_playlist_info(task.playlist_url)
        if "error" in info:
            raise RuntimeError(f"YouTube info failed: {info['error']}")

        video_count = info.get("video_count", 0)
        if task.max_videos and task.max_videos > 0:
            video_count = min(video_count, task.max_videos)
            logger.info("transcribe", f"max_videos 限制: 仅处理前 {video_count} 个视频")
        self.queue.update(task.task_id, video_count=video_count)
        logger.info("transcribe", f"播放列表: {info.get('title', 'Unknown')}, 计划处理 {video_count} 个视频")

        # Step 1: Try subtitles first
        logger.info("transcribe", "下载字幕...")
        srt_files = self.yt_tool.download_subtitles(
            task.playlist_url, course_dir / ".tmp_srt", lang="en"
        )
        logger.info("transcribe", f"下载了 {len(srt_files)} 个字幕文件")

        use_subtitle = len(srt_files) > 0
        total_videos = len(srt_files) if use_subtitle else video_count
        if task.max_videos and task.max_videos > 0:
            srt_files = srt_files[:task.max_videos]
            total_videos = len(srt_files) if use_subtitle else min(total_videos, task.max_videos)
        refined_count = 0

        if use_subtitle:
            # ── Path A: Subtitle-based transcription ──
            for i, srt_path in enumerate(srt_files, 1):
                index_str = srt_path.stem.split("_")[0] if "_" in srt_path.stem else f"{i:02d}"
                if self._skip_if_exists(course_dir, index_str, logger):
                    refined_count += 1
                    continue

                logger.info("transcribe", f"处理字幕 {i}/{len(srt_files)}: {srt_path.name}")
                raw_text = self.yt_tool.parse_srt(srt_path)
                if not raw_text:
                    logger.warn("transcribe", f"空字幕: {srt_path.name}")
                    continue

                refined = self._refine_and_save(
                    task, course_dir, index_str, info.get("title", task.course_name),
                    raw_text, logger, "字幕",
                )
                if refined:
                    refined_count += 1

                pct = int(refined_count / len(srt_files) * 100)
                self.queue.update(task.task_id, progress_pct=pct, video_completed=refined_count)
                jitter = self.config.get("retry", "sleep_jitter", default=[0, 2])
                time.sleep(random.uniform(*jitter))

            # Cleanup temp SRT files
            tmp_dir = course_dir / ".tmp_srt"
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)
        else:
            # ── Path B: Audio fallback (Whisper via Gemini API) ──
            logger.info("transcribe", "字幕不可用，切换到音频转录 (Whisper/Gemini)...")

            # Fetch individual videos
            try:
                _, videos = self.yt_tool.fetch_playlist(task.playlist_url)
            except Exception as e:
                raise RuntimeError(f"无法获取视频列表: {e}")

            if task.max_videos and task.max_videos > 0:
                videos = videos[:task.max_videos]
            total_videos = len(videos)
            tmp_video_dir = course_dir / ".tmp_video"
            tmp_video_dir.mkdir(parents=True, exist_ok=True)

            for i, video in enumerate(videos, 1):
                index_str = f"{i:02d}"
                if self._skip_if_exists(course_dir, index_str, logger):
                    refined_count += 1
                    continue

                logger.info("transcribe", f"[{i}/{total_videos}] 音频转录: {video['title']}")
                video_path = None
                audio_path = None
                raw_text = ""

                try:
                    # 1. Download video
                    logger.info("transcribe", "  → 下载视频...")
                    video_path = self.download_tool.download(
                        video["url"], str(tmp_video_dir), playlist_items="1"
                    )

                    # 2. Extract audio
                    logger.info("transcribe", "  → 提取音频...")
                    audio_path = str(Path(video_path).with_suffix(".mp3"))
                    self.audio_tool.extract(video_path, audio_path)

                    # 3. Transcribe with Gemini (Whisper)
                    logger.info("transcribe", "  → Whisper 转录 (Gemini API)...")
                    raw_text = self.gemini.transcribe_audio(audio_path)
                    if not raw_text:
                        logger.warn("transcribe", "  → 转录结果为空")
                        continue

                    # 4. Refine
                    refined = self._refine_and_save(
                        task, course_dir, index_str, video["title"],
                        raw_text, logger, "音频转录",
                    )
                    if refined:
                        refined_count += 1

                except Exception as e:
                    logger.error("transcribe", f"  → 音频链路失败: {e}")
                    continue
                finally:
                    # Cleanup temp files
                    if video_path:
                        Path(video_path).unlink(missing_ok=True)
                    if audio_path:
                        Path(audio_path).unlink(missing_ok=True)

                pct = int(refined_count / total_videos * 100)
                self.queue.update(task.task_id, progress_pct=pct, video_completed=refined_count)
                jitter = self.config.get("retry", "sleep_jitter", default=[0, 2])
                time.sleep(random.uniform(*jitter))

            # Cleanup temp video dir
            if tmp_video_dir.exists():
                shutil.rmtree(tmp_video_dir, ignore_errors=True)

        logger.info("transcribe", f"转录完成: {refined_count}/{total_videos} 个视频")

    def _skip_if_exists(self, course_dir: Path, index_str: str, logger: TaskLogger) -> bool:
        """Check idempotency: skip if refined file already exists."""
        refined_candidates = list(course_dir.glob(f"{index_str}-*.md"))
        refined_candidates = [f for f in refined_candidates if "srt" not in f.name.lower()]
        if refined_candidates:
            logger.info("transcribe", f"跳过已处理: {refined_candidates[0].name}")
            return True
        return False

    def _refine_and_save(
        self,
        task: Task,
        course_dir: Path,
        index_str: str,
        title: str,
        raw_text: str,
        logger: TaskLogger,
        source_label: str,
    ) -> bool:
        """Refine raw text with Gemini and save to disk. Returns True on success."""
        # Refine with Gemini
        prompt = self.prompt_registry.get("refine", body=raw_text[:300000])
        try:
            refined = self.gemini.generate(prompt)
        except Exception as e:
            logger.error("transcribe", f"精修失败: {e}")
            return False

        # Quality check
        q = self.quality_gate.check_transcribe(course_dir, raw_text, refined)
        if not q.passed:
            logger.warn("transcribe", f"质量检查未通过: {q.checks}")
            if q.retry_prompt_hint:
                prompt = self.prompt_registry.get("refine", body=raw_text[:300000])
                try:
                    refined = self.gemini.generate(prompt)
                except Exception:
                    pass

        # Save refined file
        safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)[:50]
        out_name = f"{index_str}-{safe_title}.md"
        out_path = course_dir / out_name
        header = f"# {title}\n\n## 元信息\n\n- **序号**: {index_str}\n- **课程**: {task.course_name}\n- **处理时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n- **来源**: {source_label}\n\n---\n\n## 精修内容\n\n"
        out_path.write_text(header + refined, encoding="utf-8")
        logger.info("transcribe", f"保存: {out_name}", size=len(refined))
        return True

    def _run_study(self, task: Task, logger: TaskLogger) -> None:
        """Phase 2: NotebookLM study - syllabus, chapters, MOC."""
        logger.info("study", "启动学习流水线")
        course_name = sanitize_course_name(task.course_name)
        input_dir = PROJECT_ROOT / "input" / course_name
        output_dir = PROJECT_ROOT / "output" / course_name
        output_dir.mkdir(parents=True, exist_ok=True)

        if not input_dir.exists():
            raise FileNotFoundError(f"Input directory not found: {input_dir}")

        # Get all transcript files
        md_files = sorted(input_dir.glob("*.md"))
        if not md_files:
            raise FileNotFoundError(f"No markdown files found in {input_dir}")

        logger.info("study", f"找到 {len(md_files)} 个转录文件")

        # Create NotebookLM project
        logger.info("study", "创建 NotebookLM 项目...")
        try:
            notebook_id = self.notebooklm.create_notebook(course_name)
        except Exception as e:
            logger.error("study", f"NotebookLM 创建失败: {e}")
            raise RuntimeError(f"NotebookLM create failed: {e}")

        logger.info("study", f"Notebook ID: {notebook_id}")

        # Configure academic persona
        try:
            self.notebooklm.configure_persona(notebook_id, (
                "You are a graduate-level research assistant specializing in "
                "financial economics and quantitative methods. "
                "Produce rigorous, academically dense notes with LaTeX formulas, "
                "critical analysis, and cross-references. All output must be in Chinese."
            ))
        except Exception:
            pass  # Non-critical, continue

        # Upload sources
        logger.info("study", f"上传 {len(md_files)} 个 source...")
        upload_result = self.notebooklm.upload_sources(notebook_id, md_files)
        logger.info("study", f"上传结果: {upload_result}")

        if upload_result["uploaded"] == 0 and upload_result["failed"] > 0:
            # Total failure - use Gemini Direct fallback
            logger.warn("study", "NotebookLM 上传全部失败，切换到 Gemini Direct")
            self._run_study_gemini_direct(task, logger, md_files, output_dir)
            return

        # Phase 1: Generate syllabus
        logger.info("study", "Phase 1: 生成课程大纲...")
        self.queue.update(task.task_id, current_phase="study_phase1_syllabus")
        syllabus_prompt = self.prompt_registry.get("syllabus", content="")
        # Build content from transcript summaries
        content_parts = []
        for f in md_files[:20]:  # Limit to first 20 files for context
            text = f.read_text(encoding="utf-8")[:5000]
            content_parts.append(f"=== {f.name} ===\n{text}")
        content = "\n\n".join(content_parts)[:20000]
        syllabus_prompt = self.prompt_registry.get("syllabus", content=content)

        try:
            syllabus = self.notebooklm.ask(notebook_id, syllabus_prompt, timeout=300)
        except Exception as e:
            logger.error("study", f"大纲生成失败: {e}")
            # Fallback to Gemini Direct
            self._run_study_gemini_direct(task, logger, md_files, output_dir)
            return

        # Save syllabus
        syllabus_path = output_dir / f"{course_name}_课程大纲.md"
        header = f"# {course_name} — 课程大纲\n\n> **Metadata**\n> - 课程：{course_name}\n> - 生成时间：{time.strftime('%Y-%m-%d')}\n\n---\n\n"
        syllabus_path.write_text(header + syllabus, encoding="utf-8")
        logger.info("study", f"大纲保存: {syllabus_path.name}")

        # Parse chapters from syllabus
        chapters = self._parse_syllabus(syllabus)
        logger.info("study", f"解析到 {len(chapters)} 个章节")

        if len(chapters) < 3:
            logger.warn("study", f"章节数过少 ({len(chapters)})，尝试 Gemini Direct")
            self._run_study_gemini_direct(task, logger, md_files, output_dir)
            return

        # Phase 2: Chapter deep dive
        logger.info("study", "Phase 2: 逐章深挖...")
        for idx, ch in enumerate(chapters):
            self.queue.update(
                task.task_id,
                current_phase=f"study_phase2_ch{ch['num']}",
                progress_pct=int((idx / len(chapters)) * 70),
            )
            logger.info("study", f"[{ch['num']}] {ch['title']} (视频 {ch['range']})")

            # Find relevant transcript files for this chapter
            range_files = self._get_files_for_range(md_files, ch['range'])
            transcript = "\n\n".join(
                f.read_text(encoding="utf-8")[:8000] for f in range_files
            )[:20000]

            chapter_prompt = self.prompt_registry.get(
                "chapter_deep_dive",
                video_range=ch['range'],
                chapter_title=ch['title'],
                transcript=transcript,
            )

            try:
                chapter_content = self.notebooklm.ask(notebook_id, chapter_prompt, timeout=300)
            except Exception as e:
                logger.error("study", f"章节 {ch['num']} 生成失败: {e}")
                # Try Gemini Direct for this chapter
                try:
                    chapter_content = self.gemini.generate(chapter_prompt)
                except Exception as e2:
                    logger.error("study", f"Gemini Direct 也失败: {e2}")
                    continue

            # Save chapter
            safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in ch['title'])[:50]
            ch_path = output_dir / f"Ch_{ch['num']:02d}_{safe_title}.md"
            header = f"# Ch.{ch['num']:02d} {ch['title']}\n\n"
            header += f"> **Metadata**\n> - 课程：{course_name}\n> - 视频范围：{ch['range']}\n> - 核心命题：[从大纲中提取]\n\n---\n\n"
            ch_path.write_text(header + chapter_content, encoding="utf-8")
            logger.info("study", f"章节保存: {ch_path.name}")

            # Sleep between chapters
            time.sleep(2)

        # Phase 3: MOC and Anki
        logger.info("study", "Phase 3: 生成知识地图和 Anki...")
        self.queue.update(task.task_id, current_phase="study_phase3_moc_anki", progress_pct=85)

        # Read all chapters for MOC context
        chapter_files = sorted(output_dir.glob("Ch_*.md"))
        chapters_text = "\n\n".join(
            f.read_text(encoding="utf-8")[:5000] for f in chapter_files
        )[:20000]

        # MOC
        moc_prompt = self.prompt_registry.get("moc", course_name=course_name, chapters=chapters_text)
        try:
            moc = self.notebooklm.ask(notebook_id, moc_prompt, timeout=300)
        except Exception as e:
            logger.error("study", f"MOC 生成失败: {e}")
            moc = self.gemini.generate(moc_prompt)

        moc_path = output_dir / f"{course_name}_知识地图_MOC.md"
        moc_path.write_text(f"# {course_name} — 知识地图 (MOC)\n\n---\n\n" + moc, encoding="utf-8")
        logger.info("study", f"MOC 保存: {moc_path.name}")

        # Anki
        anki_prompt = self.prompt_registry.get("anki", count=20, chapters=chapters_text)
        try:
            anki = self.notebooklm.ask(notebook_id, anki_prompt, timeout=300)
        except Exception as e:
            logger.error("study", f"Anki 生成失败: {e}")
            anki = self.gemini.generate(anki_prompt)

        anki_path = output_dir / f"Anki_{course_name}_20张真题卡.md"
        anki_path.write_text(f"# Anki — {course_name} (真题卡)\n\n---\n\n" + anki, encoding="utf-8")
        logger.info("study", f"Anki 保存: {anki_path.name}")

        # Quality check
        q = self.quality_gate.check_course_study(course_name, PROJECT_ROOT)
        self.queue.update(task.task_id, quality_score=q.score)
        logger.info("study", f"质量评分: {q.score}/100")

        logger.info("study", "学习完成", output_dir=str(output_dir))

    def _run_study_gemini_direct(self, task: Task, logger: TaskLogger,
                                  md_files: list, output_dir: Path) -> None:
        """Fallback: Use Gemini API directly when NotebookLM fails."""
        logger.info("study", "使用 Gemini Direct 模式")
        course_name = sanitize_course_name(task.course_name)

        # Build content from all transcripts
        all_content = "\n\n".join(
            f.read_text(encoding="utf-8")[:5000] for f in md_files[:30]
        )[:20000]

        # Generate syllabus
        syllabus_prompt = self.prompt_registry.get("syllabus", content=all_content)
        syllabus = self.gemini.generate(syllabus_prompt)
        syllabus_path = output_dir / f"{course_name}_课程大纲.md"
        syllabus_path.write_text(f"# {course_name} — 课程大纲\n\n---\n\n" + syllabus, encoding="utf-8")
        logger.info("study", "大纲生成完成 (Gemini Direct)")

        chapters = self._parse_syllabus(syllabus)
        logger.info("study", f"解析到 {len(chapters)} 个章节")

        # Generate chapters
        for ch in chapters:
            range_files = self._get_files_for_range(md_files, ch['range'])
            transcript = "\n\n".join(f.read_text(encoding="utf-8")[:8000] for f in range_files)[:20000]
            prompt = self.prompt_registry.get(
                "chapter_deep_dive",
                video_range=ch['range'],
                chapter_title=ch['title'],
                transcript=transcript,
            )
            content = self.gemini.generate(prompt)
            safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in ch['title'])[:50]
            ch_path = output_dir / f"Ch_{ch['num']:02d}_{safe_title}.md"
            ch_path.write_text(f"# Ch.{ch['num']:02d} {ch['title']}\n\n---\n\n" + content, encoding="utf-8")
            logger.info("study", f"章节 {ch['num']} 完成 (Gemini Direct)")
            time.sleep(2)

        # MOC
        chapter_files = sorted(output_dir.glob("Ch_*.md"))
        chapters_text = "\n\n".join(f.read_text(encoding="utf-8")[:5000] for f in chapter_files)[:20000]
        moc_prompt = self.prompt_registry.get("moc", course_name=course_name, chapters=chapters_text)
        moc = self.gemini.generate(moc_prompt)
        (output_dir / f"{course_name}_知识地图_MOC.md").write_text(
            f"# {course_name} — 知识地图\n\n---\n\n" + moc, encoding="utf-8"
        )

        # Anki
        anki_prompt = self.prompt_registry.get("anki", count=20, chapters=chapters_text)
        anki = self.gemini.generate(anki_prompt)
        (output_dir / f"Anki_{course_name}_20张真题卡.md").write_text(
            f"# Anki — {course_name}\n\n---\n\n" + anki, encoding="utf-8"
        )

        logger.info("study", "Gemini Direct 模式完成")

    def _run_anki(self, task: Task, logger: TaskLogger) -> None:
        """Phase 3: Generate Anki cards from chapter notes."""
        logger.info("anki", "启动 Anki 生成")
        course_name = sanitize_course_name(task.course_name)
        output_dir = PROJECT_ROOT / "output" / course_name
        anki_dir = PROJECT_ROOT / "anki" / course_name
        anki_dir.mkdir(parents=True, exist_ok=True)

        if not output_dir.exists():
            raise FileNotFoundError(f"Output directory not found: {output_dir}")

        # Read chapter files
        chapter_files = sorted(output_dir.glob("Ch_*.md"))
        if not chapter_files:
            logger.warn("anki", "未找到章节文件，跳过")
            return

        chapters_text = "\n\n".join(
            f.read_text(encoding="utf-8")[:5000] for f in chapter_files
        )[:20000]

        anki_prompt = self.prompt_registry.get("anki", count=20, chapters=chapters_text)
        try:
            anki = self.gemini.generate(anki_prompt)
        except Exception as e:
            logger.error("anki", f"Anki 生成失败: {e}")
            raise

        anki_path = anki_dir / f"Anki_{course_name}_20张真题卡.md"
        anki_path.write_text(f"# Anki — {course_name} (真题卡)\n\n---\n\n" + anki, encoding="utf-8")
        logger.info("anki", f"Anki 保存: {anki_path.name}")
        logger.info("anki", "Anki 生成完成", output_dir=str(anki_dir))

    def _parse_syllabus(self, text: str) -> list:
        """Parse syllabus text to extract chapter list."""
        import re
        chapters = []
        chinese_nums = {
            '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
            '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
        }

        pattern1 = r"##\s*第\s*(\d+|[一二三四五六七八九十]+)\s*章\s*[：:]\s*(.+?)(?=\n##|\Z)"
        pattern2 = r"##\s*Chapter\s+(\d+)\s*[:：]\s*(.+?)(?=\n##|\Z)"

        matches = re.findall(pattern1, text, re.DOTALL)
        if not matches:
            matches = re.findall(pattern2, text, re.DOTALL)

        for m in matches:
            num_str = m[0]
            if num_str in chinese_nums:
                num = chinese_nums[num_str]
            else:
                try:
                    num = int(num_str)
                except ValueError:
                    continue
            title = m[1].strip().split("\n")[0].strip()
            title = re.sub(r'\*\*', '', title)
            range_match = re.search(r"视频范围[：:]\s*(\d+(?:-\d+)?)", text)
            video_range = range_match.group(1) if range_match else f"{num:02d}"
            chapters.append({
                "num": num,
                "title": title,
                "range": video_range,
            })

        return chapters

    def _get_files_for_range(self, md_files: list, video_range: str) -> list:
        """Get transcript files matching a video range."""
        import re
        if "-" in video_range:
            try:
                start, end = map(int, video_range.split("-"))
                return [f for f in md_files if any(
                    re.match(rf"^{i:02d}-", f.name) or re.match(rf"^{i}\D", f.name)
                    for i in range(start, end + 1)
                )]
            except ValueError:
                pass
        # Single video or fallback
        try:
            idx = int(video_range)
            for f in md_files:
                if re.match(rf"^{idx:02d}-", f.name) or re.match(rf"^{idx}\D", f.name):
                    return [f]
        except ValueError:
            pass
        return md_files[:5]  # Fallback to first 5 files

    def run_once(self) -> bool:
        """Process one pending task. Returns True if a task was processed."""
        task = self.queue.next_pending()
        if not task:
            return False
        self.run_task(task)
        return True

    def _write_health(self) -> None:
        health_file = PROJECT_ROOT / "logs" / ".health"
        data = {
            "pid": os.getpid(),
            "status": "running" if self.running else "stopped",
            "current_task": self.current_task.task_id if self.current_task else "idle",
            "last_heartbeat": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        try:
            with open(health_file, "w") as f:
                json.dump(data, f)
        except IOError:
            pass

    def run_loop(self, interval: int = 5) -> None:
        """Main daemon loop — serial worker."""
        lock_path = Path(self.config.get("daemon", "lock_file", default="./logs/.daemon.lock"))
        if not lock_path.is_absolute():
            lock_path = PROJECT_ROOT / lock_path
        file_lock = FileLock(lock_path)
        if not file_lock.acquire():
            print("Error: Another daemon instance is already running.", file=sys.stderr)
            sys.exit(1)

        self.recover_orphan_tasks()

        self.running = True
        self.exec_logger.log("INFO", "执行引擎启动 (单 worker 串行)")

        try:
            while self.running:
                self._write_health()
                processed = self.run_once()
                if not processed:
                    time.sleep(interval)
        except KeyboardInterrupt:
            self.exec_logger.log("INFO", "执行引擎收到中断信号")
        finally:
            self.running = False
            self._write_health()
            self.exec_logger.log("INFO", "执行引擎停止")
            self.exec_logger.close()
            file_lock.release()

    def stop(self) -> None:
        self.running = False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Agent Service Executor")
    parser.add_argument("--once", action="store_true", help="执行一次后退出")
    parser.add_argument("--interval", type=int, default=5, help="轮询间隔(秒)")
    args = parser.parse_args()

    executor = Executor()
    if args.once:
        processed = executor.run_once()
        print(f"Processed: {processed}")
    else:
        executor.run_loop(interval=args.interval)


if __name__ == "__main__":
    main()
