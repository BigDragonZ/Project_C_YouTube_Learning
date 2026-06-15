"""
Generate chapter notes and course artifacts (MOC, Anki).

Orchestrates:
  - Phase 1: Syllabus generation via NotebookLM
  - Phase 2: Chapter deep-dive with pressure-test rounds
  - Phase 3: MOC, next-steps, Anki generation

Dependencies:
  - lib.adapters.base.NotebookLMAdapter (injected, not hardcoded)
  - lib.prompt_engine (structured prompts, not raw strings)
  - lib.checkpoint (state persistence)
"""

import time
from pathlib import Path
from typing import Optional

from config.notebooklm import load_config
from config.note_paths import (
    chapter_note_path,
    moc_path,
    anki_path,
)
from models.note import Chapter, CourseContext, PressureTestRound
from lib.adapters.base import NotebookLMAdapter
from lib.prompt_engine import get_prompt
from lib.checkpoint import (
    PipelineCheckpoint,
    ChapterCheckpoint,
    save_checkpoint,
)


# ── Pressure test round definitions ──

PRESSURE_ROUNDS: list[PressureTestRound] = [
    PressureTestRound(
        name="定义与分类",
        prompt_template=get_prompt("pressure_definition"),
        focus="definition",
    ),
    PressureTestRound(
        name="数学推导",
        prompt_template=get_prompt("pressure_derivation"),
        focus="derivation",
    ),
    PressureTestRound(
        name="案例对撞",
        prompt_template=get_prompt("pressure_case"),
        focus="case",
    ),
    PressureTestRound(
        name="学术批判",
        prompt_template=get_prompt("pressure_critique"),
        focus="critique",
    ),
    PressureTestRound(
        name="跨章关联",
        prompt_template=get_prompt("pressure_cross"),
        focus="cross",
    ),
]


def _build_chapter_prompt(chapter: Chapter, round_idx: int) -> str:
    """Build the prompt for a specific pressure-test round."""
    if round_idx == 0:
        return get_prompt("chapter_deep_dive").render(video_range=chapter.video_range)

    round_cfg = PRESSURE_ROUNDS[(round_idx - 1) % len(PRESSURE_ROUNDS)]
    return round_cfg.prompt_template.render(
        video_range=chapter.video_range,
        concept_a=chapter.thesis[:50] if chapter.thesis else "核心概念",
        concept_b="相关概念A",
        concept_c="相关概念B",
        theorem=chapter.thesis[:50] if chapter.thesis else "核心定理",
        mechanism=chapter.thesis[:50] if chapter.thesis else "核心机制",
    )


# ── Phase 1: Syllabus ──

def generate_syllabus(
    ctx: CourseContext,
    adapter: NotebookLMAdapter,
) -> str:
    """Generate course syllabus via NotebookLM."""
    print("\n" + "=" * 60)
    print("Phase 1: Generating Syllabus")
    print("=" * 60)

    adapter.use_notebook(ctx.notebook_id)
    adapter.configure_persona(load_config().persona)

    print("[INFO] Asking NotebookLM to generate syllabus...")
    prompt = get_prompt("syllabus")
    response = adapter.ask(prompt.template, timeout=300)

    print(f"[OK] Syllabus received: {len(response)} chars")
    return response


# ── Phase 2: Chapter Deep Dive ──

