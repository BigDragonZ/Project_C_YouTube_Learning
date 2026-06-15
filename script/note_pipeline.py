#!/usr/bin/env python3
"""
Note generation pipeline CLI.

Orchestrates the full knowledge-base workflow:
  Phase 1: Upload transcripts → generate syllabus
  Phase 2: Chapter-by-chapter deep-dive with pressure tests
  Phase 3: MOC, next-steps, Anki synthesis

Features:
  - Automatic checkpoint persistence (resume after interruption)
  - Dry-run mode with MockAdapter
  - Phase auto-detection from checkpoint or filesystem
  - Structured logging

Usage:
    uv run flow/script/note_pipeline.py --course "CourseName"
    uv run flow/script/note_pipeline.py --course "CourseName" --resume
    uv run flow/script/note_pipeline.py --course "CourseName" --dry-run
"""

import argparse
import logging
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from config.note_paths import raw_note_dir, permanent_note_dir
from config.notebooklm import load_config
from models.note import CourseContext
from lib.course_loader import load_videos, count_raw_files
from lib.syllabus_parser import parse_syllabus, save_syllabus, load_syllabus
from lib.note_generator import (
    generate_syllabus,
    generate_chapter_note,
    generate_moc,
    generate_next_steps,
    generate_anki,
)
from lib.checkpoint import (
    init_checkpoint,
    save_checkpoint,
    load_checkpoint,
    detect_phase_from_checkpoint,
    PipelineCheckpoint,
)
from lib.adapters.cli import CLIAdapter
from lib.adapters.mock import MockAdapter
from lib.adapters.base import NotebookLMAdapter


