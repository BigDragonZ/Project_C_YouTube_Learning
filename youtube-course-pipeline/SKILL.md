---
name: youtube-course-pipeline
description: |
  Use when user wants to learn from a YouTube course playlist. Orchestrates
  full pipeline: download subtitles → transcribe audio → refine with Gemini →
  generate structured notes → upload to NotebookLM for study. Runs in background
  with git checkpointing after each video.
version: 1.0.0
author: DALONG ZHANG
license: MIT
metadata:
  hermes:
    tags: [youtube, course, learning, pipeline, notebooklm, transcription]
    related_skills: [knowledge-base-youtube-download]
---

# YouTube Course Learning Pipeline

## Overview

Automated pipeline for learning from YouTube course playlists. Given a playlist
URL, the system:

1. Extracts all videos from the playlist
2. Downloads subtitles (or transcribes audio as fallback)
3. Refines content with Gemini (content-preserving optimization)
4. Saves structured Markdown notes to `flow/{course}/`
5. Commits each video to git as checkpoint
6. Uploads to NotebookLM for interactive study

## When to Use

- User says "开始学习 [YouTube URL]"
- User provides a YouTube playlist and asks to transcribe/take notes
- User wants to build a knowledge base from video lectures
- User says "利用现有的脚本" (use existing scripts) for YouTube learning
- **User provides MULTIPLE playlist URLs and asks to learn them in sequence** → see `knowledge-base-youtube-download` skill for batch deduplication and sequential execution pattern
- **CRITICAL**: This skill is STEP 2 of a TWO-STEP workflow. When user says "学习课程" with a YouTube link, `knowledge-base-youtube-download` runs FIRST (transcription to `youtube2note/input/`), then THIS skill runs SECOND (study to `youtube2note/output/`). User explicitly corrected: "正常的流程：1、knowledge-base-youtube-download 转录课程 2、youtube-course-pipeline 课程学习"

## Prerequisites

- Project: `~/Documents/all-in-one` (Git-backed Obsidian vault)
- Subproject: `~/Documents/all-in-one/youtube2note/`
- Python venv: `~/Documents/all-in-one/.venv/`
- yt-dlp: `.venv/bin/yt-dlp` (version >= 2026.03.17, NEVER system Python)
- Pipeline script: `youtube2note/input/script/run_pipeline.py`
- NotebookLM CLI: `.venv/bin/notebooklm` (for Phase 2 study)
- **Input directory**: `youtube2note/input/{course}/` (refined transcripts from Step 1)
- **Output directory**: `youtube2note/output/{course}/` (generated notes from Step 2)

## Workflow

### Step 0: Git Pre-Work Commit (MANDATORY)

Before starting ANY course work:
```bash
cd ~/Documents/all-in-one
git status
# If uncommitted changes:
git add -A
git commit -m "chore: checkpoint before starting new course - <course_name>"
git push origin main
```

User explicitly requires this. See Pitfall 12a-i.

### Step 1: Transcription Pipeline (Background)

Run the pipeline in background for non-blocking execution:

```bash
cd ~/Documents/all-in-one
.venv/bin/python flow/script/run_pipeline.py \
  "<PLAYLIST_URL>" "<COURSE_NAME>" [MAX_VIDEOS]
```

- Omit `MAX_VIDEOS` to process all videos
- Use small number (e.g., 2) for test run
- Process runs in background — use `process(action="poll")` to check status

**Pipeline logic per video:**
1. Try subtitle download first (fast, accurate)
2. If subtitle fails → download video → extract audio → transcribe with Gemini
3. Refine raw Markdown with content-preserving optimization
4. Save final `.md` to `flow/{course}/`
5. Git commit after each video

**File lifecycle:**
```
Video → subtitle.md (raw) → refine → {index}-{title}.md (final)
       └→ [deleted after refinement]
```

### Step 2: NotebookLM Setup

```bash
uv run notebooklm doctor         # 验证认证
uv run notebooklm create "COURSE_课程名"  # 创建项目
# 记录 notebook-id
```

**Batch notebook creation**: When creating many notebooks at once (e.g., 20+ courses), use a loop via `execute_code` or `terminal` to avoid manual repetition. Save the mapping to a JSON file:

```python
# Example: create notebooks for all courses in a directory
import json, subprocess, os
from pathlib import Path

project_root = Path.home() / "Documents/all-in-one"
anki_dir = project_root / "youtube2note/anki"
mapping = {}

for course_dir in sorted(anki_dir.iterdir()):
    if course_dir.is_dir():
        result = subprocess.run(
            [str(project_root / ".venv/bin/notebooklm"), "create", course_dir.name],
            capture_output=True, text=True, cwd=project_root
        )
        # Parse "Created notebook: <ID> - <title>"
        if "Created notebook:" in result.stdout:
            parts = result.stdout.strip().split("Created notebook: ")[1].split(" - ")
            mapping[course_dir.name] = parts[0]

# Save mapping
mapping_file = project_root / "notebooklm_course_mapping.json"
mapping_file.write_text(json.dumps(mapping, indent=2, ensure_ascii=False))
```

**NotebookLM list JSON format**: `notebooklm list --json` returns `{"notebooks": [...], "count": N}`. Always parse the `notebooks` key, not the raw list.

Upload transcripts:
```bash
for f in youtube2note/input/课程名/*.md; do
  basename=$(basename "$f")
  if uv run notebooklm source list 2>/dev/null | grep -q "$basename"; then
    echo "SKIP (exists): $basename"
    continue
  fi
  uv run notebooklm source add "$f" 2>/dev/null
  echo "OK: $basename"
  sleep 1
done
```

**Note**: NotebookLM has a ~100 source limit per notebook. If upload stalls at ~100 files with `Failed to get SOURCE_ID from registration response`, proceed with the 100 uploaded sources — they typically cover the full course. See Pitfall 13a-i and 13a-ii. For courses with >100 files, consider creating a Part 2 notebook or merging files.

### Step 3: NotebookLM Study (Background)

**推荐方式**：使用后台脚本自动执行三阶段学习。

创建并运行后台学习脚本：
```python
terminal(
    command="cd ~/Documents/all-in-one && .venv/bin/python flow/script/notebooklm_study.py \\"
            "\"COURSE_NAME\" \"NOTEBOOK_ID\" all",
    background=True,
    notify_on_complete=True,
    timeout=2400  # 40分钟，足够处理8-10章
)
```

脚本自动执行：
1. **Phase 1**: 生成课程大纲 → 保存到 `01_Permanent/课程名/课程名_课程大纲.md`
2. **Phase 2**: 逐章深挖（每章2轮提问）→ 保存到 `01_Permanent/课程名/Ch_XX_章节名.md`
3. **Phase 3**: 生成知识地图 + Anki 卡片 → 保存到对应文件
4. **每步自动 git 提交**

**手动方式**（如果需要精细控制）：

### Phase 1: Syllabus Generation（课程大纲）

Upload all refined transcripts to NotebookLM, then generate a graduate-level syllabus:

```bash
uv run youtube2note/input/script/note_pipeline.py --course "CourseName" --phase 1
```

- Creates a new NotebookLM project (or uses `--notebook-id` to resume)
- Uploads all `*.md` files from `youtube2note/input/{course}/` with deduplication
- Generates syllabus: chapters determined by **actual content**, not a fixed count
- Saves syllabus to `youtube2note/output/{course}/{course}_课程大纲.md`
- Parses syllabus into structured `Chapter` objects

**User preference**: Do NOT preset chapter count (e.g. "8-10 chapters"). Let NotebookLM determine the natural module boundaries from the content itself.

