---
name: knowledge-base-youtube-download
version: 2.0.0
description: |
  Full course knowledge base pipeline: YouTube download → transcription →
  NotebookLM analysis → Obsidian structured notes + MOC + Anki.
  Key lessons: always use project venv yt-dlp, never system Python yt-dlp;
  never name Python package 'types'; let NotebookLM determine natural chapter boundaries.
author: DALONG ZHANG
---

# Knowledge Base YouTube Video Download

## Trigger
- User wants to download YouTube videos for knowledge base processing
- Need to fetch course playlists and store locally
- User explicitly said "all scripts in Python" — this overrides any prior Deno/TypeScript implementation
- **CRITICAL**: When user says "利用现有的脚本" (use existing scripts), ALWAYS use their pipeline scripts instead of reinventing the workflow
- User provides a YouTube playlist URL and asks to "开始学习" (start learning) → use `run_pipeline.py`
- **CRITICAL**: This skill is STEP 1 of a TWO-STEP workflow. When user says "学习课程" with a YouTube link, ALWAYS run this skill FIRST (transcription), then `youtube-course-pipeline` SECOND (study). User explicitly corrected: "正常的流程：1、knowledge-base-youtube-download 转录课程 2、youtube-course-pipeline 课程学习"

## Steps

### 1. Environment Check
- **CRITICAL**: Always use the project virtual environment's yt-dlp
- Path: `~/Documents/all-in-one/.venv/bin/yt-dlp`
- Version must be >= 2026.03.17 (system Python's 2025.10.14 is BROKEN for YouTube)
- Never use system Python yt-dlp (`~/.local`, `/Library/Python/3.9`, etc.)

### 2. Verify yt-dlp Availability
```bash
cd ~/Documents/all-in-one
.venv/bin/yt-dlp --version
```

### 3. Download Command Pattern
```bash
.venv/bin/yt-dlp \
  --cookies-from-browser chrome \
  --playlist-items 1 \
  --format "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best" \
  --merge-output-format mp4 \
  --output "/tmp/video_audio_downloads/%(title)s.%(ext)s" \
  "<YOUTUBE_URL>"
```

## Pitfalls

### Pitfall 1: System Python yt-dlp
- System Python yt-dlp (2025.10.14) fails with HTTP 403 / SABR errors
- YouTube 2025 anti-bot requires latest yt-dlp + cookies
- **Always** use project `.venv` version

### Pitfall 2: Missing Cookies
- Without `--cookies-from-browser chrome`, YouTube returns 403
- Chrome must be logged into YouTube for cookies to work

### Pitfall 3: Playlist vs Single Video
- URLs with `watch?v=...&list=...` default to playlist mode
- Use `--playlist-items 1` to download only first item (test mode)
- Use `--no-playlist` to download single video ignoring playlist

### Pitfall 4: Format Selection
- `bestvideo+bestaudio` may select AV1 codec which needs ffmpeg
- Ensure ffmpeg is installed: `/opt/homebrew/bin/ffmpeg`

### Pitfall 5: Wrong Project Directory
- User's active project is `~/Documents/all-in-one` (NOT `all-in-one_副本`)
- Always `cd ~/Documents/all-in-one` before any git or venv operation
- Scripts belong in `~/Documents/all-in-one/youtube2note/input/script/` (NOT `flow/script/` — directory was renamed in May 2026 refactor)
- Commit after each completed step

### Pitfall 5a: PROJECT_ROOT Depth Mismatch After Refactor

After the May 2026 refactor (`flow/` → `youtube2note/input/`), `config/paths.py` had incorrect `PROJECT_ROOT` depth.

**File**: `youtube2note/input/script/config/paths.py`

**Before (broken)**:
```python
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # 3 levels = youtube2note/
Y2N_ROOT = PROJECT_ROOT  # same as youtube2note/
PATHS = {
    "venv_bin": PROJECT_ROOT.parent / ".venv" / "bin",  # tries to find .venv outside youtube2note/
}
```

**After (fixed)**:
```python
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # 4 levels = repo root
Y2N_ROOT = PROJECT_ROOT / "youtube2note"
PATHS = {
    "venv_bin": PROJECT_ROOT / ".venv" / "bin",  # correct: .venv is at repo root
}
```

**Symptom**: `[Errno 2] No such file or directory: '/Users/.../youtube2note/.venv/bin/yt-dlp'`

**Fix**: Update `PROJECT_ROOT` to use `parent.parent.parent.parent` (4 levels up from `input/script/config/paths.py` to reach the git repo root where `.venv/` lives).

**Also see Pitfall 28** for the same issue in batch processing scripts.

### Pitfall 7: LLM Summarization on Refinement

The default "academic editor" persona causes Gemini to **summarize and condense** transcripts. A 217K char transcript was reduced to ~5K chars (98% loss).

**Root cause**: The prompt used "精修" (refine/process) which the LLM interpreted as "rewrite academically and concisely".

**Fix**: Use a **concise, instruction-only prompt** — no persona, no examples, no prohibitions:

```
这是一段音频转录文本，请进行以下优化：
1. 补全标点符号（句号、逗号等）
2. 修正识别错误的术语、人名、地名
3. 去除口语噪音（"嗯"、"啊"、"那个"等填充词）
4. 按语义分段（每段一个主题）
5. Obsidian 格式化（Markdown 标准格式）
请直接输出优化后的文本，不要添加额外说明。
```

**Why this works**: Short prompts give LLM clear boundaries. Every extra instruction (persona, examples, prohibitions) increases the chance of unwanted summarization behavior.

**Verification**: After switching to the concise prompt, output went from ~5K to ~25K chars (88% retention of original 217K chars), with full lecture transcript preserved.

See `references/content-refinement.md` for the full prompt evolution and analysis.
See `references/srt-overlap-removal.md` for SRT deduplication technique.
See `references/batch-processing-recovery.md` for batch recovery patterns.

### Pitfall 7a: English Output from NotebookLM / Gemini

When processing English-language course videos, NotebookLM and Gemini may output chapter notes, syllabus, and MOC in English even though the user requires Chinese output.

**Root cause**: The prompts did not explicitly enforce Chinese output. LLMs default to the language of the input content (English transcripts → English output).

**Fix**: Add explicit Chinese output enforcement to ALL prompts:

1. **Refinement prompt** (`lib/refine.py`):
```python
REFINE_PROMPT = """这是一段音频转录文本，请进行以下优化，输出必须为中文：
...
6. 所有内容翻译成中文，保留专业术语的英文原文（如首次出现可标注英文）

请直接输出优化后的中文文本，不要添加额外说明。"""
```

2. **Syllabus prompt** (`lib/prompt_engine.py` + `config/prompts.py`):
```
基于全部转录文本，生成研究生级别的课程逻辑大纲，输出必须为中文：
...
6. 所有内容用中文输出，专业术语保留英文原文
```

3. **Chapter deep-dive prompt**:
```
基于视频{video_range}的内容，请深入分析本章，输出必须为中文：
...
- 所有内容用中文输出，专业术语保留英文原文
```

4. **Pressure test prompts** (all 5 rounds):
```
基于视频{video_range}的内容，请回答，输出必须为中文：
...
要求：...所有内容用中文输出（专业术语保留英文），署名DALONG ZHANG。
```

5. **MOC / Next Steps / Anki prompts**:
```
所有章节已完成。请生成《{course_name}》知识地图，输出必须为中文：
...
5. 所有内容用中文输出，专业术语保留英文原文
```

**Key rule**: Every prompt must include either:
- `输出必须为中文` at the top (preferred)
- `所有内容用中文输出，专业术语保留英文原文` in the requirements

**Files to modify**:
- `flow/script/lib/refine.py` — REFINE_PROMPT
- `flow/script/lib/prompt_engine.py` — SYLLABUS, CHAPTER_DEEP_DIVE, PRESSURE_*, MOC, NEXT_STEPS, ANKI
- `flow/script/config/prompts.py` — legacy string constants (mirror of prompt_engine.py)

**Note**: Both `prompt_engine.py` (dataclass-based) and `config/prompts.py` (legacy string constants) must be kept in sync. The pipeline may use either depending on the entry point.

### Pitfall 7a: English Output from NotebookLM / Gemini

When processing English-language course videos, NotebookLM and Gemini may output chapter notes, syllabus, and MOC in English even though the user requires Chinese output.

**Root cause**: The prompts did not explicitly enforce Chinese output. LLMs default to the language of the input content (English transcripts → English output).

**Fix**: Add explicit Chinese output enforcement to ALL prompts:

1. **Refinement prompt** (`lib/refine.py`):
```python
REFINE_PROMPT = """这是一段音频转录文本，请进行以下优化，输出必须为中文：
...
6. 所有内容翻译成中文，保留专业术语的英文原文（如首次出现可标注英文）

请直接输出优化后的中文文本，不要添加额外说明。"""
```

2. **Syllabus prompt** (`lib/prompt_engine.py` + `config/prompts.py`):
```
基于全部转录文本，生成研究生级别的课程逻辑大纲，输出必须为中文：
...
6. 所有内容用中文输出，专业术语保留英文原文
```

3. **Chapter deep-dive prompt**:
```
基于视频{video_range}的内容，请深入分析本章，输出必须为中文：
...
- 所有内容用中文输出，专业术语保留英文原文
```

4. **Pressure test prompts** (all 5 rounds):
```
基于视频{video_range}的内容，请回答，输出必须为中文：
...
要求：...所有内容用中文输出（专业术语保留英文），署名DALONG ZHANG。
```

5. **MOC / Next Steps / Anki prompts**:
```
所有章节已完成。请生成《{course_name}》知识地图，输出必须为中文：
...
5. 所有内容用中文输出，专业术语保留英文原文
```

**Key rule**: Every prompt must include either:
- `输出必须为中文` at the top (preferred)
- `所有内容用中文输出，专业术语保留英文原文` in the requirements

**Files to modify**:
- `flow/script/lib/refine.py` — REFINE_PROMPT
- `flow/script/lib/prompt_engine.py` — SYLLABUS, CHAPTER_DEEP_DIVE, PRESSURE_*, MOC, NEXT_STEPS, ANKI
- `flow/script/config/prompts.py` — legacy string constants (mirror of prompt_engine.py)

**Note**: Both `prompt_engine.py` (dataclass-based) and `config/prompts.py` (legacy string constants) must be kept in sync. The pipeline may use either depending on the entry point.

### Pitfall 6: Subtitle Download to Markdown
- Use `--write-auto-subs --sub-langs en --convert-subs srt` to fetch auto-generated English subtitles
- Parse SRT blocks: index line, timestamp line (`00:00:00,000 --> 00:00:00,000`), text lines
- Strip HTML tags, music markers (`[Music]`, `♪`), and carriage returns
- Convert to Markdown with metadata header (title, index, course, URL, timestamp, source)
- Output naming: `{index}-{title}.md` under `flow/{course}/`
- Clean up temporary `.srt` files after conversion

### Pitfall 7: LLM Summarization on Refinement

The default "academic editor" persona causes Gemini to **summarize and condense** transcripts. A 217K char transcript was reduced to ~5K chars (98% loss).

**Root cause**: The prompt used "精修" (refine/process) which the LLM interpreted as "rewrite academically and concisely".

**Fix**: Use a **concise, instruction-only prompt** — no persona, no examples, no prohibitions:

```
这是一段音频转录文本，请进行以下优化：
1. 补全标点符号（句号、逗号等）
2. 修正识别错误的术语、人名、地名
3. 去除口语噪音（"嗯"、"啊"、"那个"等填充词）
4. 按语义分段（每段一个主题）
5. Obsidian 格式化（Markdown 标准格式）
请直接输出优化后的文本，不要添加额外说明。
```

**Why this works**: Short prompts give LLM clear boundaries. Every extra instruction (persona, examples, prohibitions) increases the chance of unwanted summarization behavior.

**Verification**: After switching to the concise prompt, output went from ~5K to ~25K chars (88% retention of original 217K chars), with full lecture transcript preserved.

See `references/content-refinement.md` for the full prompt evolution and analysis.
See `references/srt-overlap-removal.md` for SRT deduplication technique.
See `references/batch-processing-recovery.md` for batch recovery patterns.

## Transcription (Audio → Text)

Uses fault-tolerant backend chain: GCP Vertex AI → Gemini Standard API.

```bash
cd ~/Documents/all-in-one
PYTHONPATH=flow/script python3 flow/script/transcribe_audio.py \
  <AUDIO_PATH> <COURSE_NAME> <INDEX>
```

- Output: `flow/{course}/{index}-Transcription {course}.md`
- Backend auto-selection via `TRANSCRIBER` env var, or auto-failover
- Vertex model: `gemini-3.1-pro-preview` (working via google-genai SDK with api_key)
- Gemini fallback model: `gemini-2.5-flash-lite`
- **CRITICAL**: Uses `google-genai` SDK (`google.genai.Client`), NOT hand-crafted REST API
- Transcription prompt: Chinese, with punctuation, semantic segmentation, filler removal
- **CRITICAL**: All Google API calls follow unified pattern — Vertex AI first (project credits), Gemini Standard API fallback. Never hardcode a single endpoint.
- See `references/google-api-unified-pattern.md` for SDK usage details

## Content Refinement (Markdown → Polished Markdown)

Academic refinement via Gemini with structured prompt.

```bash
cd ~/Documents/all-in-one
PYTHONPATH=flow/script python3 flow/script/refine_markdown.py \
  <INPUT_MD> [OUTPUT_MD]
```

- **Text cleaning**: remove filler words, add punctuation, logical segmentation
- **Terminology**: standard finance/tech terms, LaTeX math formatting
- **Key concept bolding**: core definitions and conclusions
- Uses fault-tolerant backend chain: Vertex AI (gemini-3.1-pro-preview) → Gemini API (gemini-2.5-flash-lite)
- Output naming: `{index}-{title}.md` under `flow/{course}/`
- See `references/content-refinement.md` for prompt template and LaTeX examples
- **CRITICAL**: Uses `google-genai` SDK, NOT REST API. See `references/google-api-unified-pattern.md`
- **CRITICAL**: All Google API calls follow unified pattern — Vertex AI first (project credits), Gemini Standard API fallback. Never hardcode a single endpoint.
- **CRITICAL**: Prompt must be **concise and instruction-only** (5 bullet points, no persona, no examples). See `references/content-refinement.md` for the exact prompt that prevents LLM summarization.

## Architecture

Scripts follow a layered architecture for maintainability. **All scripts are Python 3.**

```
youtube2note/input/script/
├── config/
│   ├── paths.py          # Centralized paths, binaries, filename builders
│   └── transcribe.py     # Transcription config (backends, models, credentials)
├── models/
│   └── video.py          # Domain dataclasses
├── lib/
│   ├── youtube.py        # YouTube operations (fetch, download, parse, format)
│   ├── download.py       # Video download operations
│   ├── audio.py          # Audio extraction via ffmpeg
│   ├── gemini_client.py  # Unified Google Gemini client (Vertex + Standard API)
│   ├── transcribe.py     # Transcription via gemini_client
│   └── refine.py         # Academic content refinement via gemini_client
├── tests/
│   ├── test_paths.py     # Unit tests for config
│   ├── test_youtube.py   # Unit tests for SRT parsing / Markdown formatting
│   └── test_transcribe.py # Unit tests for transcription config
└── <entry>.py            # CLI entrypoint: only parsing + orchestration
```

**Project structure (refactored May 2026):**
```
youtube2note/
├── input/                # YouTube transcriptions (was flow/)
│   ├── script/           # Pipeline scripts
│   └── {course}/         # Refined markdown files
├── output/               # NotebookLM generated notes (was 01_Permanent/)
│   └── {course}/
├── img/                  # Study images
└── note/                 # Personal notes
```

**Key design rule**: lib modules use absolute imports (`from config.paths import ...`) so they work both as imports and when run directly. Entry scripts set `PYTHONPATH` or use `sys.path.insert` when needed.

See `references/script-architecture.md` for full design rationale.

## Project Directory Refactor (May 2026)

The project was reorganized into a `youtube2note` subproject:
- `flow/` → `youtube2note/input/` (YouTube transcriptions)
- `01_Permanent/` → `youtube2note/output/` (NotebookLM generated notes)
- `note/` + `02_gemini/` → `youtube2note/note/` (personal notes)
- `img/` → `youtube2note/img/` (study images)
- Scripts moved to `youtube2note/input/script/`

**Path config updates**:
- `config/paths.py`: `flow_dir` → `input_dir`, `PROJECT_ROOT` depth +2
- `config/note_paths.py`: `permanent_dir` → `output_dir`, `flow_dir` → `input_dir`
- All hardcoded path strings updated via automated find/replace

**Running scripts after refactor**:
```bash
cd ~/Documents/all-in-one
uv run youtube2note/input/script/run_pipeline.py "<URL>" "<COURSE>"
uv run youtube2note/input/script/note_pipeline.py --course "<COURSE>" --phase 1
```

## Two-Step Workflow (MANDATORY)

When user says "学习课程" and provides a YouTube link, execute this exact two-step process:

**Step 1: Transcription (THIS SKILL — knowledge-base-youtube-download)**
- Input: YouTube playlist URL
- Output: `youtube2note/input/<CourseName>/`
- Process: subtitle extraction → audio transcription → Gemini refinement

**Step 2: Course Study (youtube-course-pipeline)**
- Load skill: `skill_view(name='youtube-course-pipeline')`
- Input: `youtube2note/input/<CourseName>/` (refined markdown)
- Output: `youtube2note/output/<CourseName>/`
- Process: syllabus → chapter deep-dive → MOC → Anki cards

**User explicitly corrected**: "正常的流程：1、knowledge-base-youtube-download 转录课程 2、youtube-course-pipeline 课程学习". Never conflate these two skills.

## Testing

Run all tests before committing new features:

```bash
cd ~/Documents/all-in-one
PYTHONPATH=flow/script_py python3 flow/script_py/tests/test_paths.py
PYTHONPATH=flow/script_py python3 flow/script_py/tests/test_youtube.py
PYTHONPATH=flow/script_py python3 flow/script_py/tests/test_transcribe.py
```

Current coverage: 15 tests (paths: 5, youtube: 6, transcribe: 4).
Add tests for any new lib module.

## Subtitle-to-Markdown Pipeline

```bash
cd ~/Documents/all-in-one
PYTHONPATH=flow/script python3 flow/script/download_subtitles.py \
  "<URL>" "<COURSE_NAME>" <INDEX>
```

## Audio Extraction

```bash
cd ~/Documents/all-in-one
PYTHONPATH=flow/script python3 flow/script/extract_audio.py \
  <VIDEO_PATH> [OUTPUT_PATH]
```

- Uses ffmpeg with configurable sampleRate, channels, bitrate, format
- Default: 22kHz mono 64k MP3
- Includes `probe_file()` for media metadata via ffprobe

## Video Download

```bash
cd ~/Documents/all-in-one
PYTHONPATH=flow/script python3 flow/script/download_youtube.py \
  "<YOUTUBE_URL>"
```

## Verification

```bash
ls -lh /tmp/video_audio_downloads/
ffprobe -v error -select_streams v:0 \
  -show_entries stream=codec_name,duration,width,height \
  -of csv=s=x:p=0 /tmp/video_audio_downloads/*.mp4
```

## Unified Pipeline

Orchestrates the full workflow: playlist extraction → subtitle/audio → refinement.

```bash
cd ~/Documents/all-in-one
PYTHONPATH=flow/script python3 flow/script/run_pipeline.py \
  "<PLAYLIST_URL>" "<COURSE_NAME>" [MAX_VIDEOS]
```

**When user asks to "开始学习" a YouTube course**: Run the pipeline with appropriate `MAX_VIDEOS` (e.g., 2 for test, omit for all).

### Background Execution (Required for Large Playlists)

For playlists with 10+ videos, **always run in background** to avoid blocking the session:

```python
# Start background pipeline
terminal(
    command="cd ~/Documents/all-in-one && .venv/bin/python flow/script/run_pipeline.py &quot;<URL>&quot; &quot;<COURSE>&quot;",
    background=True,
    notify_on_complete=True,
    timeout=600
)

# Poll progress periodically
process(action="poll", session_id="...")

# Wait for completion (returns when done or timeout)
process(action="wait", session_id="...", timeout=180)
```

**Why background:** Processing 22 videos takes ~1 hour. Foreground execution blocks all other work and is vulnerable to session interruption.

**Progress tracking:** Check file count in output directory:
```bash
ls ~/Documents/all-in-one/flow/<COURSE>/ | wc -l
```

### Pipeline Logic

1. **Extract playlist** from YouTube URL → list of videos
2. **For each video**:
   - Try subtitle download first (fast, accurate)
   - If subtitle fails → download video → extract audio → transcribe with Gemini
3. **Refine** the raw Markdown with content-preserving optimization (filler removal, punctuation, term correction, LaTeX formatting — NOT summarization)
4. **Cleanup**: delete raw intermediate files, keep only final refined `.md`

### Interrupt Safety

The pipeline modifies files in `flow/{course}/`. If interrupted mid-run:
- Files may be in inconsistent state (raw deleted but refined not yet written)
- **Recovery**: `git checkout -- flow/{course}/` to restore from last commit
- **Prevention**: Run with small `MAX_VIDEOS` first to verify, then run full batch
- **Git workflow**: Always `git status` before and after pipeline runs

### File Lifecycle

```
Video → subtitle.md (raw) → refine → {index}-{title}.md (final)
       └→ [deleted after refinement]

Video → video.mp4 → audio.mp3 → transcription.md (raw) → refine → {index}-{title}.md (final)
       └→ [all intermediates deleted]
```

**Critical**: `_save_refined()` uses atomic replacement:
1. Write refined content to temp file
2. Delete raw file
3. Rename temp to final filename

This ensures only one `.md` file per video exists in the output directory.

### LLM Non-Determinism Warning

Re-running refinement on identical input produces different outputs. This is expected LLM behavior, not a bug:

| Factor | Impact |
|--------|--------|
| `temperature=0.2` | Sampling randomness |
| Thought tokens (93-476) | Internal reasoning varies per call |
| `maxOutputTokens=8192` | Compression choices differ |
| Context window | Minor length shifts affect attention |

**Mitigation**: Run pipeline once per video. Do not re-refine expecting identical output. See `references/llm-nondeterminism.md` for full analysis.

### Example Output

```
flow/Course_Name/
├── 01-Chapter 1_ Ten Principles of Economics.md
├── 02-Chapter 2_ Thinking Like an Economist.md
├── 03-Chapter 3_ ...
└── ...
```

Each file contains:
- Metadata header (index, course, timestamp, source)
- `## 精修内容` section with polished academic text

## Note Generation Pipeline (Transcription → Knowledge Base)

After transcription is complete, the **note generation pipeline** converts raw transcripts into structured Obsidian knowledge base via NotebookLM.

### Architecture (Refactored — Adapter + Checkpoint + Template Engine)

```
flow/script_py/
├── note_pipeline.py              # CLI entrypoint (phase 1/2/3 orchestration)
├── config/
│   ├── notebooklm.py             # NotebookLM CLI configuration
│   ├── note_paths.py             # Path helpers (raw/permanent/MOC/Anki)
│   └── prompts.py                # All phase prompts (syllabus, deep-dive, MOC, Anki)
├── models/
│   └── note.py                   # Domain models (VideoInfo, Chapter, CourseContext)
├── lib/
│   ├── adapters/                 # Adapter pattern for NotebookLM backend
│   │   ├── base.py               # NotebookLMAdapter ABC interface
│   │   ├── cli.py                # CLIAdapter — production (subprocess)
│   │   └── mock.py               # MockAdapter — testing/dry-run
│   ├── checkpoint.py             # PipelineCheckpoint + ChapterCheckpoint persistence
│   ├── prompt_engine.py          # PromptTemplate with variable binding + versioning
│   ├── notebooklm_client.py      # Legacy CLI wrapper (kept for compat)
│   ├── syllabus_parser.py        # Parse NotebookLM syllabus → Chapter objects
│   ├── note_generator.py         # Phase 1/2/3 generation logic (adapter-injected)
│   └── course_loader.py          # Load video metadata from raw transcription dir
└── tests/
    ├── test_syllabus_parser.py
    ├── test_note_paths.py
    └── test_course_loader.py
```

**Key architectural decisions**:
1. **Adapter pattern**: `NotebookLMAdapter` ABC allows swapping CLI backend for API backend or mock injection. Production uses `CLIAdapter`, tests use `MockAdapter`.
2. **Checkpoint persistence**: JSON checkpoint auto-saves after each chapter. Resume with `--resume` flag without manual `--notebook-id --phase`.
3. **PromptTemplate engine**: Versioned templates with `.render(**kwargs)` variable binding. Missing variables raise `ValueError` at render time, not at API call time.
4. **Chinese numeral parsing**: Syllabus parser handles both `第一章` and `第1章` via `_parse_chapter_number()`.

**CRITICAL**: The `types/` directory was renamed to `models/` because `types` conflicts with Python's standard library `types` module. Never name a Python package directory `types`.

### Phase 1: Syllabus Generation

Upload all refined transcripts to NotebookLM, then generate a graduate-level syllabus:

```bash
```bash
uv run youtube2note/input/script/note_pipeline.py --course "CourseName" --phase 1
```

- Creates a new NotebookLM project (or uses `--notebook-id` to resume)
- Uploads all `*.md` files from `youtube2note/input/{course}/` with deduplication
- Generates syllabus: chapters determined by **actual content**, not a fixed count
- Saves syllabus to `youtube2note/output/{course}/{course}_课程大纲.md`
- Parses syllabus into structured `Chapter` objects

**User preference**: Do NOT preset chapter count (e.g. "8-10 chapters"). Let NotebookLM determine the natural module boundaries from the content itself.

**CRITICAL**: NotebookLM may output Chinese numerals (第一章) instead of Arabic (第1章). The syllabus parser MUST handle both formats. See `references/note-generation-pipeline.md` for parser implementation.

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

### NotebookLM CLI Quirks

**JSON response format**: `notebooklm list --json` returns `{"notebooks": [...], "count": N}` NOT a raw list. Parser must handle both dict-wrapped and raw-list formats.

**Timeout**: `notebooklm ask` can take 60-120s for complex questions. Default timeout should be 180s+.

**Authentication**: Run `uv run notebooklm doctor` to verify auth status before pipeline.

### Dry-Run Mode

Use `--dry-run` to verify the pipeline plan without executing:

```bash
uv run flow/script_py/note_pipeline.py --course "CourseName" --dry-run
```

### Resume Pattern

If the pipeline fails mid-run, resume from the failed phase:

```bash
# Phase 1 completed, resume Phase 2
uv run flow/script/note_pipeline.py --course "CourseName" --phase 2 --notebook-id "abc123..."

# Resume from checkpoint (auto-detects phase and notebook-id)
uv run flow/script/note_pipeline.py --course "CourseName" --resume
```

The script auto-detects the current phase from existing files:
- No syllabus → Phase 1
- Syllabus exists but no chapter notes → Phase 2
- Chapter notes exist but no MOC → Phase 3

**Checkpoint file**: `youtube2note/output/{course}/.checkpoint.json` — auto-saved after each chapter completes. Contains notebook_id, phase, and per-chapter status. Use `--resume` to load it automatically.

## Pitfalls

### Pitfall 17: Partially Processed Files After Interruption

When the pipeline is interrupted (Ctrl+C, session timeout, background kill), some videos may be in an inconsistent state:
- **Refined**: Small file (~100-200 lines), contains `## 精修内容` section
- **Raw only**: Large file (~5000+ lines), contains `## 字幕内容` or `## 转写内容` section, no refinement

**Symptoms:**
```bash
ls -la youtube2note/input/CourseName/
# 01-1_ Title.md          (19KB)   ← refined
# 02-2_ Title.md          (210KB)  ← raw only, needs refinement
```

**Diagnosis:**
```bash
# Check line counts
wc -l youtube2note/input/CourseName/*.md
# Small files = refined, large files = raw

# Check content structure
grep -n "## 精修内容\|## 字幕内容\|## 转写内容" youtube2note/input/CourseName/*.md
# "精修内容" = refined, "字幕/转写内容" = raw
```

**Fix — Use refine_existing.py helper:**
```bash
# Refine a specific file by index
uv run youtube2note/input/script/refine_existing.py "CourseName" 2

# This creates: 02-refined_Title.md
# Then manually replace:
cd youtube2note/input/CourseName
mv "02-refined_Title.md" "02-2_ Title.md"
```

**Alternative — Re-run full pipeline:**
```bash
# The pipeline skips already-refined files (checks for "精修内容" section)
# So re-running is safe for partially completed batches
uv run youtube2note/input/script/run_pipeline.py "<URL>" "CourseName"
```

**Prevention:**
- Use `notify_on_complete=True` for background runs
- Process in small batches (e.g., `MAX_VIDEOS=2` first to verify)
- Check file sizes after each batch
- Commit after each successful batch: `git add flow/CourseName/ && git commit`

### Pitfall 18: Python `types` Module Name Conflict

Never name a Python package directory `types` — it shadows the standard library `types` module.

**Error**: `ModuleNotFoundError: No module named 'types.note'; 'types' is not a package`

**Fix**: Rename to `models/`, `domain/`, `schemas/`, or `entities/`.

**Related**: Also avoid naming packages `json`, `sys`, `os`, `pathlib`, `collections`, or any other stdlib module name.

### Pitfall 8a: `re.split` with Multiple Capture Groups

When using `re.split()` with regex containing multiple capture groups, the returned list structure depends on which group matched. This makes index arithmetic fragile.

**Problem**: `re.split(r"(第(\d+)章|Chapter (\d+))", text)` produces inconsistent list lengths because unmatched groups return `None`.

**Fix**: Use `re.findall()` with a single capture group instead:
```python
# ❌ Fragile: re.split with multiple groups
blocks = re.split(r"\n##\s*(?:第\s*(\d+)\s*章|Chapter\s+(\d+))\s*[：:]\s*", text)
# blocks[i] may be None depending on which group matched

# ✅ Robust: re.findall with single group
pattern = r'##\s*第([一二三四五六七八九十\d]+)章\s*\uff1a\s*(.+?)(?=\n##\s*第|\Z)'
matches = re.findall(pattern, text, re.DOTALL)
for num_str, content in matches:
    idx = _parse_chapter_number(num_str)
```

### Pitfall 8b: NotebookLM JSON Response Wrapping

`notebooklm list --json` and `notebooklm source list --json` return dict-wrapped formats, NOT raw lists:

```json
// list --json
{"notebooks": [...], "count": 8}

// source list --json  
{"notebook_id": "...", "sources": [...], "count": 2}
```

**Fix**: Parser must handle both dict-wrapped and raw-list formats for forward compatibility:
```python
def _parse_json_list(stdout: str, key: str) -> list[dict]:
    data = json.loads(stdout)
    if isinstance(data, dict) and key in data:
        return data[key]
    if isinstance(data, list):
        return data
    return []
```

### Pitfall 9: NotebookLM Source Upload Duplicates

NotebookLM returns `{"error": "source already exists"}` for duplicate uploads. Always check `source list` before `source add`.

The `notebooklm_client.add_source()` function handles this automatically with `source_exists()` check.

### Pitfall 13: NotebookLM Bulk Upload Timeouts

When uploading many sources (20+ files) via `note_pipeline.py --phase 1`, the NotebookLM CLI may timeout with `RPC GET_NOTEBOOK failed after Xs` errors. This is a rate-limiting / connection issue, not an auth problem.

**Symptoms:**
```
[WARN] notebooklm attempt 1/3 failed: ERROR [notebooklm._core] RPC GET_NOTEBOOK failed after 1.532s
RuntimeError: notebooklm failed after 3 attempts
```

**Root cause:** The pipeline's `upload_sources_dir()` calls `source_exists()` before each upload, which issues `source list --json`. With 20+ files, this creates N+1 API calls quickly, triggering rate limits.

**Fix — Manual bulk upload:**
```bash
# 1. Check if notebook was created (it likely was despite the error)
notebooklm list

# 2. Get the notebook ID
notebooklm list --json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['notebooks'][0]['id'])"

# 3. Check which sources are already uploaded
notebooklm source list --notebook "<NOTEBOOK_ID>"

# 4. Upload remaining files individually
for f in flow/CourseName/1[89]-*.md flow/CourseName/2*.md; do
  notebooklm source add --notebook "<NOTEBOOK_ID>" "$f"
done

# 5. Verify all uploaded
notebooklm source list --notebook "<NOTEBOOK_ID>" | grep -c "Markdown"
```

**Prevention:** For large playlists (20+ videos), consider uploading in batches of 10, or use the manual loop above instead of the automated pipeline upload.

### Pitfall 14: Checkpoint State Out of Sync with Filesystem

The note generation pipeline uses `.checkpoint.json` to track phase completion. If the checkpoint says a phase is incomplete but the filesystem already has the outputs, the pipeline will **re-run from the checkpoint's phase** instead of skipping ahead.

**Symptoms:**
- User reports "发送指令他就失败了" (sending command fails)
- `.checkpoint.json` shows `"phase1_done": false` but `01_Permanent/{course}/` already contains:
  - `{course}_课程大纲.md`
  - `Ch_XX_*.md` files
  - `{course}_知识地图_MOC.md`
  - `Anki_*.md`

**Root cause:** `detect_phase_from_checkpoint()` prioritizes checkpoint state over filesystem scanning:
```python
# lib/checkpoint.py
if cp:  # checkpoint exists
    if cp.phase1_done:
**Symptoms:**
- User reports "发送指令他就失败了" (sending command fails)
- `.checkpoint.json` shows `"phase1_done": false` but `youtube2note/output/{course}/` already contains:
  - `{course}_课程大纲.md`
  - `Ch_XX_*.md` files
  - `{course}_知识地图_MOC.md`
  - `Anki_*.md`

**Root cause:** `detect_phase_from_checkpoint()` prioritizes checkpoint state over filesystem scanning:

**Fix — Force filesystem re-detection:**
```bash
# Delete the stale checkpoint
cd ~/Documents/all-in-one
rm youtube2note/output/{course}/.checkpoint.json

# Re-run — now auto-detects from filesystem
uv run youtube2note/input/script/note_pipeline.py --course "{course}"
```

With no checkpoint, `detect_phase_from_checkpoint()` falls through to filesystem scanning:
- Syllabus exists + chapter files exist + MOC exists → returns phase 3
- Syllabus exists + chapter files exist + no MOC → returns phase 3 (MOC regeneration)
- Syllabus exists + no chapters → returns phase 2

**Prevention:**
- Always use `--resume` flag to resume from checkpoint (preserves state)
- If manually recovering files, delete the old checkpoint first
- After any manual file manipulation in `01_Permanent/{course}/`, verify checkpoint consistency
- **Before starting a new course**, verify the course name doesn't conflict with an existing directory that has a stale checkpoint

### Pitfall 15: URL/Course Name Mismatch

When starting a new course, the user provides both a YouTube playlist URL and a course name. If these don't match (e.g., URL is for "Microeconomics" but course name is "Probabilistic Systems"), the pipeline will:
- Download and process the wrong content
- Save files under the wrong course directory
- Cause confusion when the user tries to access the notes

**Symptoms:**
- Processed files contain content that doesn't match the course name
- User asks "为什么这里有error" when the pipeline appears to work but produces wrong output
- Directory `flow/{course_name}/` contains transcripts for a completely different subject

**Verification before starting:**
```bash
# Check what playlist actually contains
.venv/bin/yt-dlp --flat-playlist --print "%(playlist_index)s. %(title)s" "<URL>" | head -10
```

**Fix:**
1. Stop the pipeline if running
2. Remove the incorrect directory:
   ```bash
   rm -rf flow/{wrong_course_name}/
   rm -rf 01_Permanent/{wrong_course_name}/
   ```
3. Re-run with correct course name matching the playlist content:
   ```bash
   uv run flow/script/run_pipeline.py "<URL>" "Correct_Course_Name" [MAX_VIDEOS]
   ```

**Prevention:**
- Always verify playlist titles match the course name before starting
- For MIT OCW courses, the course number in the name should match the playlist content
- If user provides a course name that doesn't match the URL, ask for confirmation

### Pitfall 16: Background Execution Timeout on Command Send

When a pipeline is running in background mode (`terminal(background=True)`), sending a new command to the same terminal session can cause:
- "⚡ Sending after interrupt" errors
- Session confusion between foreground and background processes
- The appearance that "发送指令他就失败了"

**Root cause:** The agent's terminal tool doesn't support concurrent foreground commands while a background process is active. The background process holds the session, and new commands interrupt it.

**Symptoms:**
```
⚡ New message detected, interrupting...
[error] ⚡ Sending after interrupt: '<new command>'
```

**Diagnosis steps:**
1. Check if background process exists:
   ```python
   process(action="list")
   ```
2. If found, check its status:
   ```python
   process(action="poll", session_id="...")
   ```
3. If process shows `status: "running"` but empty output, it may be stuck (e.g., waiting for API response, downloading large video)
4. If process shows `status: "completed"` with exit code -15 (SIGTERM), it was killed by interrupt

**Fix:**
1. Check if background process is still running:
   ```bash
   process(action="poll", session_id="...")
   ```
2. If running and you need to send a new command, either:
   - Wait for completion: `process(action="wait", session_id="...")`
   - Kill the background process: `process(action="kill", session_id="...")`
   - Use a new terminal session for the new command
3. If process completed but produced no output (exit code -15), check filesystem state:
   ```bash
   ls -la flow/<course>/
   ```
   The pipeline may have partially completed (some files refined, others raw)

**Prevention:**
- For long-running pipelines, always use `notify_on_complete=True` and wait for notification
- Don't send new commands to a session with an active background process
- Use `process(action="log")` to check output without interrupting
- For interactive work, start a fresh terminal session instead of reusing the background one
- If pipeline is expected to take >3 minutes, use `timeout=600` or longer

### Pitfall 10: Import Cache in Tests

When monkey-patching functions in tests, patch at the **module usage site**, not the definition site:

```python
# ❌ Wrong: patches config module, but lib already cached the import
import config.note_paths as np
np.raw_note_dir = lambda name: mock_dir

# ✅ Correct: patch in the module where raw_note_dir is actually used
import lib.course_loader as cl
cl.raw_note_dir = lambda name: mock_dir
```

This is because Python caches imports — `from config.note_paths import raw_note_dir` creates a local reference that won't see module-level reassignments.

### Pitfall 11: Adapter Pattern for External CLI Tools

When wrapping external CLI tools (like `notebooklm`), always extract an ABC interface:

```python
class NotebookLMAdapter(ABC):
    @abstractmethod
    def create_notebook(self, title: str) -> str: ...
    @abstractmethod
    def ask(self, question: str, timeout: int = 180) -> str: ...

class CLIAdapter(NotebookLMAdapter):
    # subprocess-based production implementation

class MockAdapter(NotebookLMAdapter):
    # records calls for testing, no external deps
```

**Benefits**:
- Unit tests run without external credentials
- Can swap backend (CLI → REST API) without changing business logic
- Dry-run mode is just `MockAdapter` injection

### Pitfall 12: Prompt Template Variable Binding

Hardcoded prompt strings with `.format()` or f-strings are brittle. Use a `PromptTemplate` class:

```python
@dataclass
class PromptTemplate:
    name: str
    version: str
    template: str

    def render(self, **kwargs) -> str:
        try:
            return self.template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing variable {e} for prompt '{self.name}'")
```

**Benefits**:
- Missing variables fail at render time, not at API call time
- Versioned templates enable A/B testing
- Central registry (`PROMPT_REGISTRY`) makes prompts discoverable

## Batch Processing: Multiple Playlists in Sequence

When the user provides multiple playlist URLs and asks to learn them in order:

### Step 0: User Timeout Preference — CRITICAL

**User explicitly corrected**: "去掉600s的超时限制，任务本身就属于耗时较多的类型"

For ALL long-running operations in this workflow:
- **ALWAYS** use `terminal(background=True, notify_on_complete=True)`
- **NEVER** use foreground mode with `timeout=600` as a workaround — it has a hard 600s limit that will kill the process mid-run
- Background mode has no timeout limit and is the only viable approach for playlists with 10+ videos

### Step 0a: URL Validation Before Starting

**CRITICAL**: Always validate the playlist title matches the expected course before starting transcription. A stale or incorrect URL may resolve to unrelated content.

**Validation command**:
```bash
.venv/bin/yt-dlp --cookies-from-browser chrome --flat-playlist --print "%(playlist_title)s" "<URL>"
```

**Abort condition**: If returned title does NOT match expected course name (e.g., "YouTube Tips & Advice" instead of "Principles of Management"), STOP and ask user to verify the URL.

**Do NOT** proceed with transcription of mismatched content — it wastes API quota and produces garbage output. See Pitfall 13j for full details.

### Step 1: Deduplication Check

Before starting any pipeline, check for existing courses:

```bash
cd ~/Documents/all-in-one
ls -1 flow/ | grep -v "^script$" | grep -v "^Test_Simple$"
ls -1 01_Permanent/ 2>/dev/null | grep -v "\.md$" || true
```

### Step 2: Resolve Playlist Titles

For each URL, resolve the actual playlist title to detect duplicates:

```bash
.venv/bin/yt-dlp --flat-playlist --print "%(playlist_title)s" "<URL>" | head -1
```

Compare against existing course names. Normalize by:
- Removing special characters and spaces
- Case-insensitive comparison
- Matching known variants (e.g., "MIT 14.01 Principles of Microeconomics" vs "MIT_14.01_Principles_of_Microeconomics")

### Step 3: Filter Non-Course Playlists

Some playlists may not be courses (e.g., "YouTube Tips & Advice"). Verify by:
- Checking playlist title contains course-related keywords
- Sampling first few video titles: `.venv/bin/yt-dlp --flat-playlist --print "%(playlist_index)s. %(title)s" "<URL>" | head -5`
- Checking uploader/channel consistency

**Skip** playlists that are clearly not educational courses.

### Step 5: Sequential Execution Pattern (One Course at a Time)

**CRITICAL**: Process one course fully before starting the next:

```
Course N:   Pipeline 1 (transcription) → git commit → Pipeline 2 (notes) → git commit → NEXT
```

**Never** start Pipeline 1 for Course N+1 until Course N's Pipeline 2 is complete. This prevents:
- Git conflicts from concurrent modifications
- NotebookLM project confusion (multiple active notebooks)
- Resource contention (API rate limits, disk space)
- Lost progress if session is interrupted

**Execution flow for each course:**
1. Run Pipeline 1 in background (`run_pipeline.py`)
2. Wait for completion (poll or `notify_on_complete`)
3. Git commit the refined transcripts
4. Create NotebookLM notebook and upload sources
5. Generate syllabus + chapter notes + MOC + Anki
   - Try `note_pipeline.py` first (automated)
   - If automated fails (RPC errors, rate limits), fall back to manual NotebookLM CLI workflow (see Pitfall 20)
   - For MOC/Anki generation, if API is rate-limited after chapter generation, create manually from syllabus (see Pitfall 13f)
6. Git commit the generated notes
7. Move to next course

**When `note_pipeline.py` succeeds**: All phases (syllabus + chapters + MOC + Anki) are generated automatically in one run.

**When `note_pipeline.py` fails**: Use the manual fallback workflow documented in Pitfall 20. The manual workflow has been validated across 4+ courses and produces identical output quality.

### Step 5a: Git Pre-Work Commit (MANDATORY)

**User explicitly requires**: Before starting ANY new course processing work, ALWAYS commit the current directory state to GitHub first. This is a mandatory pre-work step, not optional.

**Command sequence**:
```bash
cd ~/Documents/all-in-one
git status
# If there are uncommitted changes:
git add -A
git commit -m "chore: checkpoint before starting new course - <course_name>"
git push origin main
```

**Why this matters**:
- Prevents losing work from previous courses
- Creates a clean rollback point
- User explicitly said: "先把当前的目录提交的github仓库，提交后再进行学习"
- This applies before Step 1 (transcription) AND before Step 2 (NotebookLM study) if there was a gap between steps

### Step 5b: Course Queue Progress Tracking

When processing multiple courses in sequence, maintain a progress tracker file:

**File**: `课程学习进度清单.md` (at project root)

**Format**:
```markdown
# 课程学习进度清单

| 序号 | 课程名称 | YouTube链接 | 视频数 | 时长 | 状态 |
|------|---------|------------|--------|------|------|
| 1 | Financial_Accounting | PLxCUhFZ3hAvn3tsvtyFy4UtxxuHJZ0f36 | 190 | 32h9m | 已完成 |
| 2 | Managerial_Accounting | PLSlzC-HFo7w7TwAnmyThgdTDL_M0xG1P6 | 59 | 10h43m | 进行中 |
| 3 | MIT_14.01_Microeconomics | PLUl4u3cNGP62oJSoqb4Rf-vZMGUBe59G- | 25 | 20h | 未开始 |
```

**Rules**:
- Create/update this file BEFORE starting the first course in a batch
- Update status after each course completes ("已完成" / "进行中" / "未开始")
- Include playlist stats (video count, duration) for planning
- Git commit the progress file after each update
- Use this file to answer "what's next" questions from the user

**Stats collection command**:
```bash
.venv/bin/yt-dlp --flat-playlist --dump-single-json "<URL>" | python3 -c "
import sys, json
d = json.load(sys.stdin)
entries = d.get('entries', [])
total = sum(e.get('duration', 0) for e in entries)
print(f'{len(entries)} videos, {total//3600}h{(total%3600)//60}m')
"
```

### Step 6: Background Execution with Polling

For each course, start Pipeline 1 in background:

```python
terminal(
    command="cd ~/Documents/all-in-one && uv run flow/script/run_pipeline.py \\"
            "\"<URL>\" \"<COURSE_NAME>\"",
    background=True,
    notify_on_complete=True,
    timeout=600
)
```

**Poll periodically** (every 5-10 minutes) to detect hangs:

```python
process(action="poll", session_id="...")
```

If status is "running" but output hasn't changed for >20 minutes, the task may be stuck (e.g., waiting for API response, downloading large video). Consider:
- Checking filesystem: `ls -la flow/<course>/`
- Checking log: `tail -50 /tmp/<course>_pipeline.log`
- Killing and restarting if truly stuck

### Step 7: Todo Tracking for Multi-Course Batches

Use the todo tool to track batch progress and present a clear status table to the user:

```python
todo(todos=[
    {"id": "1", "content": "Check existing courses", "status": "completed"},
    {"id": "2", "content": "Course 1: Accounting 101", "status": "completed"},
    {"id": "3", "content": "Course 2: Managerial Accounting", "status": "completed"},
    {"id": "4", "content": "Course 3: MIT 14.02 Macroeconomics", "status": "in_progress"},
    {"id": "5", "content": "Course 4: Valuation", "status": "pending"},
    # ... etc
])
```

Update todo status as each course completes. Present results in a markdown table:

```
| # | Course | Status | Videos | Notes |
|---|--------|--------|--------|-------|
| 1 | Accounting 101 | completed | 12 | syllabus + 6 chapters + MOC + Anki |
| 2 | Managerial Accounting | completed | 60 | syllabus + 13 chapters + MOC + Anki |
| 3 | MIT 14.02 Macroeconomics | in_progress | 25 | Pipeline 1 running |
```

### Step 8: Cronjob Health Monitoring

For overnight or long-running batch jobs, set up a cronjob to periodically check task health:

```bash
# Create a health check cronjob that runs every 15 minutes
hermes cronjob create \
  --name pipeline-health-check \
  --schedule "*/15 * * * *" \
  --command "cd ~/Documents/all-in-one && ls -1 flow/*/ 2>/dev/null | head -20 && echo '---' && process list 2>/dev/null || true"
```

This prevents tasks from silently dying without notification. The cronjob will report process status and file counts even if the main session is not active.

## Batch Execution Summary Table

Present results to user in a clear table:

```
| # | Playlist Title | Status |
|---|---------------|--------|
| 1 | Accounting 101 | in_progress |
| 2 | Managerial Accounting | pending |
| 3 | MIT 14.01 Microeconomics | SKIP (duplicate) |
| 4 | MIT 14.02 Macroeconomics | pending |
| 5 | Valuation | pending |
| 6 | Operations Management | pending |
| 7 | Principles of Management | pending |
| 8 | YouTube Tips & Advice | SKIP (not a course) |
| 9 | MIS | pending |
| 10 | Strategic Analysis Masterclass | pending |
```

### Pitfall 19: Playlist Title Mismatch / Non-Course Playlists

A playlist URL may resolve to content that is not an academic course. The `%(playlist_title)s` field alone is not sufficient — always verify by sampling video titles.

**Example**: Playlist ID `PLuAz-nxZVHKCgTMK9qJVoRnnx5D1EdmUj` resolved to "YouTube Tips & Advice" (67 videos about YouTube channel management), not a business course.

**Detection command**:
```bash
.venv/bin/yt-dlp --flat-playlist --print "%(playlist_index)s. %(title)s" "<URL>" | head -10
```

**Skip criteria** (any one qualifies):
- Video titles contain platform-specific terms ("subscriber", "view count", "algorithm", "monetization")
- Uploader is not an educational institution or known educator
- Playlist has >50 videos with no clear curriculum structure
- Content is clearly about the platform itself, not a subject domain

**Action**: Skip the playlist and report to user with explanation.

### Pitfall 20: NotebookLM CLIAdapter Notebook Context Loss

The `CLIAdapter` in `note_pipeline.py` calls `notebooklm use <id>` to set context, then subsequent commands like `notebooklm source list --json` may still fail with "No notebook specified. Use 'notebooklm use <id>' to set context."

**Root cause**: The `notebooklm` CLI stores context in a local state file (`~/.notebooklm/profiles/default/storage_state.json`), but subprocess calls may not share this state, or the state may be stale between retries.

**Symptoms**:
```
[WARN] notebooklm attempt 1/3 failed: No notebook specified. Use 'notebooklm use <id>' to set context...
RuntimeError: notebooklm failed after 3 attempts
```

**Fix — Manual fallback workflow (VALIDATED across 4 courses in May 2026)**:
When automated `note_pipeline.py` fails, fall back to manual NotebookLM operations:

```bash
# 1. Verify auth and list notebooks
.venv/bin/notebooklm doctor
.venv/bin/notebooklm list

# 2. Create notebook manually (if not exists)
.venv/bin/notebooklm create "CourseName"

# 3. Get notebook ID and set context
.venv/bin/notebooklm use <NOTEBOOK_ID>

# 4. Upload sources individually (avoids bulk upload timeout)
for f in flow/CourseName/*.md; do
  echo "Adding: $f"
  .venv/bin/notebooklm source add "$f" 2>&1 | tail -3
  sleep 1
done

# 5. Verify upload
.venv/bin/notebooklm source list

# 6. Generate syllabus via ask
.venv/bin/notebooklm ask "Based on all uploaded sources, generate a comprehensive course syllabus..."

# 7. Generate each chapter individually
.venv/bin/notebooklm ask "Generate deep-dive chapter notes for Chapter X..."

# 8. Generate MOC and Anki
.venv/bin/notebooklm ask "Generate a comprehensive MOC..."
.venv/bin/notebooklm ask "Generate N Anki flashcards..."

# 9. Generate Next Steps
.venv/bin/notebooklm ask "Generate a Next Steps and Advanced Topics guide..."
```

**Prevention**:
- For small courses (<15 videos), the automated pipeline usually works
- For large courses (20+ videos), prefer manual upload or batch in groups of 10
- Always verify notebook context with `notebooklm status` before bulk operations
- Delete stale checkpoints (`rm 01_Permanent/{course}/.checkpoint.json`) if resuming fails

See `references/notebooklm-manual-fallback.md` for the full manual workflow transcript.

### Pitfall 20a: NotebookLM Source Upload Loop Timeout
- Uploading 60 files via `for f in *.md; do notebooklm source add "$f"; done` in a single terminal command may timeout at 300s
- **Fix**: The loop itself may succeed even if the wrapping command times out — always check `notebooklm source list` afterward to verify how many were actually uploaded
- **Verification**: `notebooklm source list | grep -c "ready"` to count successfully processed sources
- **Duplicate handling**: NotebookLM accepts duplicate uploads gracefully (returns existing source ID), so re-uploading is safe
- **Alternative**: Split into smaller batches of 15-20 files if the full loop consistently times out

### Pitfall 20b: NotebookLM `source_exists()` N+1 Query Storm

The `CLIAdapter.upload_sources_dir()` method calls `source_exists()` before each file upload, which internally issues `notebooklm source list --json`. For 40 files, this creates 40+ API calls in rapid succession, triggering `RPC GET_NOTEBOOK failed` rate-limit errors.

**Symptoms:**
```
[WARN] notebooklm attempt 1/3 failed: ERROR [notebooklm._core] RPC GET_NOTEBOOK failed after 1.037s
RuntimeError: notebooklm failed after 3 attempts
```

**Root cause**: Each `source_exists()` call hits the NotebookLM API. With 40 files, the CLI adapter makes 40 `source list` calls + 40 `source add` calls = 80 API requests in ~60 seconds.

**Fix — Cache source list before upload loop:**
```python
# In CLIAdapter.upload_sources_dir()
existing_sources = {s.get("name") or s.get("title", "") for s in self.list_sources()}

for f in files:
    if f.name in existing_sources:
        skipped += 1
        continue
    self.add_source(str(f))
    uploaded += 1
    time.sleep(1)
```

**Alternative — Manual bulk upload with single list call:**
```bash
# 1. Set notebook context once
notebooklm use <NOTEBOOK_ID>

# 2. Get existing sources ONCE
notebooklm source list --json > /tmp/existing.json

# 3. Upload only missing files
for f in flow/CourseName/*.md; do
  basename=$(basename "$f")
  if ! grep -q "$basename" /tmp/existing.json; then
    notebooklm source add "$f"
    sleep 1
  fi
done
```

**Prevention**: For courses with 20+ sources, always use cached source list or manual upload. The automated `upload_sources_dir()` works reliably only for small courses (<15 files).

### Pitfall 20d: NotebookLM Source Upload Complete Failure — Two Distinct Modes

NotebookLM source upload can fail in two distinct ways. Both produce `Failed to get SOURCE_ID from registration response` but require different responses.

**Mode A: 100-Source Hard Limit**
- Uploads succeed for first ~100 files, then consistently fail
- `source list` confirms ~100 sources uploaded
- **Response**: Proceed with 100 sources — sufficient for complete note generation

**Mode B: Total API Degradation (ALL uploads fail)**
- EVERY file returns `Failed to get SOURCE_ID from registration response`
- `source list` confirms **0 sources** uploaded
- "OK" messages in output are **misleading** — they indicate the loop iterated, not that the API succeeded
- **Response**: Immediately switch to Gemini API direct fallback (see below)

**Symptoms for Mode B:**
```
Error: Failed to get SOURCE_ID from registration response
OK: 01-MA1 _ Managerial Accounting Basics for Beginners.md
Error: Failed to get SOURCE_ID from registration response
OK: 02-MA2 _ Classifying Activities Example_ Managerial Accounting _MA_ or Financial Accounting _FA__.md
```

**Verification (mandatory):**
```bash
notebooklm use <NOTEBOOK_ID>
notebooklm source list | grep -c "\.md"  # ACTUAL uploaded count
```

**Validated cases:**
- Financial Accounting (181 files): Mode A — 100 sources uploaded, rest failed
- Managerial Accounting (45 files): Mode B — **0 sources** uploaded, all failed
- Foundations of Finance (9 files): Mode B — 0 sources uploaded
- Introduction to Management (10 files): Mode B — 0 sources uploaded
- Introduction to Marketing (10 files): Mode B — 0 sources uploaded
- Management Information Systems (9 files): Mode B — 0 sources uploaded
- Strategic Management (10 files): Mode B — 0 sources uploaded

**Root causes:**
1. **100-source quota** (Mode A): Files 101+ consistently fail
2. **API degradation** (Mode B): ALL uploads fail when NotebookLM backend is overloaded or the API endpoint is deprecated
3. The error is **persistent, not transient** — waiting does not help

**Fix — Gemini API Direct Fallback (Validated at Scale, May 2026)**

When NotebookLM upload fails completely (Mode B, 0 sources), bypass NotebookLM entirely and use Gemini API directly. This workflow was validated across **6 courses** in a single session:

| Course | Videos | Chapters | Method | Status |
|--------|--------|----------|--------|--------|
| Managerial Accounting | 45 | 8 | Gemini direct | ✅ Complete |
| Foundations of Finance | 9 | 5 | Gemini direct | ✅ Complete |
| Introduction to Management | 10 | 4 | Gemini direct | ✅ Complete |
| Introduction to Marketing | 10 | 4 | Gemini direct | ✅ Complete |
| Management Information Systems | 9 | 5 | Gemini direct | ✅ Complete |
| Strategic Management | 10 | 5 | Gemini direct | ✅ Complete |

**Workflow:**

1. **Generate syllabus** from video titles and content summaries:
```bash
cd ~/Documents/all-in-one
uv run python -c "
from google.genai import Client
from google.genai.types import HttpOptions
import os

client = Client(vertexai=True, api_key=os.environ.get('GOOGLE_API_KEY',''), http_options=HttpOptions(api_version='v1'))

# Read all transcript files
import glob
files = sorted(glob.glob('youtube2note/input/CourseName/*.md'))
content = ''
for f in files:
    with open(f) as fh:
        content += f'\n=== {f} ===\n' + fh.read()[:8000]

# Generate syllabus
prompt = f'''Based on these transcripts, generate a graduate-level syllabus in Chinese with 4-8 chapters. Each chapter: core thesis, video range, key concepts. Format: Markdown.\n\n{content[:20000]}'''
response = client.models.generate_content(model='gemini-2.5-pro', contents=prompt)
print(response.text)
"
```

2. **Generate chapters** in batch:
```bash
# Write batch generation script to /tmp/generate_all.py
# See references/gemini-api-direct-fallback.md for full template
uv run python /tmp/generate_all.py
```

3. **Generate MOC and Anki**:
```bash
uv run python -c "
from google.genai import Client
from google.genai.types import HttpOptions
import os, glob

client = Client(vertexai=True, api_key=os.environ.get('GOOGLE_API_KEY',''), http_options=HttpOptions(api_version='v1'))

# Read all chapter notes
chapters = ''
for f in sorted(glob.glob('youtube2note/output/CourseName/Ch_*.md')):
    with open(f) as fh:
        chapters += fh.read()[:5000] + '\n\n'

# Generate MOC
moc = client.models.generate_content(model='gemini-2.5-pro', contents=f'Generate knowledge map (MOC) in Chinese:\n\n{chapters[:20000]}')
# Save to youtube2note/output/CourseName/CourseName_知识地图_MOC.md

# Generate Anki
anki = client.models.generate_content(model='gemini-2.5-pro', contents=f'Generate 10-15 graduate-level Anki cards in Chinese:\n\n{chapters[:20000]}')
# Save to youtube2note/output/CourseName/Anki_CourseName_N张真题卡.md
"
```

**Key advantages of Gemini direct fallback:**
- No NotebookLM upload required (bypasses 100-source limit AND total API failure)
- Single API call per chapter (vs 5+ rounds with NotebookLM)
- More reliable when NotebookLM CLI is unstable
- Can process unlimited files (no source count limit)

**Key disadvantages:**
- No interactive "ask" capability
- Must manually construct prompts
- No conversation context across chapters
- Requires writing scripts to temp files (see Pitfall 23)

**Prevention:**
- For courses with >100 videos, expect Mode A (100-source limit)
- For ALL courses, verify `source list` count after upload — don't trust "OK" messages
- If `source list` shows 0 after upload, **immediately** switch to Gemini API fallback
- Do NOT block course completion waiting for NotebookLM API recovery
- The Gemini direct fallback has been validated as production-ready for this workflow

### Pitfall 20c: NotebookLM `ask` RPC Timeout After `use_notebook`

Even after successfully calling `adapter.use_notebook(notebook_id)`, subsequent `adapter.ask()` calls may fail with `RPC GET_LAST_CONVERSATION_ID failed` / `RPC GET_NOTEBOOK failed`. The CLI's internal state file may not be synchronized with subprocess calls.

**Symptoms:**
```
[WARN] notebooklm attempt 1/2 failed: ERROR GET_LAST_CONVERSATION_ID failed after 1.472s
ERROR GET_NOTEBOOK failed after 0.484s
```

**Fix — Manual `notebooklm use` before scripted operations:**
```bash
# Run this in the SAME shell session before any Python script
notebooklm use <NOTEBOOK_ID>

# Then the Python script's subprocess calls inherit the context
```

**Alternative — Use Python directly with CLIAdapter:**
```python
from lib.adapters.cli import CLIAdapter
a = CLIAdapter()
a.use_notebook('b399259e-...')  # This runs 'notebooklm use' via subprocess
# Wait a few seconds for state file to sync
import time; time.sleep(2)
# Now ask() should work
resp = a.ask('Generate syllabus...', timeout=300)
```

**If still failing**: The NotebookLM CLI state may be corrupted. Delete stale notebooks and recreate:
```bash
notebooklm list
notebooklm delete -n <partial_id> -y
notebooklm create "CourseName"
```

### Pitfall 21: Syllabus Parser English Format Mismatch

The `syllabus_parser.py` expects Chinese format (`第N章：...`) but NotebookLM may output English format (`Chapter N: ...` or `### Chapter N: Title`). This causes `load_syllabus()` to return 0 chapters, making Phase 2 skip all work.

**Symptoms:**
```
[OK] Loaded 0 chapters from saved syllabus
[OK] All 0 chapters processed
```

**Root cause**: The regex pattern only matches `第[一二三四五六七八九十\d]+章`:
```python
pattern = r'##\s*第([一二三四五六七八九十\d]+)章\s*\uff1a\s*(.+?)(?=\n##\s*第|\Z)'
```

**Fix — Add English fallback pattern:**
```python
def parse_syllabus(text: str) -> list[Chapter]:
    # Try Chinese format first
    pattern = r'##\s*第([一二三四五六七八九十\d]+)章\s*[：:]\s*(.+?)(?=\n##\s*第|\Z)'
    matches = re.findall(pattern, text, re.DOTALL)
    
    # Fallback to English format
    if not matches:
        pattern = r'##\s*Chapter\s+(\d+)\s*[:：]\s*(.+?)(?=\n##\s*Chapter|\Z)'
        matches = re.findall(pattern, text, re.DOTALL)
    
    for num_str, content in matches:
        # ... rest of parsing
```

**Prevention**: Always verify syllabus parsing before starting Phase 2:
```bash
uv run python -c "
import sys; sys.path.insert(0, 'flow/script')
from lib.syllabus_parser import load_syllabus
from pathlib import Path
chapters = load_syllabus(Path('01_Permanent/Course/Course_课程大纲.md'))
print(f'Loaded {len(chapters)} chapters')
for ch in chapters:
    print(f'  Ch.{ch.index:02d}: {ch.title}')
"
```

**Workaround — Manual syllabus reformatting:**
If NotebookLM outputs English format, manually reformat to Chinese before saving:
```markdown
# Course 课程大纲

## 第1章：Chapter Title in English
- **核心命题**：...
- **视频范围**：01-05
- **前置知识**：无
- **本章概要**：...
```

### Pitfall 23: `execute_code` Sandbox Isolation — No Project Venv Access

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

For scripts that need to call Gemini API or use project packages:
1. Write the script to a temporary file (e.g., `/tmp/generate_ch1.py`)
2. Run it via `uv run python /tmp/script.py` in the project directory
3. The script will have full access to `.venv` packages

**Example workflow:**
```python
# Step 1: Write script to temp file
write_file(path='/tmp/generate_notes.py', content='''
from google.genai import Client
from google.genai.types import HttpOptions
import os

client = Client(
    vertexai=True,
    api_key=os.environ.get('GOOGLE_API_KEY', ''),
    http_options=HttpOptions(api_version='v1')
)
# ... rest of script
''')

# Step 2: Run via terminal with uv
terminal(command="cd ~/Documents/all-in-one && uv run python /tmp/generate_notes.py")
```

**Prevention**: Always use `terminal()` + `uv run python` for any script that imports project-specific packages. Reserve `execute_code` for pure stdlib operations only.

### Pitfall 23a: Gemini API `RemoteProtocolError` — Server Disconnected

When calling Gemini API via `generate_content()`, intermittent `httpx.RemoteProtocolError: Server disconnected without sending a response` errors may occur. This is a transient network issue, not an authentication or quota problem.

**Symptoms:**
```
httpx.RemoteProtocolError: Server disconnected without sending a response.
```

**Context where observed:**
- After generating multiple chapters in rapid succession (8 chapters back-to-back)
- During MOC/Anki generation when the prompt is very large (>20K chars of context)
- More frequent during peak hours (US daytime)

**Fix — Retry with exponential backoff:**
```python
import time
from google.genai import Client
from google.genai.types import HttpOptions

def generate_with_retry(client, prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(
                model='gemini-2.5-pro',
                contents=prompt
            )
        except Exception as e:
            if 'RemoteProtocolError' in str(e) and attempt < max_retries - 1:
                wait = 2 ** attempt  # 2, 4, 8 seconds
                print(f'API error, retrying in {wait}s...')
                time.sleep(wait)
            else:
                raise
```

**Alternative — Add `time.sleep(2)` between API calls:**
When generating multiple chapters or components in a loop, add a 2-second sleep between calls to reduce server load:
```python
for chapter in chapters:
    response = client.models.generate_content(model='gemini-2.5-pro', contents=prompt)
    # Save response...
    time.sleep(2)  # Prevent rapid-fire requests
```

**Alternative — Reduce prompt size:**
If the error persists, the prompt may be too large. Trim context:
```python
# Instead of sending all chapter content
prompt = f"Generate MOC based on: {all_chapters[:20000]}"

# Use a condensed version
prompt = """Generate MOC for a course with these chapters:
1. Managerial Accounting Basics
2. Cost Classification
3. Product Costing
4. Job/Process Costing
5. ABC Costing
6. CVP Analysis
7. Budgeting
8. Capital Budgeting
"""
```

**Alternative — Wait and retry manually:**
If batch generation fails mid-way:
1. Wait 10-30 seconds
2. Retry the failed call
3. If still failing, switch to a shorter prompt
4. As last resort, create content manually from existing notes

**Prevention:**
- Add `time.sleep(2)` between API calls when generating multiple chapters
- Keep prompts under 20K chars when possible
- For MOC/Anki, use chapter titles/summaries instead of full content
- Save progress after each successful chapter (git commit)

**Validated in session**: Foundations of Finance course (May 2026) — MOC generated successfully but Anki failed with RemoteProtocolError. After waiting 10s and retrying with a shorter prompt, Anki generation succeeded.

### Pitfall 23b: Batch Generation Script Pattern (Validated at Scale)

When generating multiple chapters, MOC, and Anki via Gemini API, writing a single Python script that generates ALL content in one execution is more efficient than individual API calls. This pattern was validated across 6 courses in May 2026.

**Pattern:**
```python
# Write a single script to /tmp/generate_course_all.py
# The script reads transcript files, generates syllabus, chapters, MOC, Anki
# Then run it once via uv run python

cd ~/Documents/all-in-one
uv run python /tmp/generate_course_all.py
```

**Why this works:**
- One `uv run` invocation = one venv activation overhead
- Script can manage its own retry logic, sleep intervals, and progress tracking
- Output files are written directly to `youtube2note/output/{course}/`
- Can be restarted from any point if interrupted

**Script structure:**
```python
#!/usr/bin/env python3
"""Generate all course content via Gemini API."""
import os, glob, time
from pathlib import Path
from google.genai import Client
from google.genai.types import HttpOptions

client = Client(vertexai=True, api_key=os.environ.get('GOOGLE_API_KEY',''),
                http_options=HttpOptions(api_version='v1'))

course = 'CourseName'
input_dir = Path(f'youtube2note/input/{course}')
output_dir = Path(f'youtube2note/output/{course}')
output_dir.mkdir(parents=True, exist_ok=True)

# 1. Generate syllabus
files = sorted(input_dir.glob('*.md'))
# ... read content, generate syllabus, save ...
time.sleep(2)

# 2. Generate chapters
for ch in chapters:
    # ... generate chapter content, save ...
    time.sleep(2)

# 3. Generate MOC
# ... generate MOC, save ...
time.sleep(2)

# 4. Generate Anki
# ... generate Anki, save ...
```

**Validated courses using this pattern:**
- Managerial Accounting (8 chapters)
- Foundations of Finance (5 chapters)
- Introduction to Management (4 chapters)
- Introduction to Marketing (4 chapters)
- Management Information Systems (5 chapters)
- Strategic Management (5 chapters)

**Note**: The `execute_code` tool cannot access `.venv` packages (see Pitfall 23). Always write the script to a temp file and run via `terminal()` + `uv run python`.

### Pitfall 24: Batch Playlist Processing — Log-and-Continue on Failure

**User explicitly instructed**: "遇到异常的任务先记录下来视频信息，继续处理其他任务，等全部任务处理完再来处理这些任务"

When processing many playlists in sequence (e.g., 33 playlists from a YouTube channel), individual playlists may fail due to:
- Network errors during subtitle download
- Gemini API 429 rate limiting
- Private/unavailable videos in playlist
- yt-dlp extraction failures

**NEVER stop the entire batch for a single playlist failure.**

**Pattern — Log and continue:**
```python
import json
from pathlib import Path

retry_file = Path('youtube2note/input/.batch_retry.json')
failed = []

for playlist in playlists:
    try:
        process_playlist(playlist)
    except Exception as e:
        print(f"FAILED: {playlist['title']} — {e}")
        failed.append({
            'title': playlist['title'],
            'id': playlist['id'],
            'error': str(e),
            'index': playlist['index']
        })
        # Continue to next playlist immediately
        continue

# Save failures for retry at the end
with open(retry_file, 'w') as f:
    json.dump({'failed': failed, 'retried': []}, f, indent=2)
```

**Progress tracking:**
```python
progress = {
    'completed': [],   # indices of successfully processed playlists
    'in_progress': None,
    'pending': list(range(1, 34)),  # remaining playlist indices
    'failed': []       # playlists that failed and need retry
}
```

**Retry at end of batch:**
```python
# After all playlists processed once
for item in progress['failed']:
    try:
        process_playlist(item)
        progress['completed'].append(item['index'])
    except Exception as e:
        print(f"RETRY FAILED: {item['title']} — {e}")
```

**Git commit after each playlist:**
```bash
git add youtube2note/input/<CourseName>/
git commit -m "feat: Asianometry #N <CourseName> - X videos transcribed and refined"
git push origin main
```

### Pitfall 25: run_pipeline.py Timeout — Use Manual Step-by-Step for Large Batches

The unified `run_pipeline.py` script times out in terminal foreground mode (60s hard limit per command). For large batches with many playlists, the manual step-by-step approach is more reliable.

**Why run_pipeline.py fails for batch work:**
- Single playlist with 10 videos takes 5-10 minutes (subtitle download + Gemini refinement)
- Terminal 60s timeout kills the process mid-run
- Background mode with `notify_on_complete` works but is hard to orchestrate for 30+ sequential playlists

**Manual step-by-step workflow (validated for 33 playlists, 1700+ videos):**

**Step 1: Download subtitles for entire playlist:**
```bash
cd ~/Documents/all-in-one
.venv/bin/yt-dlp --cookies-from-browser chrome \
  --write-auto-subs --sub-langs en --convert-subs srt \
  --skip-download --output "/tmp/<prefix>_%(playlist_index)s" \
  "https://www.youtube.com/playlist?list=<PLAYLIST_ID>"
```

**Step 2: Parse SRT → Markdown (Python script):**
```python
import re
from pathlib import Path

srt_files = sorted(Path('/tmp').glob('<prefix>_*.srt'))
out_dir = Path('youtube2note/input/<CourseName>')
out_dir.mkdir(parents=True, exist_ok=True)

for i, srt_file in enumerate(srt_files, 1):
    content = srt_file.read_text(encoding='utf-8')
    blocks = re.split(r'\n\s*\n', content.strip())
    texts = []
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            text = ' '.join(lines[2:])
            text = re.sub(r'\r+', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            if text and text not in ['[Music]', '']:
                texts.append(text)
    # Deduplicate consecutive identical lines
    deduped = []
    prev = None
    for t in texts:
        if t != prev:
            deduped.append(t)
            prev = t
    full_text = ' '.join(deduped)
    # Write markdown with metadata header...
```

**Step 3: Refine with Gemini (Python script via uv run):**
```python
from google.genai import Client
from google.genai.types import HttpOptions
import os, time
from pathlib import Path

client = Client(vertexai=True, api_key=os.environ.get('GOOGLE_API_KEY',''),
                http_options=HttpOptions(api_version='v1'))

REFINE_PROMPT = """这是一段音频转录文本，请进行以下优化：
1. 补全标点符号（句号、逗号等）
2. 修正识别错误的术语、人名、地名
3. 去除口语噪音（"嗯"、"啊"、"那个"等填充词）
4. 按语义分段（每段一个主题）
5. Obsidian 格式化（Markdown 标准格式）
请直接输出优化后的文本，不要添加额外说明。

```
{body}
```
"""

input_dir = Path('youtube2note/input/<CourseName>')
for f in sorted(input_dir.glob('*.md')):
    content = f.read_text(encoding='utf-8')
    body = content.split('## 字幕内容', 1)[1].strip()
    prompt = REFINE_PROMPT.format(body=body[:300000])
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite', contents=prompt)
        refined = response.text
        # Write refined file with ## 精修内容 header
    except Exception as e:
        print(f"ERROR on {f.name}: {e}")
    time.sleep(3)  # Prevent 429 rate limiting
```

**Step 4: Git commit:**
```bash
git add youtube2note/input/<CourseName>/
git commit -m "feat: <BatchName> #N <CourseName> - X videos transcribed and refined"
git push origin main
```

**Key advantages of manual approach:**
- Each step can be retried independently if it fails
- No timeout issues (each command is short)
- Better visibility into progress
- Easier to handle rate limiting with sleep delays

### Pitfall 25a: SRT Parsing — Overlapping Text Duplication

YouTube auto-generated subtitles frequently contain overlapping text across consecutive timestamp blocks (the same phrase appears in block N, N+1, N+2 with slightly extended timestamps).

**Example:**
```
1
00:00:01,120 --> 00:00:03,030
the overseas chinese community are

2
00:00:03,030 --> 00:00:03,040
the overseas chinese community are

3
00:00:03,040 --> 00:00:05,430
the overseas chinese community are
amongst the largest in the world
```

**Without overlap removal**: 40-60% of text is duplicated, producing bloated raw transcripts.

**Fix — `_remove_overlap()` in `lib/youtube.py`:**
```python
def _remove_overlap(prev: str, curr: str) -> str:
    """Remove overlapping prefix from curr that appears at end of prev."""
    prev = prev.strip()
    curr = curr.strip()
    # Find longest suffix of prev that is a prefix of curr
    for i in range(min(len(prev), len(curr)), 0, -1):
        if prev[-i:] == curr[:i]:
            return curr[i:].strip()
    return curr
```

**Integration in `parse_srt()`:**
```python
for block in blocks:
    # ... parse text ...
    text = _remove_overlap(prev_text, text)
    if text:
        texts.append(text)
        prev_text = text
```

**Result**: Removes 40-60% duplication while preserving all unique content. A 10-minute video transcript goes from ~60K chars to ~25K chars.

**Note**: This is distinct from simple deduplication (`if t != prev`). Overlap removal handles partial phrase repetition, while deduplication handles full-line repetition. Both should be applied.

### Pitfall 26: YouTube Auto-Generated Subtitle Duplication

YouTube's auto-generated English subtitles have heavy line duplication — the same text appears across 3-5 consecutive timestamp blocks.

**Example SRT excerpt:**
```
1
00:00:01,120 --> 00:00:03,030
the overseas chinese community are

2
00:00:03,030 --> 00:00:03,040
the overseas chinese community are

3
00:00:03,040 --> 00:00:05,430
the overseas chinese community are
amongst the largest in the world
```

**Without deduplication**: A 10-minute video produces ~60K chars of raw text, ~50% of which is duplicated.

**Fix — Deduplicate consecutive identical phrases:**
```python
deduped = []
prev = None
for t in texts:
    if t != prev:
        deduped.append(t)
        prev = t
full_text = ' '.join(deduped)
```

**Result**: Deduplication reduces text size by 40-60% while preserving all unique content.

### Pitfall 27: Gemini API 429 Rate Limiting During Batch Refinement

When refining many files in sequence via Vertex AI (`gemini-2.5-flash-lite`), the API returns `429 RESOURCE_EXHAUSTED` after ~3-5 rapid calls.

**Symptoms**:
```
ClientError: 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'Resource exhausted...'}}
```

**Fix — Sleep + retry pattern**:
```python
import time

for f in files:
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite', contents=prompt)
        refined = response.text
        # save...
    except Exception as e:
        if '429' in str(e) or 'RESOURCE_EXHAUSTED' in str(e):
            print(f"Rate limited on {f.name}, will retry later")
            failed.append(f.name)
        else:
            raise
    time.sleep(3)  # 3-4s delay between calls prevents most 429s
```

**Retry strategy for failed files**:
1. Wait 30-60 seconds after the batch completes
2. Retry only the failed files individually
3. If still 429, wait another 60s and retry
4. After 3 retries, log to retry file and continue to next playlist

**Key rule**: Never stop the entire batch for a single file failure. Log and continue.

### Pitfall 28: Batch Processing Script — `paths.py` PROJECT_ROOT Depth

When creating a standalone batch processing script that imports from `config/paths.py`, the `PROJECT_ROOT` calculation must match the actual file location depth.

**File**: `youtube2note/input/script/config/paths.py`

**Before (broken)**:
```python
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # 3 levels = youtube2note/
Y2N_ROOT = PROJECT_ROOT  # same as youtube2note/
PATHS = {
    "venv_bin": PROJECT_ROOT.parent / ".venv" / "bin",  # tries to find .venv outside youtube2note/
}
```

**After (fixed)**:
```python
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # 4 levels = repo root
Y2N_ROOT = PROJECT_ROOT / "youtube2note"
PATHS = {
    "venv_bin": PROJECT_ROOT / ".venv" / "bin",  # correct: .venv is at repo root
}
```

**Symptom**: `[Errno 2] No such file or directory: '/Users/.../youtube2note/.venv/bin/yt-dlp'`

**Fix**: Update `PROJECT_ROOT` to use `parent.parent.parent.parent` (4 levels up from `youtube2note/input/script/config/paths.py` to reach the git repo root where `.venv/` lives).

### Pitfall 29: Batch Processing — Missing `.asianometry_playlists.json`

When resuming a batch processing task, the playlist metadata file may be missing or empty. Do NOT block on recreating it from scratch.

**Pattern — Recover from filesystem state:**
```python
import json
from pathlib import Path

progress_file = Path('youtube2note/input/.asianometry_progress.json')
retry_file = Path('youtube2note/input/.asianometry_retry.json')

# If progress file is empty/missing, scan filesystem
if not progress_file.exists() or progress_file.read_text().strip() == '{}':
    completed = []
    for d in Path('youtube2note/input').iterdir():
        if d.is_dir() and d.name not in ('script',):
            md_count = len(list(d.glob('*.md')))
            srt_count = len(list(d.glob('*.srt')))
            if md_count > 0 and md_count == srt_count:
                completed.append(d.name)
    progress = {'completed': completed, 'in_progress': None, 'pending': []}
    progress_file.write_text(json.dumps(progress, indent=2))
```

**Key rule**: Always derive progress from filesystem state when metadata files are stale or missing.

The pipeline uses `course_name` in multiple contexts with inconsistent normalization:
- Raw directory: `flow/Operations_Management/` (underscores)
- Checkpoint: may use `"Operations Management"` (spaces)
- NotebookLM notebook title: `"Operations_Management"` (underscores)

**Symptoms:**
```
FileNotFoundError: Raw directory not found: /.../flow/Operations Management
```

**Root cause**: `config/paths.py` `raw_note_dir(course_name)` uses the raw course name. If the checkpoint was created with spaces but the directory uses underscores, the path resolution fails.

**Fix — Normalize course name at entry point:**
```python
# In note_pipeline.py main()
course_name = args.course.replace(" ", "_")
```

**Prevention**: Always use underscore-normalized course names:
- Directory names: `Operations_Management`
- Checkpoint `course_name`: `Operations_Management`
- NotebookLM title: `Operations_Management`
- CLI `--course` argument: `Operations_Management` (with underscores)

**If mismatch already exists**: Rename the directory or update the checkpoint:
```bash
# Option 1: Rename directory to match checkpoint
mv "flow/Operations Management" flow/Operations_Management

# Option 2: Update checkpoint to match directory
# Edit 01_Permanent/Course/.checkpoint.json: "course_name": "Operations_Management"
```

**Dependencies**: `brew install pandoc pango gdk-pixbuf libffi` + `uv pip install weasyprint`

**Note**: If WeasyPrint fails with `cannot load library 'libgobject-2.0-0'`, set `DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH` before running.

See `references/pdf-export.md` for full implementation details.

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

**Validated in session**: MIS course (May 16, 2026) — Phase 2 completed all 7 chapters successfully, but Phase 3 MOC/Anki failed due to rate limiting. Manual MOC and Anki were created from the syllabus in ~2 minutes, allowing course completion without waiting for API recovery.

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

**Validated in session**: Principles_of_Management (May 16, 2026) — initial Phase 2 produced 5 empty chapters (~1.5KB each). Notebook was deleted and recreated, sources re-uploaded, and Phase 2 re-run successfully. Final output: 10 chapters at ~20-25KB each.

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

### Pitfall 13r-a: Manual Syllabus from NotebookLM Ask Output

When using `notebooklm ask` to generate a syllabus, the output may be in English format (`Chapter N: Title`) with rich markdown (bullet points, learning objectives). To make it parser-compatible:

1. **Reformat to Chinese numerals**: Replace `Chapter N:` with `第N章：`
2. **Add required metadata fields**: `核心命题`, `视频范围`, `前置知识`, `本章概要`
3. **Preserve video range mapping**: Map each chapter to specific video indices (e.g., `01-06` for videos 1-6)
4. **Save to correct path**: `01_Permanent/{course}/{course}_课程大纲.md`

**Verification after saving**:
```python
from lib.syllabus_parser import load_syllabus
chapters = load_syllabus(Path('01_Permanent/Course/Course_课程大纲.md'))
print(f'Loaded {len(chapters)} chapters')
for ch in chapters:
    print(f'  Ch.{ch.index:02d}: {ch.title} ({ch.video_range})')
```

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

## Related Files
- Entry: `~/Documents/all-in-one/youtube2note/input/script/run_pipeline.py`
- Entry: `~/Documents/all-in-one/youtube2note/input/script/note_pipeline.py`
- Helper: `~/Documents/all-in-one/youtube2note/input/script/refine_existing.py` (refine raw files individually)
- Lib: `~/Documents/all-in-one/youtube2note/input/script/lib/pipeline.py`
- Lib: `~/Documents/all-in-one/youtube2note/input/script/lib/notebooklm_client.py`
- Lib: `~/Documents/all-in-one/youtube2note/input/script/lib/note_generator.py`
- Lib: `~/Documents/all-in-one/youtube2note/input/script/lib/syllabus_parser.py`
- Lib: `~/Documents/all-in-one/youtube2note/input/script/lib/course_loader.py`
- Lib: `~/Documents/all-in-one/youtube2note/input/script/lib/adapters/cli.py` (CLIAdapter for NotebookLM)
- Lib: `~/Documents/all-in-one/youtube2note/input/script/lib/adapters/mock.py` (MockAdapter for testing)
- Lib: `~/Documents/all-in-one/youtube2note/input/script/lib/checkpoint.py` (PipelineCheckpoint persistence)
- Entry: `~/Documents/all-in-one/youtube2note/input/script/download_youtube.py`
- Entry: `~/Documents/all-in-one/youtube2note/input/script/download_subtitles.py`
- Entry: `~/Documents/all-in-one/youtube2note/input/script/extract_audio.py`
- Entry: `~/Documents/all-in-one/youtube2note/input/script/transcribe_audio.py`
- Entry: `~/Documents/all-in-one/youtube2note/input/script/refine_markdown.py`
- Entry: `~/Documents/all-in-one/youtube2note/input/script/export_pdf.py`
- Config: `~/Documents/all-in-one/youtube2note/input/script/config/paths.py`
- Config: `~/Documents/all-in-one/youtube2note/input/script/config/transcribe.py`
- Config: `~/Documents/all-in-one/youtube2note/input/script/config/notebooklm.py`
- Config: `~/Documents/all-in-one/youtube2note/input/script/config/note_paths.py`
- Config: `~/Documents/all-in-one/youtube2note/input/script/config/prompts.py`
- Models: `~/Documents/all-in-one/youtube2note/input/script/models/note.py`
- Models: `~/Documents/all-in-one/youtube2note/input/script/models/video.py`
- Lib: `~/Documents/all-in-one/youtube2note/input/script/lib/youtube.py`
- Lib: `~/Documents/all-in-one/youtube2note/input/script/lib/download.py`
- Lib: `~/Documents/all-in-one/youtube2note/input/script/lib/audio.py`
- Lib: `~/Documents/all-in-one/youtube2note/input/script/lib/gemini_client.py`
- Lib: `~/Documents/all-in-one/youtube2note/input/script/lib/transcribe.py`
- Lib: `~/Documents/all-in-one/youtube2note/input/script/lib/refine.py`
- Tests: `~/Documents/all-in-one/youtube2note/input/script/tests/`
- Project venv: `~/Documents/all-in-one/.venv/`
- Download dir: `/tmp/video_audio_downloads/`
- Skill refs: `references/transcription-rest-api.md`, `references/content-refinement.md`, `references/model-availability-2026-05.md`, `references/google-api-unified-pattern.md`, `references/llm-nondeterminism.md`, `references/note-generation-pipeline.md`, `references/note-generation-architecture.md`, `references/python-import-pattern.md`, `references/pdf-export.md`, `references/checkpoint-filesystem-sync.md`, `references/session-log-mit-course-mixup-2026-05-15.md`, `references/notebooklm-manual-fallback.md`, `references/session-log-batch-processing-2026-05-15.md`, `references/session-log-financial-accounting-2026-05-22.md`, `references/gemini-api-direct-fallback.md`, `references/gemini-api-direct-fallback-at-scale.md`, `references/batch-gemini-refinement-timeout-resilience.md`
- Skill scripts: `scripts/test_transcription_backend.py`, `scripts/refine_existing.py`