# Script Architecture Reference

Session: 2026-05-14 — Refactoring monolithic Deno scripts into a maintainable module structure.

## Problem

Initial scripts (`download_youtube.ts`, `download_subtitles.ts`) were monolithic:
- All logic in one file
- Hardcoded paths scattered throughout
- No type definitions
- Duplicated yt-dlp invocation code
- Difficult to extend or test

## Solution: Layered Architecture

```
flow/script/
├── config/
│   └── paths.ts          # Centralized paths, binaries, filename builders
├── types/
│   └── video.ts          # Domain types (VideoMeta, SubtitleEntry, CourseConfig)
├── lib/
│   ├── youtube.ts        # YouTube operations
│   └── download.ts       # Video download operations
└── <entry>.ts            # CLI entrypoint: only parsing + orchestration
```

### Layer Responsibilities

| Layer | Role | Example |
|-------|------|---------|
| `config/` | Environment abstraction, path resolution | `PROJECT_ROOT`, `BINARIES.ytDlp`, `courseDir()` |
| `types/` | Domain model contracts | `interface VideoMeta { id, title, url, index }` |
| `lib/` | Reusable business logic | `fetchTitle()`, `downloadSubtitle()`, `parseSrt()`, `toMarkdown()` |
| Entry script | CLI parsing, I/O, orchestration | `Deno.args`, `console.log`, error handling, `Deno.exit` |

### Key Design Decisions

1. **PROJECT_ROOT calculation** — Must account for import depth:
   - File at `flow/script/config/paths.ts`
   - `dirname(dirname(dirname(dirname(import.meta.url))))` → project root
   - Test with `deno eval` before committing

2. **yt-dlp path** — Always absolute via `config/paths.ts`:
   ```ts
   export const BINARIES = {
     ytDlp: join(PATHS.venvBin, "yt-dlp"),
   };
   ```
   Never rely on `$PATH` or `which`.

3. **Filename standardization** — `buildFilename(index, title, ext)`:
   - Pads index to 2 digits: `01`, `02`, ...
   - Sanitizes title: replaces `<>:"/\|?*` with `_`
   - Pattern: `{index}-{safeTitle}.{ext}`

4. **Error handling** — lib functions throw; entry scripts catch and exit:
   ```ts
   // lib/youtube.ts
   if (code !== 0) throw new Error(`fetchTitle failed: ${stderr}`);

   // entry script
   try { ... } catch (e: any) {
     console.error(`[ERROR] ${e.message}`);
     Deno.exit(1);
   }
   ```

5. **Cleanup** — Temporary files removed in `finally` or after successful write:
   ```ts
   const tempBase = `${outDir}/_tmp_${Date.now()}`;
   const srtFile = await downloadSubtitle(url, tempBase);
   // ... process ...
   await Deno.remove(srtFile);
   ```

## Migration Pattern

When adding a new feature (e.g., "download audio only"):

1. Add type to `types/video.ts` if new domain concept
2. Add function to `lib/` module (or new `lib/audio.ts`)
3. Add CLI flag to entry script, keep orchestration thin
4. Never duplicate yt-dlp invocation logic

## Testing Checklist

- [ ] `deno eval` confirms `PROJECT_ROOT` resolves correctly
- [ ] Script runs from project root: `deno run flow/script/<name>.ts ...`
- [ ] Output lands in correct `flow/{course}/` directory
- [ ] Temporary files are cleaned up
- [ ] Exit code 0 on success, 1 on error
