# Session Log: MIT 6.041 vs 14.01 Course Mixup (2026-05-15)

## Problem Report

User attempted to start learning a new course:
- URL: https://www.youtube.com/playlist?list=PLUl4u3cNGP62oJSoqb4Rf-vZMGUBe59G-
- Course name provided: `MIT_6.041_Probabilistic_Systems`
- Command: `uv run flow/script/run_pipeline.py "<URL>" "MIT_6.041_Probabilistic_Systems" 2`

User reported: "为什么发送指令他就失败了" (why does sending the command fail?)

## Root Cause Analysis

### 1. URL/Course Name Mismatch

The playlist URL actually contains **MIT 14.01 Principles of Microeconomics**, not MIT 6.041 Probabilistic Systems.

Playlist contents (first 20 videos):
```
01. 1. Introduction and Supply & Demand
02. 2. Preferences and Utility Functions
03. 3. Budget Constraints and Constrained Choice
04. 4. Demand Curves and Income/Substitution Effects
05. 5. Production Theory
06. 6. Costs
07. 7. Competition I
08. 8. Competition II
09. 9. Supply and Demand & Consumer/Producer Surplus
10. 10. Welfare Economics
11. 11. Monopoly I
12. 12. Monopoly II
13. 13. Oligopoly
14. 14. Oligopoly II
15. 15. Input Markets I—Labor Market
16. 16. Input Markets II—Labor and Capital
17. 17. Making Choices Over Time
18. 18. Increasing Savings & Introduction to Trade
19. 19. International Trade: Welfare and Policy
20. 20. Uncertainty
```

This is clearly a microeconomics course (supply/demand, monopoly, oligopoly, trade), not probability.

### 2. Background Process Interference

The user had previously run the pipeline in background mode. When sending a new command, the agent encountered:
```
⚡ New message detected, interrupting...
[error] ⚡ Sending after interrupt: '<new command>'
```

This happens because the terminal tool cannot handle concurrent foreground commands while a background process holds the session.

### 3. Stale Checkpoint from Previous Run

Directory `flow/MIT_6.041_Probabilistic_Systems/` already existed with one processed file:
- `01-1_ Introduction and Supply _ Demand.md` (176KB, refined)

This suggests a previous run had started but the checkpoint in `01_Permanent/MIT_6.041_Probabilistic_Systems/.checkpoint.json` would show incomplete state if it existed.

## Resolution Steps

1. **Verify playlist content** before starting:
   ```bash
   .venv/bin/yt-dlp --flat-playlist --print "%(playlist_index)s. %(title)s" "<URL>" | head -10
   ```

2. **Clean up incorrect directory**:
   ```bash
   rm -rf flow/MIT_6.041_Probabilistic_Systems/
   rm -rf 01_Permanent/MIT_6.041_Probabilistic_Systems/
   ```

3. **Re-run with correct course name**:
   ```bash
   uv run flow/script/run_pipeline.py \
     "https://www.youtube.com/playlist?list=PLUl4u3cNGP62oJSoqb4Rf-vZMGUBe59G-" \
     "MIT_14.01_Principles_of_Microeconomics" \
     2
   ```

## Recovery: Partially Processed Files

If the pipeline was interrupted mid-run (e.g., video 1 refined but video 2 only has raw subtitles):

1. **Check file status**:
   ```bash
   ls -la flow/<course>/
   wc -l flow/<course>/*.md
   ```
   - Small file (~100-200 lines) = refined
   - Large file (~5000+ lines) = raw subtitles, needs refinement

2. **Use refine_existing.py helper** to refine raw files individually:
   ```bash
   uv run flow/script/refine_existing.py "MIT_14.01_Principles_of_Microeconomics" 2
   ```
   This script:
   - Extracts the raw subtitle/transcription body
   - Calls `refine_markdown()` with content-preserving prompt
   - Saves as `{index}-refined_{title}.md`
   - Preserves original file for safety

3. **Replace original with refined**:
   ```bash
   cd flow/<course>
   mv "02-refined_ Preferences and Utility Functions.md" "02-2_ Preferences and Utility Functions.md"
   ```

4. **Commit the fix**:
   ```bash
   git add -A && git commit -m "Refine video 02 and add refine_existing.py helper"
   ```

## Key Lessons

1. **Always verify URL content matches course name** — don't trust user-provided names blindly
2. **Background processes block new commands** — check `process(action="poll")` before sending new commands to a session
3. **Stale checkpoints cause re-processing** — delete checkpoint when starting fresh after a failed/mismatched run
4. **The error "发送指令他就失败了" often means background interference**, not actual pipeline failure

## Files Involved

- Pipeline entry: `flow/script/run_pipeline.py`
- Pipeline lib: `flow/script/lib/pipeline.py`
- Checkpoint: `01_Permanent/{course}/.checkpoint.json`
- Output dir: `flow/MIT_6.041_Probabilistic_Systems/` (incorrect)
- Correct output dir should be: `flow/MIT_14.01_Principles_of_Microeconomics/`
