# LLM Non-Determinism in Content Refinement

Session: 2026-05-15 — User observed that re-running the same refinement pipeline on identical input produced significantly different outputs.

## Problem

Running `refine_markdown.py` twice on the same transcription file produced:

| Run | Output chars | Key differences |
|-----|-------------|-----------------|
| 1st | 13232 | Detailed 16-item classroom exercise list, extensive examples |
| 2nd | 10673 | Summarized descriptions, no itemized lists, different paragraph structure |

The user initially suspected the file deletion/replacement logic was corrupting content. Investigation showed the issue was LLM non-determinism, not file handling.

## Root Causes

### 1. Temperature > 0

```python
# lib/refine.py
config = GenerateContentConfig(temperature=0.2, ...)  # NOT 0
```

Any temperature > 0 introduces randomness in token sampling. Even `temperature=0` with Gemini may have residual non-determinism from `thought` tokens.

### 2. Thought Tokens (gemini-2.5-pro / gemini-3.1-pro-preview)

These models use internal reasoning chains before generating output:

```
usage_metadata: {
  "thoughts_token_count": 93-476,
  ...
}
```

The reasoning path varies between calls, affecting final output structure even with identical input.

### 3. Max Output Tokens Limit

```python
config = GenerateContentConfig(max_output_tokens=8192, ...)
```

When input is large (200K+ chars of transcription), the model must compress significantly. Different runs make different compression choices:
- Run 1: preserves detailed examples, drops some context
- Run 2: summarizes examples, preserves more context

### 4. Context Window Variance

Minor input length differences (e.g., 217537 vs 217531 chars) shift attention patterns across the context window.

## Mitigation Strategies

| Strategy | Effect | Trade-off |
|----------|--------|-----------|
| `temperature=0` | Reduces sampling randomness | Still affected by thought tokens |
| `top_k=1` | Greedy decoding | May reduce output quality/diversity |
| Cache responses | Same input → same output | Requires storage, stale content risk |
| Single-pass pipeline | Run once, never re-refine | Simplest, but no iteration |
| Chunked refinement | Process smaller sections | More API calls, context loss at boundaries |

## Recommendation

For knowledge base pipelines where consistency matters:

1. **Run the pipeline once per video** — do not re-run refinement on already-processed content
2. **If re-running is needed**, expect output differences and use `temperature=0` to minimize variance
3. **Store raw transcription** (before refinement) as backup, even if deleting intermediate files
4. **Consider the first refinement as canonical** — subsequent runs are "revisions" not "reproductions"

## User Preference

User explicitly asked: "精修成功后，把原来的文件删除掉，只保留最终输出."

Implementation: `_save_refined()` writes to temp file → deletes raw → renames temp to final. This is correct and unrelated to output variance.

## See Also

- `lib/refine.py` — refinement implementation
- `lib/gemini_client.py` — unified client with configurable temperature
- `references/content-refinement.md` — prompt template and LaTeX examples