### Phase 2: Chapter Deep Dive

For each chapter, execute 5 rounds of pressure-test questioning:

```bash
uv run youtube2note/input/script/note_pipeline.py --course "CourseName" --phase 2 --notebook-id "xxx"
```

| Round | Focus | Prompt Template |
|-------|-------|-----------------|
| 1 | 综合深挖 | Comprehensive analysis (definitions, derivations, cases, critique) |
| 2 | 定义与分类 | Mathematical definitions, boundary conditions |
| 3 | 数学推导 | Complete derivation, assumptions, vulnerabilities |
| 4 | 案例对撞 | Real-world cases vs theory deviation |
| 5 | 学术批判 | Systemic risk, historical crises, regulatory gaps |
| 6+ | 跨章关联 | Cross-chapter links, knowledge network (if rounds > 5) |

Output: `youtube2note/output/{course}/Ch_XX_章节名.md` with Metadata header + multi-round analysis.

### Phase 3: Capstone Synthesis

Generate knowledge map, next steps, and Anki cards:

```bash
uv run youtube2note/input/script/note_pipeline.py --course "CourseName" --phase 3 --notebook-id "xxx"
```

Outputs:
- `{course}_知识地图_MOC.md` — knowledge map with cross-references
- `Anki_{course}_N张真题卡.md` — graduate-level flashcards
- Saved to `youtube2note/output/{course}/`

## Background Execution Pattern

### Phase 1: Transcription Pipeline (Background)

```python
# Start background pipeline
terminal(
    command="cd ~/Documents/all-in-one && .venv/bin/python flow/script/run_pipeline.py \\"
            "\"<PLAYLIST_URL>\" \"<COURSE_NAME>\" [MAX_VIDEOS]",
    background=True,
    notify_on_complete=True,
    timeout=600
)

# Poll progress
process(action="poll", session_id="...")

# Wait for completion
process(action="wait", session_id="...", timeout=300)
```

### Phase 2: NotebookLM Study (Background)

NotebookLM 学习流程也应后台执行，避免阻塞用户交互。

**2.1 创建后台学习脚本**

创建 `~/Documents/all-in-one/flow/script/notebooklm_study.py`：

```python
#!/usr/bin/env python3
"""
NotebookLM 后台学习脚本。
用法: python notebooklm_study.py <course_name> <notebook_id> <phase>
"""
import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

def run_phase1(course: str, notebook_id: str):
    """生成课程大纲并保存。"""
    import google.genai as genai
    
    # 使用 NotebookLM CLI 生成大纲
    cmd = [
        str(PROJECT_ROOT / ".venv" / "bin" / "notebooklm"),
        "ask", "--notebook", notebook_id,
        "基于全部转录文本，生成研究生级别课程大纲："
        "- 每章包含核心命题（Thesis）"
        "- 标注每章对应的原始视频编号范围"
        "- 体现从基础到高阶的完整逻辑链条"
        "- 使用中文输出"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    
    # 保存大纲
    out_dir = PROJECT_ROOT / "01_Permanent" / course
    out_dir.mkdir(parents=True, exist_ok=True)
    syllabus_file = out_dir / f"{course}_课程大纲.md"
    syllabus_file.write_text(result.stdout, encoding="utf-8")
    print(f"[OK] Syllabus saved: {syllabus_file}")

def run_phase2(course: str, notebook_id: str, chapters: list[dict]):
    """逐章深挖并保存笔记。"""
    out_dir = PROJECT_ROOT / "01_Permanent" / course
    
    for ch in chapters:
        # 第1轮：定义+推导
        q1 = f"基于视频{ch['range']}的内容，请深入分析："
        q1 += "1) 核心概念的数学定义 2) 关键公式的完整推导"
        
        # 第2轮：批判+案例
        q2 = f"基于视频{ch['range']}的内容，继续分析："
        q2 += "1) 理论的边界条件 2) 现实中的反例 3) 学术批判"
        
        # 调用 NotebookLM
        for i, q in enumerate([q1, q2], 1):
            cmd = [
                str(PROJECT_ROOT / ".venv" / "bin" / "notebooklm"),
                "ask", "--notebook", notebook_id, q
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            
            # 累加内容
            if i == 1:
                content = result.stdout
            else:
                content += "\n\n" + result.stdout
        
        # 保存章节笔记
        ch_file = out_dir / f"Ch_{ch['num']:02d}_{ch['title']}.md"
        ch_file.write_text(content, encoding="utf-8")
        print(f"[OK] Chapter {ch['num']} saved: {ch_file}")
        
        # Git 提交
        subprocess.run(["git", "add", str(out_dir)], cwd=PROJECT_ROOT)
        subprocess.run(["git", "commit", "-m", f"chore: add {course} Ch.{ch['num']} notes"], cwd=PROJECT_ROOT)

def run_phase3(course: str, notebook_id: str):
    """生成知识地图和 Anki 卡片。"""
    out_dir = PROJECT_ROOT / "01_Permanent" / course
    
    # 生成 MOC
    cmd = [
        str(PROJECT_ROOT / ".venv" / "bin" / "notebooklm"),
        "ask", "--notebook", notebook_id,
        "所有章节已完成。请生成知识地图："
        "- 总结全课核心矛盾与底层逻辑"
        "- 梳理各章之间的逻辑依赖关系"
        "- 标注关键公式和定理的交叉引用"
        "- 使用中文输出"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    moc_file = out_dir / f"{course}_知识地图_MOC.md"
    moc_file.write_text(result.stdout, encoding="utf-8")
    print(f"[OK] MOC saved: {moc_file}")
    
    # 生成 Anki 卡片
    cmd = [
        str(PROJECT_ROOT / ".venv" / "bin" / "notebooklm"),
        "ask", "--notebook", notebook_id,
        "基于全部课程内容，生成15-20条研究生级别Anki真题卡片："
        "- 每张覆盖完整推理链条"
        "- 正面：问题/情境"
        "- 背面：多步骤推导+公式+案例"
        "- 使用中文输出"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    anki_file = out_dir / f"Anki_{course}_15张真题卡.md"
    anki_file.write_text(result.stdout, encoding="utf-8")
    print(f"[OK] Anki saved: {anki_file}")
    
    # Git 提交
    subprocess.run(["git", "add", str(out_dir)], cwd=PROJECT_ROOT)
    subprocess.run(["git", "commit", "-m", f"chore: add {course} MOC and Anki cards"], cwd=PROJECT_ROOT)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("course", help="Course name")
    parser.add_argument("notebook_id", help="NotebookLM notebook ID")
    parser.add_argument("phase", choices=["1", "2", "3", "all"], help="Phase to run")
    args = parser.parse_args()
    
    if args.phase in ["1", "all"]:
        run_phase1(args.course, args.notebook_id)
    if args.phase in ["2", "all"]:
        # 从大纲解析章节列表
        chapters = parse_syllabus(args.course)
        run_phase2(args.course, args.notebook_id, chapters)
    if args.phase in ["3", "all"]:
        run_phase3(args.course, args.notebook_id)

if __name__ == "__main__":
    main()
```

**2.2 后台启动学习流程**