def _setup_logging() -> None:
    """Configure structured logging to console and file."""
    log_format = "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Course knowledge base note generation pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline (auto-detect phase, create checkpoint)
  %(prog)s --course "Valuation"

  # Resume from last checkpoint
  %(prog)s --course "Valuation" --resume

  # Dry-run with mock adapter (no external calls)
  %(prog)s --course "Valuation" --dry-run

  # Force specific phase
  %(prog)s --course "Valuation" --phase 2 --notebook-id "abc123..."

  # Custom rounds and Anki count
  %(prog)s --course "Valuation" --rounds 7 --anki-count 30
        """,
    )

    parser.add_argument(
        "--course",
        required=True,
        help="Course name (used for directory and notebook naming)",
    )
    parser.add_argument(
        "--raw-dir",
        default=None,
        help="Override raw transcription directory (default: flow/<course_name>)",
    )
    parser.add_argument(
        "--phase",
        type=int,
        choices=[1, 2, 3],
        default=None,
        help="Force specific phase (default: auto-detect)",
    )
    parser.add_argument(
        "--notebook-id",
        default=None,
        help="Existing NotebookLM notebook ID",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=5,
        help="Pressure-test rounds per chapter (default: 5)",
    )
    parser.add_argument(
        "--anki-count",
        type=int,
        default=20,
        help="Anki cards to generate (default: 20)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mock mode: no external calls, print actions only",
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Skip source upload (sources already in notebook)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint (overrides --phase auto-detection)",
    )

    return parser


def _create_adapter(dry_run: bool) -> NotebookLMAdapter:
    """Factory: return appropriate adapter."""
    if dry_run:
        return MockAdapter()
    return CLIAdapter()


def phase1_upload_and_syllabus(
    ctx: CourseContext,
    adapter: NotebookLMAdapter,
    cp: PipelineCheckpoint,
    skip_upload: bool = False,
) -> CourseContext:
    """Phase 1: Upload sources and generate syllabus."""
    print("\n" + "=" * 60)
    print("PHASE 1: Upload & Syllabus Generation")
    print("=" * 60)

    if not ctx.notebook_id:
        print(f"[INFO] Creating notebook: {ctx.course_name}")
        ctx.notebook_id = adapter.create_notebook(ctx.course_name)
        print(f"[OK] Notebook ID: {ctx.notebook_id}")
        cp.notebook_id = ctx.notebook_id
        save_checkpoint(cp)
    else:
        print(f"[INFO] Using existing notebook: {ctx.notebook_id}")
        adapter.use_notebook(ctx.notebook_id)

    if not skip_upload:
        raw_dir = raw_note_dir(ctx.course_name)
        if not raw_dir.exists():
            raise FileNotFoundError(f"Raw directory not found: {raw_dir}")

        file_count = count_raw_files(ctx.course_name)
        print(f"[INFO] Uploading {file_count} files from {raw_dir}")

        uploaded, skipped = adapter.upload_sources_dir(raw_dir, "*.md")
        print(f"[OK] Uploaded: {uploaded}, Skipped: {skipped}")

        if not adapter.verify_upload(file_count):
            print("[WARN] Upload verification failed, continuing anyway...")
    else:
        print("[INFO] Skipping upload (--skip-upload)")

    syllabus_text = generate_syllabus(ctx, adapter)

    pdir = permanent_note_dir(ctx.course_name)
    pdir.mkdir(parents=True, exist_ok=True)
    syllabus_path = save_syllabus(syllabus_text, ctx.course_name, pdir)
    print(f"[OK] Syllabus saved: {syllabus_path}")

    ctx.chapters = parse_syllabus(syllabus_text)
    print(f"[OK] Parsed {len(ctx.chapters)} chapters")
    for ch in ctx.chapters:
        print(f"  Ch.{ch.index:02d}: {ch.title} ({ch.video_range})")

    # Update checkpoint with chapters
    from lib.checkpoint import ChapterCheckpoint as CC
    cp.chapters = [
        CC(index=ch.index, title=ch.title)
        for ch in ctx.chapters
    ]
    cp.phase1_done = True
    cp.phase = 2
    save_checkpoint(cp)

    return ctx


def phase2_chapter_deep_dive(
    ctx: CourseContext,
    adapter: NotebookLMAdapter,
    cp: PipelineCheckpoint,
    max_rounds: int = 5,
) -> None:
    """Phase 2: Chapter-by-chapter deep-dive."""
    print("\n" + "=" * 60)
    print("PHASE 2: Chapter Deep Dive")
    print("=" * 60)

    if not ctx.chapters:
        pdir = permanent_note_dir(ctx.course_name)
        syllabus_path = pdir / f"{ctx.course_name}_课程大纲.md"
        if syllabus_path.exists():
            ctx.chapters = load_syllabus(syllabus_path)
            print(f"[OK] Loaded {len(ctx.chapters)} chapters from saved syllabus")
        else:
            raise RuntimeError("No chapters found. Run Phase 1 first.")

    total = len(ctx.chapters)
    for i, chapter in enumerate(ctx.chapters, 1):
        ch_cp = next((c for c in cp.chapters if c.index == chapter.index), None)
        if ch_cp and ch_cp.status == "completed":
            print(f"\n[{i}/{total}] SKIP Chapter {chapter.index}: already completed")
            continue

        print(f"\n[{i}/{total}] Processing chapter {chapter.index}: {chapter.title}")
        generate_chapter_note(ctx, chapter, adapter, cp=cp, max_rounds=max_rounds)

    cp.phase2_done = True
    cp.phase = 3
    save_checkpoint(cp)
    print(f"\n[OK] All {total} chapters processed")


def phase3_synthesis(
    ctx: CourseContext,
    adapter: NotebookLMAdapter,
    cp: PipelineCheckpoint,
    anki_count: int = 20,
) -> None:
    """Phase 3: Generate MOC, next steps, Anki."""
    print("\n" + "=" * 60)
    print("PHASE 3: Capstone Synthesis")
    print("=" * 60)

    generate_moc(ctx, adapter)
    generate_next_steps(ctx, adapter)
    generate_anki(ctx, adapter, card_count=anki_count)

    cp.phase3_done = True
    cp.phase = 3
    save_checkpoint(cp)
    print("\n[OK] Phase 3 complete")


def main() -> int:
    _setup_logging()
    parser = _build_argparser()
    args = parser.parse_args()

    if not args.dry_run:
        cfg = load_config()
        cfg.validate()

    raw_dir = Path(args.raw_dir) if args.raw_dir else raw_note_dir(args.course)
    perm_dir = permanent_note_dir(args.course)

    print(f"Course: {args.course}")
    print(f"Raw dir: {raw_dir}")
    print(f"Permanent dir: {perm_dir}")

    try:
        videos = load_videos(args.course)
        print(f"Videos: {len(videos)}")
    except FileNotFoundError:
        videos = []
        print(f"[WARN] No raw videos found in {raw_dir}")

    adapter = _create_adapter(args.dry_run)

    # Determine phase and checkpoint
    cp: PipelineCheckpoint | None = None
    if args.resume:
        cp = load_checkpoint(args.course)
        if cp:
            print(f"[OK] Resumed from checkpoint (updated: {cp.updated_at})")
            phase = cp.phase
            if args.notebook_id:
                cp.notebook_id = args.notebook_id
        else:
            print("[WARN] No checkpoint found, starting fresh")
            phase = args.phase or 1
    elif args.phase:
        phase = args.phase
    else:
        phase, cp = detect_phase_from_checkpoint(args.course)

    if cp is None:
        cp = PipelineCheckpoint(
            course_name=args.course,
            notebook_id=args.notebook_id or "",
            phase=phase,
            total_rounds=args.rounds,
            anki_count=args.anki_count,
        )

    ctx = CourseContext(
        course_name=args.course,
        notebook_id=cp.notebook_id or args.notebook_id or "",
        raw_dir=raw_dir,
        permanent_dir=perm_dir,
        videos=videos,
        chapters=[],
    )

    print(f"\nStarting from Phase {phase}")

    if args.dry_run:
        print("\n[DRY RUN] Would execute:")
        if phase <= 1:
            print(f"  - Phase 1: Create notebook, upload {len(videos)} files, generate syllabus")
        if phase <= 2:
            print(f"  - Phase 2: Deep-dive chapters with {args.rounds} rounds each")
        if phase <= 3:
            print(f"  - Phase 3: MOC, next-steps, {args.anki_count} Anki cards")
        if isinstance(adapter, MockAdapter):
            print(f"\nMock calls recorded: {len(adapter.calls)}")
        return 0

    try:
        if phase <= 1:
            ctx = phase1_upload_and_syllabus(ctx, adapter, cp, skip_upload=args.skip_upload)
            print(f"\n[IMPORTANT] Notebook ID: {ctx.notebook_id}")

        if phase <= 2:
            phase2_chapter_deep_dive(ctx, adapter, cp, max_rounds=args.rounds)

        if phase <= 3:
            phase3_synthesis(ctx, adapter, cp, anki_count=args.anki_count)

        print("\n" + "=" * 60)
        print("PIPELINE COMPLETE")
        print("=" * 60)
        print(f"Output: {perm_dir}")
        print(f"Notebook ID: {ctx.notebook_id}")
        return 0

    except Exception as e:
        logging.exception("Pipeline failed")
        print(f"\n[ERROR] Pipeline failed: {e}")
        if cp and cp.notebook_id:
            print(f"[INFO] To resume: --course {args.course} --resume")
        return 1


if __name__ == "__main__":
    sys.exit(main())
