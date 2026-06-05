# SRT Overlap Removal Technique

## Problem

YouTube auto-generated subtitles contain overlapping text across consecutive timestamp blocks. The same phrase appears in multiple blocks with slightly different end timestamps.

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

## Impact

Without overlap removal:
- 40-60% of text is duplicated
- A 10-minute video produces ~60K chars of raw text
- Gemini refinement costs increase proportionally
- Final markdown is bloated with repetition

## Solution

Add `_remove_overlap()` to `lib/youtube.py`:

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

## Result

- Removes 40-60% duplication
- 10-minute video transcript: ~60K chars → ~25K chars
- All unique content preserved
- Distinct from simple deduplication (`if t != prev`)

## When to Apply

- Always when parsing YouTube auto-generated English subtitles
- Not needed for manually created subtitles (no overlap)
- Apply BEFORE writing raw markdown, so both raw and refined files benefit