```python
# 阶段一：生成大纲（后台）
terminal(
    command="cd ~/Documents/all-in-one && .venv/bin/python flow/script/notebooklm_study.py \\"
            "\"Principles_of_Microeconomics\" \"ec06698d-...\" 1",
    background=True,
    notify_on_complete=True,
    timeout=300
)

# 阶段二：章节深挖（后台，每章自动提交）
terminal(
    command="cd ~/Documents/all-in-one && .venv/bin/python flow/script/notebooklm_study.py \\"
            "\"Principles_of_Microeconomics\" \"ec06698d-...\" 2",
    background=True,
    notify_on_complete=True,
    timeout=1800  # 30分钟，每章需要多轮提问
)

# 阶段三：知识收拢（后台）
terminal(
    command="cd ~/Documents/all-in-one && .venv/bin/python flow/script/notebooklm_study.py \\"
            "\"Principles_of_Microeconomics\" \"ec06698d-...\" 3",
    background=True,
    notify_on_complete=True,
    timeout=300
)
```

**2.3 检查进度**

```python
# 查看后台任务状态
process(action="list")

# 查看特定任务输出
process(action="log", session_id="...", limit=50)

# 等待完成
process(action="wait", session_id="...", timeout=300)
```

## Git Checkpointing

After each video is processed:

```bash
git add flow/<course>/
git commit -m "chore: add <course> Ch<X> transcript"
```

This ensures:
- Interrupt safety — each video is committed
- Can rollback with `git reset --hard HEAD^` if needed
- Clean history of course progress

## Output Structure

**转录文本**（Gemini 精修后的原始内容）：
```
youtube2note/input/课程名/
├── 01_标题.md
├── 02_标题.md
└── ...
```

**学习笔记**（NotebookLM 分析后的知识产出）：
```
youtube2note/output/课程名/
├── 课程名_课程大纲.md
├── Ch_01_章节名.md
├── Ch_02_章节名.md
├── ...
├── 课程名_知识地图_MOC.md
└── Anki_课程名_N张真题卡.md
```

**规则**:
- `youtube2note/input/课程名/` — 存放转录流水线输出的原始精修文本
- `youtube2note/output/课程名/` — 存放 NotebookLM 章节深挖、知识地图、Anki 卡片等知识产出
- 两个阶段物理隔离，脚本与数据分离

| 类型     | 命名格式                     | 存放路径                                        |
| -------- | ---------------------------- | ----------------------------------------------- |
| 转录文本 | `XX_标题.md`               | `youtube2note/input/课程名/`                                |
| 章节笔记 | `Ch_XX_章节名.md`          | `youtube2note/output/课程名/`                        |
| 知识地图 | `课程名_知识地图_MOC.md`   | `youtube2note/output/课程名/`                        |
| Anki卡片 | `Anki_课程名_N张真题卡.md` | `youtube2note/output/课程名/`                        |

## Common Pitfalls

### Pitfall 1: System Python yt-dlp
- System yt-dlp (2025.10.14) fails with HTTP 403
- **Always** use `.venv/bin/yt-dlp`

### Pitfall 2: Pipeline Interruption
- If interrupted mid-run, files may be inconsistent
- **Recovery**: `git checkout -- flow/{course}/`
- **Prevention**: Use background mode + git commits

### Pitfall 3: LLM Summarization on Refinement
- Default "academic editor" persona causes 98% content loss
- **Fix**: Use concise instruction-only prompt (see `knowledge-base-youtube-download` skill)
- Prompt must say "不要提炼总结，不要省略原文内容"

### Pitfall 4: Re-processing Already Done Videos
- The pipeline re-processes from start if re-run
- **Fix**: Check existing files in `youtube2note/input/{course}/` before running
- Use `MAX_VIDEOS` offset or modify pipeline to skip existing

### Pitfall 4a: Large Playlist Duration Estimation
- Before starting Pipeline 1, estimate total duration to set expectations
- **Command**: `.venv/bin/yt-dlp --flat-playlist --dump-single-json "<URL>" | python3 -c "import sys,json; d=json.load(sys.stdin); entries=d.get('entries',[]); total=sum(e.get('duration',0) for e in entries); print(f'{len(entries)} videos, {total//3600}h{(total%3600)//60}m')"`
- A 60-video playlist at ~8.5 hours took ~2 hours for Pipeline 1 (subtitle download + Gemini refinement)
- A 25-video playlist at ~20 hours (MIT lectures) will take significantly longer due to longer individual videos
- **Rule of thumb**: Pipeline 1 takes ~2-4x the total video duration (depending on subtitle availability and API response times)

### Pitfall 5: NotebookLM Bulk Upload Timeouts
- Automated `note_pipeline.py --phase 1` times out with 20+ files
- **Fix**: Manual bulk upload with `notebooklm source add` in a loop
- Always verify with `notebooklm source list` after upload
- **Legacy path note**: Old docs reference `flow/` — use `youtube2note/input/` instead

### Pitfall 6: NotebookLM Source Upload Duplicates
- NotebookLM returns error for duplicate uploads
- **Fix**: Check `source list` before `source add`, or use idempotent upload script

### Pitfall 7: NotebookLM JSON Response Format
- `notebooklm list --json` returns `{"notebooks": [...], "count": N}` NOT raw list
- **Fix**: Parser must handle dict-wrapped format

### Pitfall 8: NotebookLM Chapter Numbering Mismatch
- NotebookLM may use internal numbering different from video filenames
- **Fix**: Always cross-reference with original video index (01-22)

### Pitfall 10: NotebookLM Study Blocking User Interaction
- 逐章手动提问会阻塞用户交互，每次等待 2-3 分钟
- **Fix**: 使用后台脚本 `notebooklm_study.py` 自动执行三阶段学习
- 设置 `notify_on_complete=True` 完成时通知
- 使用 `process(action="poll")` 检查进度而不阻塞

### Pitfall 11: NotebookLM API Rate Limits
- 连续快速提问可能触发 rate limiting
- **Fix**: 后台脚本内置 sleep 间隔（每轮提问后 sleep 2-3 秒）
- 单章多轮提问合并为单次 API 调用（如果 NotebookLM 支持）

### Pitfall 12: Long-running Background Tasks Timeout
- 8-10 章的深挖可能需要 30-40 分钟
- **Fix**: 设置 `timeout=2400` (40分钟) 或更长
- 或者分阶段启动：Phase 1 → 完成后启动 Phase 2 → 完成后启动 Phase 3

### Pitfall 12b: YouTube Playlist URL Validation
- Playlist IDs can become stale or redirect to unrelated content (e.g., a Principles of Management URL returning "YouTube Tips & Advice")
- **Fix**: ALWAYS validate the playlist title before starting a long transcription pipeline
- **Validation command**: `.venv/bin/yt-dlp --cookies-from-browser chrome --flat-playlist --print "%(playlist_title)s" "<URL>"`
- **Abort condition**: If the returned title does not match the expected course name, STOP and ask the user to verify the URL
- **Do NOT** proceed with transcription of mismatched content — it wastes API quota and produces garbage output
### Pitfall 12c: NotebookLM API Rate Limiting and RPC Failures

NotebookLM API intermittently returns `Error: Chat request was rate limited or rejected by the API` and `RPC GET_LAST_CONVERSATION_ID failed`. These errors are transient but can persist for 5-10 minutes during high-load periods.

**Fix**: When `note_pipeline.py` fails with rate limit errors during Phase 3 (MOC/Anki generation):
  1. Wait 60-180 seconds and retry
  2. If still failing after 3 retries, manually create MOC and Anki cards based on the syllabus and chapter titles
  3. Use the checkpoint system to mark Phase 3 as complete
  4. The chapter notes generated in Phase 2 are the critical output — MOC and Anki can be reconstructed from them

