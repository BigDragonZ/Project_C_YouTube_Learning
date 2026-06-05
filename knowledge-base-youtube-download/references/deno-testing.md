# Deno Test Patterns Reference

Session: 2026-05-14 — Establishing unit test coverage for script lib modules.

## Test File Naming

- Co-located in `flow/script/tests/`
- Named `{module}_test.ts` matching lib file
- Import from `../lib/{module}.ts`

## Running Tests

```bash
cd ~/Documents/all-in-one
deno test --allow-net --allow-read --allow-write --allow-run --allow-env flow/script/tests/
```

## Assert Patterns

```ts
import { assertEquals, assertStringIncludes } from "https://deno.land/std@0.224.0/assert/mod.ts";

// Equality
assertEquals(entries.length, 2);
assertEquals(entries[0].text, "Hello world");

// String matching
assertStringIncludes(md, "# Test Video");
assertStringIncludes(md, "**序号**: 5");

// Boolean
assertEquals(info.duration > 0, true);
```

## Async Tests

```ts
Deno.test("probeFile returns valid metadata", async () => {
  const { probeFile } = await import("../lib/audio.ts");
  const info = await probeFile(TEST_AUDIO);
  assertEquals(typeof info.duration, "number");
});
```

## Test Data Strategy

| Module | Test Data Source |
|--------|-----------------|
| `paths.ts` | Static assertions (no I/O) |
| `youtube.ts` | Inline SRT strings (no network) |
| `audio.ts` | Existing artifact files (probe only, no extraction) |

## Coverage Checklist

- [ ] Pure functions: all branches tested
- [ ] I/O functions: at least happy path + error path
- [ ] Edge cases: empty input, malformed data, special characters
- [ ] Integration: end-to-end with real artifacts (optional, slower)
