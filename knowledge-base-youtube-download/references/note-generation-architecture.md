# Note Generation Pipeline Architecture Reference

Session: 2026-05-15 — Architectural refactoring for skill-callability.

## Problem

Initial implementation had tight coupling, SRP violations, and no state persistence:
- NotebookLM CLI hardcoded → untestable, unswappable
- `note_pipeline.py` mixed argparse, phase detection, execution, error handling
- No checkpoint → manual `--notebook-id --phase` recovery after interruption
- Prompts as raw strings → no versioning, no variable validation

## Solution: Three New Architectural Patterns

### 1. Adapter Pattern (lib/adapters/)

```python
# base.py
class NotebookLMAdapter(ABC):
    @abstractmethod
    def create_notebook(self, title: str) -> str: ...
    @abstractmethod
    def ask(self, question: str, timeout: int = 180) -> str: ...
    @abstractmethod
    def upload_source(self, path: Path) -> None: ...

# cli.py — production
class CLIAdapter(NotebookLMAdapter):
    def ask(self, question, timeout=180):
        return _retry_run(["ask", question], timeout=timeout)

# mock.py — testing/dry-run
class MockAdapter(NotebookLMAdapter):
    def __init__(self):
        self.calls: list[dict] = []
    def ask(self, question, timeout=180):
        self.calls.append({"question": question, "timeout": timeout})
        return f"[MOCK] {question[:50]}..."
```

**Injection point**: `note_pipeline.py` creates adapter based on `--dry-run` flag:
```python
adapter: NotebookLMAdapter = MockAdapter() if args.dry_run else CLIAdapter()
```

### 2. Checkpoint State Machine (lib/checkpoint.py)

```python
@dataclass
class ChapterCheckpoint:
    index: int
    title: str
    completed_rounds: int = 0
    status: str = "pending"  # pending | running | completed | failed
    error: str | None = None

@dataclass
class PipelineCheckpoint:
    course_name: str
    notebook_id: str
    phase: int = 1
    phase1_done: bool = False
    phase2_done: bool = False
    phase3_done: bool = False
    chapters: list[ChapterCheckpoint] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
```

**Auto-save**: After each chapter completes, `save_checkpoint(cp, permanent_dir)` writes JSON.
**Resume**: `--resume` flag loads checkpoint, overrides auto-detection.

### 3. PromptTemplate Engine (lib/prompt_engine.py)

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

# Registry
PROMPT_REGISTRY: dict[str, PromptTemplate] = {
    "syllabus": PromptTemplate("syllabus", "1.0", SYLLABUS_PROMPT),
    "deep_dive": PromptTemplate("deep_dive", "1.0", DEEP_DIVE_PROMPT),
    ...
}

def get_prompt(name: str) -> PromptTemplate:
    if name not in PROMPT_REGISTRY:
        raise KeyError(f"Unknown prompt: {name}")
    return PROMPT_REGISTRY[name]
```

**Usage in note_generator.py**:
```python
prompt = get_prompt("deep_dive").render(
    video_range=ch.video_range,
    chapter_title=ch.title,
)
```

## Chinese Numeral Parsing

NotebookLM outputs `第一章` not `第1章`. Parser uses lookup table:

```python
_CHINESE_NUMERALS = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
}

def _parse_chapter_number(s: str) -> int:
    if s.isdigit():
        return int(s)
    total = 0
    for c in s:
        if c in _CHINESE_NUMERALS:
            total += _CHINESE_NUMERALS[c]
    return total if total > 0 else 0
```

Regex uses `re.findall()` (not `re.split()`) for stable capture:
```python
pattern = r'##\s*第([一二三四五六七八九十\d]+)章\s*\uff1a\s*(.+?)(?=\n##\s*第|\Z)'
matches = re.findall(pattern, text, re.DOTALL)
```

## NotebookLM JSON Response Formats

Always handle dict-wrapped responses:

```python
# list --json → {"notebooks": [...], "count": N}
# source list --json → {"sources": [...], "count": N}

def _parse_json_list(stdout: str, key: str) -> list[dict]:
    data = json.loads(stdout)
    if isinstance(data, dict) and key in data:
        return data[key]
    if isinstance(data, list):
        return data
    return []
```

## File Structure After Refactor

```
flow/script_py/
├── note_pipeline.py              # CLI: argparse + adapter selection + checkpoint resume
├── config/
│   ├── notebooklm.py             # CLI path, timeout defaults
│   ├── note_paths.py             # raw_note_dir(), permanent_note_dir(), etc.
│   └── prompts.py                # Backward-compat raw strings
├── models/
│   └── note.py                   # VideoInfo, Chapter, CourseContext, PressureTestRound
├── lib/
│   ├── adapters/
│   │   ├── __init__.py           # exports NotebookLMAdapter, CLIAdapter, MockAdapter
│   │   ├── base.py               # ABC interface
│   │   ├── cli.py                # subprocess-based production adapter
│   │   └── mock.py               # call-recording test adapter
│   ├── checkpoint.py             # PipelineCheckpoint, save/load/detect
│   ├── prompt_engine.py          # PromptTemplate, PROMPT_REGISTRY, get_prompt()
│   ├── note_generator.py         # Phase 1/2/3 logic (adapter-injected)
│   ├── syllabus_parser.py        # parse_syllabus(), _parse_chapter_number()
│   ├── course_loader.py          # load_videos(), _parse_filename()
│   └── notebooklm_client.py      # Legacy wrapper (kept for compat)
└── tests/
    ├── test_syllabus_parser.py   # 4 tests: parse, empty, no-chapter, save/load
    ├── test_note_paths.py        # 6 tests: dirs, chapter/MOC/Anki paths
    └── test_course_loader.py     # 5 tests: filename parse, index/files loading
```

## Testing

```bash
cd ~/Documents/all-in-one/flow/script_py

# Unit tests
uv run python tests/test_syllabus_parser.py
uv run python tests/test_note_paths.py
uv run python tests/test_course_loader.py

# Dry-run integration (no external calls)
uv run note_pipeline.py --course "TestCourse" --dry-run

# Resume from checkpoint
uv run note_pipeline.py --course "TestCourse" --resume
```

## Key Design Principles

1. **Dependency injection**: `NotebookLMAdapter` passed to `note_generator` functions, not constructed inside them.
2. **Fail fast**: `PromptTemplate.render()` raises `ValueError` on missing variables before API call.
3. **Resume anywhere**: Checkpoint saved after each chapter. `--resume` reconstructs full state.
4. **Test without credentials**: `MockAdapter` enables full pipeline testing without NotebookLM auth.
5. **Forward compatibility**: JSON parsers handle both dict-wrapped and raw-list responses.