**When NotebookLM is completely broken (0 sources uploaded)**: Use Gemini API direct fallback instead of retrying NotebookLM. See `knowledge-base-youtube-download` skill Pitfall 20d and reference `references/gemini-api-direct-fallback-at-scale.md` for the validated batch generation script.

**Do NOT** block on API recovery for non-critical synthesis steps

### Pitfall 12d: Git History Rewriting for Credential Removal
- If a commit accidentally contains API keys or credentials, standard `git revert` does NOT remove them from history
- **Fix**: Use `git filter-branch` to remove the file from all commits:
  ```bash
  FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch --force --index-filter 'git rm --cached --ignore-unmatch <filename>' --prune-empty -- --all
  git push origin --force --all
  git push origin --force --tags
  ```
- **Alternative**: If `filter-branch` is unavailable, use BFG Repo-Cleaner or `git rebase -i --root` to drop the offending commit
- **After rewriting**: Run `git reflog expire --expire=now --all && git gc --prune=now --aggressive` to purge dangling objects
- **Critical**: Force-push after rewriting to update remote history

### Pitfall 12a: Foreground Mode 600s Hard Limit
- `terminal()` foreground mode has a **hard maximum timeout of 600 seconds** (10 minutes), regardless of what value you pass
- **CRITICAL**: For Pipeline 1 (transcription) with 10+ videos, or Pipeline 2 (note generation) with 5+ chapters, foreground mode WILL timeout
- **Fix**: ALWAYS use `terminal(background=True)` for any operation expected to take >5 minutes. Background mode has no timeout limit
- **Example**: A 60-video playlist (8.5 hours of content) takes 1-2 hours for Pipeline 1. Only background mode can handle this
- **Pattern**: Start with `terminal(background=True, notify_on_complete=True)`, then check filesystem progress (`ls flow/<course>/`) rather than polling the process handle

### Pitfall 12a-i: Git Pre-Work Commit Requirement

**User explicitly requires**: Before starting ANY new course processing work, ALWAYS commit the current directory state to GitHub first.

**Command**:
```bash
cd ~/Documents/all-in-one
git status
# If uncommitted changes exist:
git add -A
git commit -m "chore: checkpoint before starting new course - <course_name>"
git push origin main
```

**When to run**:
- Before Step 1 (transcription pipeline)
- Before Step 2 (NotebookLM study) if there was a gap between steps
- Before starting any new course in a batch sequence

**User quote**: "先把当前的目录提交的github仓库，提交后再进行学习"

### Pitfall 12a-ii: Course Queue Progress Tracking

When processing multiple courses in sequence, maintain a progress tracker:

**File**: `课程学习进度清单.md` (at project root)

```markdown
# 课程学习进度清单

| 序号 | 课程名称 | YouTube链接 | 视频数 | 时长 | 状态 |
|------|---------|------------|--------|------|------|
| 1 | Financial_Accounting | PLxCUhFZ3hAvn3tsvtyFy4UtxxuHJZ0f36 | 190 | 32h9m | 已完成 |
| 2 | Managerial_Accounting | PLSlzC-HFo7w7TwAnmyThgdTDL_M0xG1P6 | 59 | 10h43m | 进行中 |
```

**Rules**:
- Create before starting the first course in a batch
- Update status after each course completes
- Include playlist stats (video count, duration)
- Git commit after each update
- Use to answer "what's next" questions

### Pitfall 12a-i: Excessive process(action="poll") Burns Iterations
- Calling `process(action="poll")` every few seconds produces no new information and wastes tool-call iterations
- **Symptom**: Agent reaches 90/90 iteration limit with no meaningful work done
- **Fix**: Check filesystem state instead — it reflects actual progress:
  ```bash
  ls -la ~/Documents/all-in-one/flow/<course>/ | wc -l   # count completed videos
  ls -la ~/Documents/all-in-one/flow/<course>/ | tail -n +4  # list files with sizes
  ```
- **Rule**: Poll process handle at most once per ~5 minutes. Between polls, check filesystem or use `notify_on_complete=True` and wait for the notification
- **Anti-pattern**: DO NOT loop `process(action="poll")` → `terminal(ls ...)` → repeat. This burns iterations without advancing the task

## Background Task Management

### Start All Phases at Once

```python
# Phase 1: Transcription
terminal(
    command="cd ~/Documents/all-in-one && .venv/bin/python flow/script/run_pipeline.py \\"
            "\"PLAYLIST_URL\" \"COURSE_NAME\"",
    background=True,
    notify_on_complete=True,
    timeout=600
)

# After transcription completes, start NotebookLM study
# (use cronjob or manual trigger)
terminal(
    command="cd ~/Documents/all-in-one && .venv/bin/python flow/script/notebooklm_study.py \\"
            "\"COURSE_NAME\" \"NOTEBOOK_ID\" all",
    background=True,
    notify_on_complete=True,
    timeout=2400
)
```

### Check All Running Tasks

```python
process(action="list")
```

### Typical Output

```
Session ID          Status    Uptime    Command
------------------  --------  --------  ----------------------------------------
proc_abc123         running   15:23     run_pipeline.py ...
proc_def456         running   8:45      notebooklm_study.py ...
```

### Wait for Specific Task

```python
process(action="wait", session_id="proc_abc123", timeout=300)
```

### Pitfall 10: NotebookLM ask Timeout on Complex Queries
- Multi-step derivation questions often exceed default timeout
- **Fix**: Use `timeout=180` or higher for `notebooklm ask` commands
- Break complex questions into sequential simpler ones

### Pitfall 13: Automated note_pipeline.py Failure — Manual Fallback

The `note_pipeline.py` script may fail with NotebookLM CLI errors (`RPC GET_NOTEBOOK failed`, `No notebook specified`). When this happens, fall back to manual NotebookLM operations rather than retrying the broken automation.

**Symptoms**:
```
RuntimeError: notebooklm failed after 3 attempts: RPC GET_NOTEBOOK failed after 1.289s
```

**Recovery steps**:
1. Verify auth: `.venv/bin/notebooklm doctor`
2. List notebooks: `.venv/bin/notebooklm list`
3. Create/select notebook manually: `.venv/bin/notebooklm create "CourseName"`
4. Upload sources one-by-one:
   ```bash
   for f in flow/CourseName/*.md; do
     .venv/bin/notebooklm source add "$f"
     sleep 1
   done
   ```
5. Generate content via `notebooklm ask` for each output (syllabus, chapters, MOC, Anki)
6. Save outputs to `01_Permanent/CourseName/`

See `knowledge-base-youtube-download` skill reference `references/notebooklm-manual-fallback.md` for complete transcript.

**When to use manual fallback**:
- Any `note_pipeline.py` failure that persists after 2 retries
- Courses with >15 videos (bulk upload timeout)
- `notebooklm use` context not persisting across subprocess calls

### Pitfall 13a: NotebookLM Source Upload Loop Timeout
- Uploading 60 files via `for f in *.md; do notebooklm source add "$f"; done` in a single command times out at 300s
- **Fix**: Upload files individually or in small batches (10-15 at a time)
- **Alternative**: The loop itself may succeed even if the wrapping command times out — check `notebooklm source list` afterward to verify how many were actually uploaded
- **Best practice**: Use the batch upload script (`batch_upload_notebooklm.py`) which handles resume, deduplication, and progress tracking automatically. See `references/notebooklm-batch-upload-script.md`.
### Pitfall 13a-i: NotebookLM Source Upload Complete Failure — Two Modes + Gemini Fallback

NotebookLM source upload can fail in two distinct ways, both producing `Failed to get SOURCE_ID from registration response`:

