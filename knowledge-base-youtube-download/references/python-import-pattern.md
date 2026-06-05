# Python Import Pattern for Knowledge Base Scripts

## Problem

When scripts live in a nested directory (`flow/script_py/`) and use relative imports (`from ..config.paths import ...`), they fail when run directly:

```
ImportError: attempted relative import beyond top-level package
```

## Solution

Use **absolute imports** in all `lib/` and `config/` modules:

```python
# lib/youtube.py
from config.paths import BINARIES        # ✓ absolute
# from ..config.paths import BINARIES    # ✗ relative — breaks when run directly
```

Entry scripts set `PYTHONPATH` or use `sys.path.insert` when needed:

```bash
# Run from project root
PYTHONPATH=flow/script_py python3 flow/script_py/download_subtitles.py ...
```

## Why This Works

- `lib/` modules are imported by multiple entry scripts
- Absolute imports make the module graph independent of the caller's location
- `PYTHONPATH` injection is a one-time setup cost at the CLI level
- Tests also use `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))`

## Directory Structure

```
flow/script_py/
├── config/
│   ├── paths.py
│   └── transcribe.py
├── models/               # was 'types/' — renamed to avoid stdlib conflict
│   └── note.py
├── lib/
│   ├── youtube.py        # from config.paths import ...
│   ├── download.py       # from config.paths import ...
│   ├── audio.py          # from config.paths import ...
│   └── transcribe.py     # from config.paths import ...
├── tests/
│   └── test_*.py         # sys.path.insert + from lib.xxx import ...
└── *.py                  # entry scripts
```

## Naming Rules

**NEVER** name a Python package directory after a standard library module:

| ❌ Forbidden | ✅ Safe Alternative | Why |
|-------------|-------------------|-----|
| `types/` | `models/`, `schemas/`, `entities/` | Shadows `types` module |
| `json/` | `data/`, `serialization/` | Shadows `json` module |
| `sys/` | `system/`, `platform/` | Shadows `sys` module |
| `os/` | `filesystem/`, `paths/` | Shadows `os` module |
| `pathlib/` | `paths/`, `locations/` | Shadows `pathlib` module |
| `collections/` | `containers/`, `structs/` | Shadows `collections` module |

**Error pattern**: `ModuleNotFoundError: No module named 'types.note'; 'types' is not a package`

This happens because `import types` resolves to the stdlib `types` module first, making your package invisible.

## Monkey-Patching in Tests

When patching imports in tests, patch at the **module usage site**, not the definition site:

```python
# ❌ Wrong: patches config module, but lib already cached the import
import config.note_paths as np
np.raw_note_dir = lambda name: mock_dir

# ✅ Correct: patch in the module where raw_note_dir is actually used
import lib.course_loader as cl
cl.raw_note_dir = lambda name: mock_dir
```

This is because Python caches imports — `from config.note_paths import raw_note_dir` creates a local reference that won't see module-level reassignments.

## Migration from Deno/TypeScript

When rewriting Deno scripts to Python:
1. Replace `import.meta.url` resolution with `Path(__file__).resolve()`
2. Replace `Deno.Command` with `subprocess.run`
3. Replace `await Deno.readTextFile` with `Path.read_text`
4. Replace `await Deno.writeTextFile` with `Path.write_text`
5. Replace `Deno.mkdir` with `Path.mkdir(parents=True, exist_ok=True)`
6. Replace `Deno.stat` with `Path.stat`
7. Replace `Deno.remove` with `Path.unlink(missing_ok=True)`