def generate_chapter_note(
    ctx: CourseContext,
    chapter: Chapter,
    adapter: NotebookLMAdapter,
    cp: Optional[PipelineCheckpoint] = None,
    max_rounds: int = 5,
) -> Path:
    """
    Generate a chapter note through multiple pressure-test rounds.

    Args:
        ctx: Course context
        chapter: Chapter to process
        adapter: NotebookLM adapter (injected dependency)
        cp: Optional checkpoint to update
        max_rounds: Number of pressure-test rounds

    Returns:
        Path to saved chapter note file
    """
    print(f"\n{'=' * 60}")
    print(f"Chapter {chapter.index}: {chapter.title}")
    print(f"Video range: {chapter.video_range}")
    print(f"Rounds: {max_rounds}")
    print("=" * 60)

    adapter.use_notebook(ctx.notebook_id)

    sections: list[str] = []

    header = f"""# Ch.{chapter.index:02d} {chapter.title}

> **Metadata**
> - 署名：DALONG ZHANG
> - 课程：{ctx.course_name}
> - 视频范围：{chapter.video_range}
> - 核心命题：{chapter.thesis}
> - 关联笔记：{' | '.join(chapter.prerequisites) if chapter.prerequisites else '待补充'}

---

"""
    sections.append(header)

    for r in range(max_rounds):
        round_name = (
            "综合深挖" if r == 0 else PRESSURE_ROUNDS[(r - 1) % len(PRESSURE_ROUNDS)].name
        )
        print(f"\n  [Round {r + 1}/{max_rounds}] {round_name}")

        if cp:
            ch_cp = next((c for c in cp.chapters if c.index == chapter.index), None)
            if ch_cp and ch_cp.completed_rounds > r:
                print(f"  [SKIP] Already completed in prior run")
                continue

        prompt = _build_chapter_prompt(chapter, r)
        try:
            response = adapter.ask(prompt, timeout=300)
            sections.append(f"## 第{r + 1}轮：{round_name}\n\n{response}\n\n---\n\n")
            print(f"  [OK] Response: {len(response)} chars")

            if cp:
                ch_cp = next((c for c in cp.chapters if c.index == chapter.index), None)
                if ch_cp:
                    ch_cp.completed_rounds = r + 1
                    ch_cp.status = "running"
                    save_checkpoint(cp)

        except Exception as e:
            print(f"  [WARN] Round failed: {e}")
            sections.append(f"## 第{r + 1}轮：{round_name}\n\n[生成失败: {e}]\n\n---\n\n")
            if cp:
                ch_cp = next((c for c in cp.chapters if c.index == chapter.index), None)
                if ch_cp:
                    ch_cp.status = "failed"
                    ch_cp.error = str(e)[:200]
                    save_checkpoint(cp)

        time.sleep(2)

    content = "\n".join(sections)
    output_path = chapter_note_path(ctx.course_name, chapter.index, chapter.title)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    if cp:
        ch_cp = next((c for c in cp.chapters if c.index == chapter.index), None)
        if ch_cp:
            ch_cp.status = "completed"
            ch_cp.completed_rounds = max_rounds
            save_checkpoint(cp)

    print(f"[OK] Saved: {output_path}")
    return output_path


# ── Phase 3: Capstone Synthesis ──

def generate_moc(
    ctx: CourseContext,
    adapter: NotebookLMAdapter,
) -> Path:
    """Generate Map of Contents (MOC)."""
    print("\n" + "=" * 60)
    print("Phase 3.1: Generating MOC")
    print("=" * 60)

    adapter.use_notebook(ctx.notebook_id)

    prompt = get_prompt("moc").render(course_name=ctx.course_name)
    response = adapter.ask(prompt, timeout=300)

    output_path = moc_path(ctx.course_name)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    header = f"""# {ctx.course_name} 知识地图 (MOC)

> **Metadata**
> - 署名：DALONG ZHANG
> - 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}
> - 章节数：{len(ctx.chapters)}

---

"""
    output_path.write_text(header + response, encoding="utf-8")
    print(f"[OK] MOC saved: {output_path}")
    return output_path


def generate_next_steps(
    ctx: CourseContext,
    adapter: NotebookLMAdapter,
) -> str:
    """Generate next steps / advanced learning path."""
    print("\n" + "=" * 60)
    print("Phase 3.2: Generating Next Steps")
    print("=" * 60)

    adapter.use_notebook(ctx.notebook_id)

    prompt = get_prompt("next_steps").render(course_name=ctx.course_name)
    response = adapter.ask(prompt, timeout=300)

    moc = moc_path(ctx.course_name)
    if moc.exists():
        existing = moc.read_text(encoding="utf-8")
        moc.write_text(
            existing + "\n\n---\n\n# 进阶学习路径\n\n" + response,
            encoding="utf-8",
        )
        print("[OK] Next steps appended to MOC")

    return response


def generate_anki(
    ctx: CourseContext,
    adapter: NotebookLMAdapter,
    card_count: int = 20,
) -> Path:
    """Generate Anki flashcards."""
    print("\n" + "=" * 60)
    print(f"Phase 3.3: Generating Anki Cards ({card_count})")
    print("=" * 60)

    adapter.use_notebook(ctx.notebook_id)

    prompt = get_prompt("anki").render(card_count=card_count)
    response = adapter.ask(prompt, timeout=300)

    output_path = anki_path(ctx.course_name, card_count)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    header = f"""# Anki: {ctx.course_name} ({card_count}张真题卡)

> **Metadata**
> - 署名：DALONG ZHANG
> - 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}
> - 难度：研究生/CFA三级

---

"""
    output_path.write_text(header + response, encoding="utf-8")
    print(f"[OK] Anki saved: {output_path}")
    return output_path