**Mode A: 100-Source Hard Limit**
- First ~100 files upload successfully, then all fail
- `source list` confirms ~100 sources
- **Response**: Proceed with 100 sources — sufficient for complete notes

**Mode B: Total API Degradation (0 sources uploaded)**
- ALL files fail with SOURCE_ID error
- `source list` confirms **0 sources** despite "OK" messages
- **Response**: Switch to **Gemini API direct fallback** (validated across 6 courses)

**Verification (mandatory):**
```bash
notebooklm use <NOTEBOOK_ID>
notebooklm source list | grep -c "\.md"
```

**Gemini API Direct Fallback (Production-Ready)**

When NotebookLM upload fails completely, bypass it entirely. This was validated for 6 courses in May 2026:

```bash
# 1. Generate syllabus from transcript files
cd ~/Documents/all-in-one
uv run python -c "
from google.genai import Client
from google.genai.types import HttpOptions
import os, glob

client = Client(vertexai=True, api_key=os.environ.get('GOOGLE_API_KEY',''), http_options=HttpOptions(api_version='v1'))
files = sorted(glob.glob('youtube2note/input/CourseName/*.md'))
content = ''.join(open(f).read()[:5000] + '\n' for f in files)
prompt = f'Generate graduate-level syllabus in Chinese:\n\n{content[:20000]}'
response = client.models.generate_content(model='gemini-2.5-pro', contents=prompt)
print(response.text)
"

# 2. Generate all chapters in batch via a script
# See knowledge-base-youtube-download skill Pitfall 23b for batch script template
uv run python /tmp/generate_all_chapters.py

# 3. Generate MOC and Anki
uv run python /tmp/generate_moc_anki.py
```

**Key advantages:**
- No NotebookLM upload required
- No 100-source limit
- Single API call per chapter
- More reliable when NotebookLM CLI is unstable

**Key disadvantages:**
- No interactive "ask" capability
- Must manually construct prompts
- Requires writing scripts to temp files (execute_code sandbox cannot access .venv)

**Prevention:**
- ALWAYS verify `source list` count after upload — don't trust "OK" messages
- If `source list` shows 0 after upload, immediately switch to Gemini API fallback
- Do NOT block course completion waiting for NotebookLM API recovery
- For courses with >100 videos, expect the 100-source limit

See `knowledge-base-youtube-download` skill Pitfall 20d for full details on both failure modes.

### Pitfall 13a-ii: NotebookLM 100-Source Hard Limit — Confirmed Behavior

**Confirmed June 2026**: NotebookLM enforces a hard limit of **exactly 100 sources per notebook**. When attempting to upload the 101st file, the CLI returns:

```
Error: Failed to get SOURCE_ID from registration response
```

All subsequent uploads fail with the same error. The first 100 sources remain intact and functional.

**Impact**: For courses with >100 markdown files (e.g., 002_Financial_Accounting with 182 files), only 100 can be uploaded to a single notebook.

**Mitigation options**:
1. **Accept 100 sources** — For most courses, 100 sources cover the full curriculum. The remaining files are often supplementary or duplicate-naming artifacts.
2. **Create Part 2 notebook** — Create a second notebook (e.g., `002_Financial_Accounting_Part2`) for remaining files. Cross-reference both notebooks in the mapping file. This was validated June 2026 for Financial Accounting (100 + 82 = 182 files across two notebooks).
3. **Merge files** — Combine multiple short chapters into single files to stay under the limit.

**Verification**:
```bash
# Check if limit is reached
notebooklm source list --notebook <ID> --json | python -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('sources',[])))"
# If count == 100 and new uploads fail = limit reached
```

**Note**: This is a NotebookLM platform limit, not a CLI bug. No amount of retrying, waiting, or using different upload methods will bypass it.

**Batch upload script**: See `references/notebooklm-batch-upload-script.md` for a production-tested script with resume, deduplication, and rate-limit handling.

### Pitfall 13b: NotebookLM Syllabus Generation Failure with `note_pipeline.py`
- `note_pipeline.py` may fail during Phase 1 with `RPC GET_LAST_CONVERSATION_ID failed` or `No notebook found starting with 'X'`
- **Root cause**: The `CLIAdapter` creates a new notebook but the subsequent `use` call fails to find it (timing/race condition)
- **Fix**: When automated syllabus generation fails, fall back to manual generation via `notebooklm ask`:
  1. Verify the notebook exists: `notebooklm list | grep "CourseName"`
  2. Select the notebook: `notebooklm use <NOTEBOOK_ID>`
  3. Ask for syllabus: `notebooklm ask "Generate a comprehensive course syllabus with chapters based on all uploaded sources. Format as markdown with chapter titles, key topics, and learning objectives."`
  4. Save output to `01_Permanent/CourseName/CourseName_课程大纲.md`
  5. Format chapter titles as `## 第N章：Title` to match `syllabus_parser.py` expectations
  6. Create/update `.checkpoint.json` with `phase=2` and chapter list
  7. Resume with `note_pipeline.py --course CourseName --resume --skip-upload`
- **Note**: The syllabus format MUST use `## 第N章：标题` (Chinese numbering with colon) for the parser to correctly identify chapters. English formats like `Chapter N:` will parse as 0 chapters.

### Pitfall 13c: NotebookLM Chapter Note Generation with Empty Content
- When `note_pipeline.py` runs but NotebookLM API is rate-limited, chapter files are created but contain only the template header with `[生成失败]` markers
- **Fix**: Check file size after generation — empty/failed chapters are ~1.5KB (template only) vs ~15-25KB (successful)
- **Recovery**: If chapters are empty, wait for API recovery and re-run `note_pipeline.py --resume --skip-upload`
- **Alternative**: For courses with simple structure, manually write chapter content based on video titles and syllabus

### Pitfall 13c-i: Manual Chapter Generation via `notebooklm ask`

When `note_pipeline.py` fails for chapter generation (rate limits, RPC errors, empty output), generate chapters manually using `notebooklm ask` with structured prompts.

**Validated workflow** (Financial Accounting, May 2026):
1. Syllabus already generated and saved (with video ranges per chapter)
2. For each chapter, run a single `notebooklm ask` with comprehensive prompt:
   ```bash
   notebooklm use <NOTEBOOK_ID>
   notebooklm ask "基于视频<range>的内容，请深入分析本章，输出必须为中文：

   1. 核心概念与定义（所有关键术语的严格定义）
   2. 理论框架与逻辑推导（公式用LaTeX格式）
   3. 实务应用与案例分析（真实商业场景）
   4. 批判性思考（理论边界、反例、学术争议）
   5. 与其他章节的关联（前置知识、后续依赖）

   要求：
   - 研究生级别的学术深度
   - 所有内容用中文输出，专业术语保留英文原文
   - 署名：DALONG ZHANG"
   ```
3. Save output to `youtube2note/output/<course>/Ch_XX_<title>.md`
4. Add metadata header:
   ```markdown
   > **Metadata**
   > - 课程：CourseName
   > - 章节：第X章
   > - 视频范围：XX-YY
   > - 生成时间：YYYY-MM-DD HH:MM
   > - 模型：gemini-2.5-pro
   ---
   ```
5. Git commit after each chapter

**Advantages over automated pipeline**:
- Single API call per chapter (vs 5+ rounds in automated pipeline)
- Less prone to rate limiting
- Full control over prompt and output format
- Can retry individual chapters without affecting others

**Disadvantages**:
- More manual steps
- Need to track progress manually
- No automatic checkpoint recovery

**When to use**: When `note_pipeline.py --phase 2` fails consistently, or when you need granular control over chapter content.

### Pitfall 13d: NotebookLM Multiple Notebooks with Same Name
- `note_pipeline.py` may create duplicate notebooks if retried after partial failure
- **Fix**: Before creating a new notebook, list existing ones and delete duplicates:
  ```bash
  notebooklm list | grep "CourseName"
  # Delete all but the one with sources uploaded
  notebooklm delete -n <NOTEBOOK_ID> -y
  ```
- **Always** verify which notebook has the uploaded sources before deleting

### Pitfall 13e: Checkpoint File Notebook ID Mismatch
- If `note_pipeline.py` creates a new notebook but `.checkpoint.json` contains an old/different notebook ID, resume will fail with `No notebook found`
- **Fix**: After creating a notebook manually, update `.checkpoint.json` with the correct `notebook_id` before resuming
- **Pattern**: Create notebook → record ID → write checkpoint → resume pipeline

### Pitfall 13f: NotebookLM API Persistent Rate Limiting (Phase 3 MOC/Anki)

NotebookLM API can enter a degraded state where ALL `ask` calls return rate limit errors for 5-10+ minutes. This commonly happens during Phase 3 (MOC + Anki generation) after intensive Phase 2 chapter generation.

**Symptoms**:
```
Error: Chat request was rate limited or rejected by the API. Wait a few seconds and try again.
```

**Recovery — Escalating wait strategy**:
1. Wait 60s, retry → if still failing
2. Wait 180s, retry → if still failing
3. Wait 300s, retry → if still failing
4. **Proceed with manual content creation** — do not block indefinitely

**Manual MOC creation** (when API is down):
```markdown
# {CourseName} 知识地图 (MOC)

## 课程概览
[1-2 sentence summary based on syllabus]

## 章节导航
[For each chapter in syllabus:]
### [[Ch_XX_Chapter_Title]]
- **核心命题**: [Thesis from syllabus]
- **关键词**: [Key terms from syllabus]

## 跨章节关联
[Logical connections: data flow, theory evolution, decision hierarchy]

## 下一步学习建议
[3-4 actionable next steps]

---
*Generated by NotebookLM Pipeline*
*Signed: DALONG ZHANG*
```

**Manual Anki creation** (20 cards):
```markdown
# Anki - {CourseName} 真题卡 (20张)

## 卡片 1
**Q: [Core concept question]?**
A: [Detailed answer with derivation/formula]

[... repeat for 20 cards, 2 per chapter ...]

---
*Generated by NotebookLM Pipeline*
*Signed: DALONG ZHANG*
```

**Key insight**: Chapter notes (Phase 2) are the critical output. MOC and Anki can always be reconstructed from the syllabus and chapter titles. Do NOT let API degradation block course completion.

### Pitfall 13g: NotebookLM Source Upload via CLIAdapter Timeout

The `CLIAdapter.upload_sources_dir()` method in `lib/adapters/cli.py` uploads files one-by-one with `add_source()`. For 40+ files, this takes 5-10 minutes and may timeout the wrapping `note_pipeline.py` command.

**Symptoms**:
- `note_pipeline.py --phase 1` times out at 600s during upload
- Only partial files uploaded (e.g., 16/46)

**Fix — Direct Python upload with progress tracking**:
```python
from lib.adapters.cli import CLIAdapter
from pathlib import Path
import time

a = CLIAdapter()
a.use_notebook('<NOTEBOOK_ID>')
raw_dir = Path('flow/CourseName')
files = sorted(raw_dir.glob('*.md'))
existing = {s.get('name') or s.get('title', '') for s in a.list_sources()}

for f in files:
    if f.name in existing or f.name.startswith('_'):
        continue
    print(f'Uploading {f.name}...')
    a.add_source(str(f))
    time.sleep(1)

print(f'Total sources: {len(a.list_sources())}')
```

**Alternative — Shell loop with verification**:
```bash
# Upload all files
for f in flow/CourseName/*.md; do
  notebooklm source add "$f" 2>&1 | tail -1
  sleep 1
done

# Verify count
notebooklm source list | grep -c "ready"
```

**Note**: The loop may succeed even if the wrapping command times out. Always verify with `source list`.

### Pitfall 13h: NotebookLM Empty Chapter Notes (All Rounds Failed)

When NotebookLM API is degraded during Phase 2, chapter files are created but all 5 rounds contain `[生成失败]` markers with no actual content.

**Symptoms**:
- Chapter file size ~1.5KB (template only) vs ~15-25KB (successful)
- File contains: `[生成失败: notebooklm failed after 2 attempts: RPC GET_LAST_CONVERSATION_ID failed]`

**Diagnosis**:
```bash
# Check file size
ls -la 01_Permanent/CourseName/Ch_*.md
# Small files (< 5KB) = failed generation

# Check content
grep -l "生成失败" 01_Permanent/CourseName/Ch_*.md
```

**Recovery**:
1. Wait for API recovery (check with simple `notebooklm ask "hello"`)
2. Delete failed chapter files: `rm 01_Permanent/CourseName/Ch_*.md`
3. Reset checkpoint chapter statuses to `"pending"`
4. Re-run: `note_pipeline.py --course CourseName --resume --skip-upload`

**Prevention**: After Phase 2 completes, verify at least one chapter has substantial content (>10KB) before proceeding to Phase 3.

### Pitfall 13i: NotebookLM Notebook Recreation After Source Loss

If a notebook is deleted (accidentally or due to API issues), the sources must be re-uploaded. The checkpoint still references the old notebook ID.

**Recovery**:
1. Create new notebook: `notebooklm create "CourseName"`
2. Record new notebook ID
3. Update `.checkpoint.json` with new `notebook_id`
4. Set `phase1_done: false` to trigger re-upload
5. Re-run: `note_pipeline.py --course CourseName --resume`

**Alternative — Skip re-upload if sources exist locally**:
1. Create new notebook
2. Upload sources via Python script (see Pitfall 13g)
3. Update checkpoint: `phase1_done: true`, new `notebook_id`
4. Resume from Phase 2: `note_pipeline.py --course CourseName --resume --skip-upload`

### Pitfall 13j: YouTube Playlist URL Validation Before Transcription

Always validate the playlist title matches the expected course before starting a long transcription pipeline. A stale or incorrect URL may resolve to unrelated content.

**Validation command**:
```bash
.venv/bin/yt-dlp --cookies-from-browser chrome --flat-playlist --print "%(playlist_title)s" "<URL>"
```

**Abort condition**: If returned title does NOT match expected course name (e.g., "YouTube Tips & Advice" instead of "Principles of Management"), STOP and ask user to verify the URL.

**Do NOT** proceed with transcription of mismatched content — it wastes API quota and produces garbage output.

### Pitfall 13k: Git History Rewriting for Credential Removal

If a commit accidentally contains API keys or credentials, standard `git revert` does NOT remove them from history.

**Fix — Use `git filter-branch`**:
```bash
FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch --force \
  --index-filter 'git rm --cached --ignore-unmatch <filename>' \
  --prune-empty -- --all

# Force-push to remote
git push origin --force --all
git push origin --force --tags

# Purge local dangling objects
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

**Alternative**: `git rebase -i --root` to drop the offending commit entirely.

**Critical**: After rewriting history, ALL collaborators must re-clone the repository.

### Pitfall 13l: note_pipeline.py Foreground Timeout (600s Hard Limit)

`terminal()` foreground mode has a **hard maximum timeout of 600 seconds** (10 minutes), regardless of the value passed. For courses with 5+ chapters, Phase 2 WILL timeout.

**Fix**: ALWAYS use `terminal(background=True, notify_on_complete=True)` for note_pipeline.py. Background mode has no timeout limit.

**Pattern**:
```python
terminal(
    command="cd ~/Documents/all-in-one && uv run flow/script/note_pipeline.py --course CourseName --resume --skip-upload",
    background=True,
    notify_on_complete=True
)
```

**Check progress**:
```bash
ls -la 01_Permanent/CourseName/Ch_*.md | wc -l  # Count completed chapters
```

### Pitfall 13m: Syllabus Reformatting for Parser Compatibility

NotebookLM may output syllabus in English format (`Chapter N: Title`) but `syllabus_parser.py` only recognizes Chinese format (`第N章：标题`).

**Fix — Manual reformatting before saving**:
```markdown
# Course 课程大纲

## 第1章：English Chapter Title
- **核心命题**：...
- **视频范围**：01-05
- **前置知识**：无
- **本章概要**：...

## 第2章：Next Chapter Title
...
```

**Verification**:
```python
from lib.syllabus_parser import load_syllabus
chapters = load_syllabus(Path('01_Permanent/Course/Course_课程大纲.md'))
print(f'Loaded {len(chapters)} chapters')  # Should match expected count
```

### Pitfall 13n: Multiple Notebooks with Same Name

`note_pipeline.py` may create duplicate notebooks if retried after partial failure. `notebooklm list` shows multiple notebooks with identical names.

**Fix**:
```bash
# List all notebooks
notebooklm list

# Delete duplicates (keep the one with sources)
notebooklm delete -n <NOTEBOOK_ID> -y
```

**Prevention**: Before creating a new notebook, check if one already exists:
```bash
notebooklm list | grep "CourseName"
```

### Pitfall 13o: Checkpoint Phase Out of Sync with Filesystem

If `.checkpoint.json` says phase=1 but filesystem already has syllabus + chapters, `note_pipeline.py` will re-run Phase 1 instead of skipping to Phase 3.

**Fix — Delete stale checkpoint**:
```bash
rm 01_Permanent/CourseName/.checkpoint.json
# Re-run — auto-detects from filesystem
uv run flow/script/note_pipeline.py --course CourseName
```

**Auto-detection logic** (when no checkpoint):
- Syllabus exists + chapters exist + MOC exists → Phase 3
- Syllabus exists + chapters exist + no MOC → Phase 3
- Syllabus exists + no chapters → Phase 2
- No syllabus → Phase 1

### Pitfall 13p: NotebookLM `ask` with Long Conversation History

After many `ask` calls in the same conversation, NotebookLM may degrade (slower responses, rate limits). The CLI maintains conversation state across calls.

**Fix — Start fresh conversation for Phase 3**:
```bash
# After Phase 2 completes, create a new notebook for Phase 3
# OR delete and recreate the notebook to clear conversation history
```

**Alternative**: The `notebooklm ask` command supports `--new-conversation` flag (if available in CLI version) to start a fresh context.

### Pitfall 13q: Operations Management Chapter Count Mismatch

When NotebookLM generates a syllabus, the chapter count may not match the user's expectation. For Operations Management, NotebookLM produced 9 chapters while the user expected 10.

**Resolution**: Trust NotebookLM's content-based chapter boundaries. The 9 chapters accurately reflected the course's natural module structure. Do NOT force an arbitrary chapter count.

**Verification**: Review the syllabus video ranges to confirm logical grouping:
```markdown
## 第1章：Introduction to Operations Management and Strategy (01-03)
## 第2章：Process Analysis and Capacity Planning (04-08)
...
```

### Pitfall 13r: Principles of Management Syllabus Expansion

Initial manual syllabus had 5 chapters based on video title grouping. NotebookLM's content analysis revealed 10 natural chapters. The expanded syllabus better reflected the course structure.

**Lesson**: When manually creating a syllabus (due to API failure), use video title patterns to estimate chapter count, but be prepared to expand if content analysis reveals more natural boundaries.

**Pattern for manual syllabus creation**:
1. Group videos by topic/theme (3-5 videos per chapter)
2. Identify natural transition points (theory → application, concept → case study)
3. Leave room for expansion (don't lock in chapter count)
4. Use descriptive titles that reflect content, not just video titles

### Pitfall 13s: Batch Course Processing Order

When processing multiple courses in sequence, maintain a strict order and update a progress tracker:

```markdown
# 课程学习进度清单

| 序号 | 课程名称 | 链接 | 状态 |
|------|---------|------|------|
| 1 | Course A | URL | 已完成 |
| 2 | Course B | URL | 进行中 |
| 3 | Course C | URL | 未开始 |
```

**Rules**:
- Process ONE course at a time (Pipeline 1 → Pipeline 2 → next course)
- Git commit after each course completion
- Update progress tracker after each course
- Validate URLs before starting (see Pitfall 13j)

### Pitfall 13t: Background Process Log Inspection

When a background process completes, inspect its log to verify success:

```bash
tail -n 50 /tmp/<course>_pipeline.log
```

**Success indicators**:
- `Summary: N/N videos processed`
- `Refined: N/N`
- `PIPELINE COMPLETE`

**Failure indicators**:
- `RuntimeError` in log
- Fewer output files than videos
- Empty or near-empty refined files

### Pitfall 15: `run_pipeline.py` Parameter Format

`run_pipeline.py` takes **positional arguments** `(url, course, [max])`, NOT `--output-dir` or other flag-style arguments.

**Correct usage:**
```bash
uv run youtube2note/input/script/run_pipeline.py "https://www.youtube.com/playlist?list=..." "Course_Name" 5
```

**Incorrect usage (will fail):**
```bash
uv run youtube2note/input/script/run_pipeline.py "URL" --output-dir /path/to/output
# Error: unrecognized arguments: --output-dir
```

**Parameter order:**
1. `url` (required) — YouTube playlist or video URL
2. `course` (required) — Course name, becomes directory name under `youtube2note/input/`
3. `max` (optional) — Max videos to process, omit for all

**Output directory is determined automatically**: `youtube2note/input/{course}/` — do NOT try to override it.

### Pitfall 16: `execute_code` Sandbox Isolation — No Project Venv Access

The `execute_code` tool runs Python scripts in an isolated sandbox environment that does NOT have access to the project's `.venv` packages. This causes `ModuleNotFoundError` for packages installed in the project environment (e.g., `google.genai`, `httpx`, `pydantic`).

**Symptoms:**
```python
from google.genai import Client
# ModuleNotFoundError: No module named 'google.genai'
```

**Root cause**: `execute_code` uses a fresh Python interpreter without the project's virtual environment activated. Even though `uv pip list` shows the package installed in `.venv`, the sandbox cannot see it.

**Fix — Use `terminal()` with `uv run` instead:**
```python
# ❌ execute_code — fails with ModuleNotFoundError
execute_code(code="from google.genai import Client; ...")

# ✅ terminal with uv run — works correctly
terminal(command="cd ~/Documents/all-in-one && uv run python /tmp/script.py")
```

**For scripts that need to call Gemini API or use project packages:**
1. Write the script to a temporary file (e.g., `/tmp/generate_ch1.py`)
2. Run it via `uv run python /tmp/script.py` in the project directory
3. The script will have full access to `.venv` packages

**Example workflow for batch chapter generation:**
```python
# Step 1: Write script to temp file
write_file(path='/tmp/generate_all_chapters.py', content='''
from google.genai import Client
from google.genai.types import HttpOptions
import os, time

client = Client(
    vertexai=True,
    api_key=os.environ.get("GOOGLE_API_KEY", ""),
    http_options=HttpOptions(api_version="v1")
)

# Generate all chapters with sleep between calls
for chapter in chapters:
    response = client.models.generate_content(model='gemini-2.5-pro', contents=prompt)
    # ... save output ...
    time.sleep(2)  # Prevent rapid-fire requests causing RemoteProtocolError
''')

# Step 2: Run via terminal with uv
terminal(command="cd ~/Documents/all-in-one && uv run python /tmp/generate_all_chapters.py", timeout=600)
```

**Batch generation pattern (validated across 6 courses):**
Write a single script that generates syllabus + all chapters + MOC + Anki in one execution:
```python
write_file(path='/tmp/generate_course_all.py', content='''
import os, glob, time
from pathlib import Path
from google.genai import Client
from google.genai.types import HttpOptions

client = Client(vertexai=True, api_key=os.environ.get('GOOGLE_API_KEY',''),
                http_options=HttpOptions(api_version='v1'))

# 1. Syllabus
# 2. Chapters (with time.sleep(2) between each)
# 3. MOC
# 4. Anki
''')
terminal(command="cd ~/Documents/all-in-one && uv run python /tmp/generate_course_all.py")
```

See `knowledge-base-youtube-download` skill Pitfall 23b for the full batch generation template.

**Prevention**: Always use `terminal()` + `uv run python` for any script that imports project-specific packages. Reserve `execute_code` for pure stdlib operations only.

Automated PDF export from Markdown with MathJax formulas consistently fails. Tools tested and their results:

| Tool | Math Rendering | Status |
|------|---------------|--------|
| pandoc + weasyprint | ❌ Raw LaTeX text | Fails — no MathJax support |
| pandoc + Chrome Headless | ❌ Async timing race | Fails — prints before MathJax renders |
| pandoc + Playwright | ⚠️ Fragile | Works with explicit wait but platform-dependent |
| **Obsidian Export** | ✅ Perfect | **Recommended** |

**Best Practice**: Use `merge_course_md.py` to merge chapters into a single `.md` file, then let the user manually export PDF via Obsidian's built-in export. Obsidian's MathJax engine renders formulas correctly.

See `references/obsidian-pdf-export-workflow.md` for complete workflow.

### Pitfall 14a: Sorting Merged Chapters by Filename

When merging chapter files with `merge_course_md.py`, sorting by filename (`sorted(glob('Ch_*.md'))`) produces incorrect order when:
- Duplicate chapter numbers exist (e.g., two Ch.03 files with different video ranges)
- Filenames use different punctuation characters

**Fix**: Extract `视频范围` metadata from each file and sort by video start number:
```python
def get_video_start(content: str) -> int:
    m = re.search(r'视频范围\s*[:：]\s*(\d+)', content)
    return int(m.group(1)) if m else 99999

chapters.sort(key=lambda c: c.video_start)
```

### Pitfall 14b: Metadata Block Cleanup in Merged Output

Chapter files contain metadata blocks like:
```markdown
> **Metadata**
> - 课程：CourseName
> - 视频范围：01-05
---
```

If not cleaned, these appear in the merged output and clutter the PDF.

**Fix**: Use regex that matches the full metadata block including trailing `---`:
```python
content = re.sub(
    r'^\s*>\s*\*\*Metadata\*\*.*?\n(?:^\s*>\s*.*?\n)*^\s*---\s*\n+',
    '',
    content,
    flags=re.MULTILINE | re.DOTALL
)
```

Also handle Chinese colons `：` in addition to English `:`.

### Pitfall 14c: Heading Level Conflicts in Merged Document

The merged document has an H1 title (`# Course Name`). If chapter files also have H1 titles, the PDF outline shows multiple top-level headings.

**Fix**: Remove the original H1 from each chapter and shift all headings down one level:
```python
# Remove original H1
content = re.sub(r'^#\s+.+?\n+', '', content, count=1, flags=re.MULTILINE)

# Shift H1→H2, H2→H3, etc.
content = re.sub(r'^(#{1,5})\s+(.+)$', shift_heading, content, flags=re.MULTILINE)
```

### Pitfall 13u: NotebookLM Source List Empty After Upload

`notebooklm source list` may return empty even after successful uploads. This is a display/API lag issue, not an actual failure.

**Verification**:
```bash
# Check count via JSON
notebooklm source list --json | python -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('sources',[])))"

# Or use CLIAdapter in Python
from lib.adapters.cli import CLIAdapter
a = CLIAdapter()
a.use_notebook('<ID>')
print(len(a.list_sources()))
```

**Note**: The `--json` flag may return a different format than the table view. Handle both dict-wrapped and raw-list formats.

## Support Files

- `references/session-log-batch-processing-may-2026.md` — Batch processing 10 courses: URL validation, API recovery, git credential removal (validated May 2026)
- `references/notebooklm-api-recovery-patterns.md` — Recovery patterns for rate limiting and RPC failures (validated May 2026)
- `references/notebooklm-upload-script.md` — NotebookLM 批量上传脚本（带去重、间隔、验证）
- `references/notebooklm-batch-creation-pattern.md` — Batch notebook creation for large course libraries (validated Jun 2026)
- `references/notebooklm-100-source-limit.md` — NotebookLM 100-source hard limit behavior and mitigation (validated Jun 2026)
- `references/notebooklm-batch-upload-script.md` — Batch upload script with resume, deduplication, rate-limit handling, and progress logging for large course libraries (validated Jun 2026)
- `references/manual-pipeline2-workflow.md` — Manual fallback workflow when note_pipeline.py fails (validated May 2026)
- `references/manual-pipeline2-workflow.md` — Manual fallback workflow when note_pipeline.py fails (validated May 2026)
- `references/obsidian-pdf-export-workflow.md` — Markdown merge + Obsidian manual PDF export for perfect MathJax rendering (validated May 2026)
- `references/gemini-api-direct-fallback.md` — Bypass NotebookLM entirely when upload is broken; use Gemini API directly for syllabus, chapters, MOC, Anki (validated May 2026)
- `references/gemini-api-direct-fallback-at-scale.md` — Full batch generation script template validated across 6 courses (May 2026)
- `templates/chapter-note-template.md` — 统一章节笔记 Markdown 模板

## Verification Checklist

### Transcription Phase
- [ ] yt-dlp version >= 2026.03.17: `.venv/bin/yt-dlp --version`
- [ ] Git status clean before starting: `git status`
- [ ] Background process started with `notify_on_complete=True`
- [ ] Each video committed after processing
- [ ] Final output in `flow/{course}/` with `.md` files

### NotebookLM Study Phase
- [ ] NotebookLM auth verified: `uv run notebooklm doctor`
- [ ] Notebook project created and notebook-id recorded
- [ ] All transcripts uploaded: `uv run notebooklm source list`
- [ ] Background study script started with `notify_on_complete=True`
- [ ] Syllabus generated and saved to `01_Permanent/{course}/`
- [ ] Each chapter note committed after generation
- [ ] MOC and Anki cards generated and committed

### Completion Check
- [ ] `youtube2note/input/{course}/` contains all video transcripts
- [ ] `youtube2note/output/{course}/` contains:
  - `{course}_课程大纲.md`
  - `Ch_XX_*.md` for each chapter
  - `{course}_知识地图_MOC.md`
  - `Anki_{course}_N张真题卡.md`
- [ ] All changes committed to git
- [ ] Background processes completed (check `process(action="list")`)
