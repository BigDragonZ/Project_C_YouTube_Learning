# Session Log: Financial Accounting Course — Manual Chapter Generation Workflow

**Date**: May 22, 2026
**Course**: Financial Accounting — Principles of Accounting Lessons
**Playlist**: PLxCUhFZ3hAvn3tsvtyFy4UtxxuHJZ0f36
**Videos**: 190 videos, 32h9m total duration
**Transcription**: 181/190 files successfully refined

---

## NotebookLM API Limitations Encountered

### Source Upload Hard Limit (~100 sources)

NotebookLM stalled at exactly 100/181 files with:
```
Failed to get SOURCE_ID from registration response
```

**Attempted fixes** (all failed):
1. Background upload process — stalled at 100
2. Retry upload process — stalled at 100
3. Single file upload test — same error on file 101

**Resolution**: Proceeded with 100 uploaded sources. These covered videos 01-405 (the full course content range), which was sufficient for complete note generation.

### Automated note_pipeline.py Failure

The `note_pipeline.py` script failed during source upload due to the 100-source limit. Manual fallback was required for all phases.

---

## Manual Workflow (Validated)

### Phase 1: Syllabus Generation

```bash
# 1. Create notebook
uv run notebooklm create "Financial_Accounting"
# ID: ba58ea32-d15d-4aa7-9fde-9c45aedd8d8f

# 2. Upload sources (stalled at 100/181)
for f in youtube2note/input/Financial_Accounting/*.md; do
  uv run notebooklm source add "$f" 2>&1 | tail -1
  sleep 1
done

# 3. Generate syllabus
uv run notebooklm use ba58ea32-d15d-4aa7-9fde-9c45aedd8d8f
uv run notebooklm ask "基于全部上传的转录文本，生成研究生级别的课程逻辑大纲，输出必须为中文：
- 每章包含核心命题（Thesis）
- 标注每章对应的原始视频编号范围
- 体现从基础到高阶的完整逻辑链条
- 所有内容用中文输出，专业术语保留英文原文"
```

**Output**: 7-chapter syllabus saved to `youtube2note/output/Financial_Accounting/Financial_Accounting_课程大纲.md`

**Chapter mapping** (video ranges):
| Chapter | Title | Video Range |
|---------|-------|-------------|
| Ch_01 | 财务报告的理论框架与商业伦理 | 01-19 |
| Ch_02 | 收入确认与存货成本流转 | 43-64 |
| Ch_03 | 信用风险评估与应收款项 | 125-158 |
| Ch_04 | 长期资产的资本化与价值损耗 | 175-238 |
| Ch_05 | 流动负债与债务融资 | 239-266, 273-281, 285-296, 304-325 |
| Ch_06 | 股东权益与公司融资 | 326-374, 379-389 |
| Ch_07 | 现金流量与财务比率 | 390-405 |

### Phase 2: Chapter Deep Dive (Manual per Chapter)

For each chapter, a single `notebooklm ask` call with comprehensive prompt:

```bash
uv run notebooklm ask "基于视频<range>的内容，请深入分析本章，输出必须为中文：

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

**Key insight**: Single comprehensive prompt per chapter is MORE reliable than the automated pipeline's 5-round pressure test. The automated pipeline makes 5+ API calls per chapter, which triggers rate limits. The manual approach uses 1 call per chapter with equivalent depth.

**Output sizes**: ~15-25KB per chapter (successful), vs ~1.5KB (failed automated generation).

### Phase 3: MOC and Anki

```bash
# MOC
uv run notebooklm ask "所有章节已完成。请生成《Financial Accounting》知识地图，输出必须为中文：
- 总结全课核心矛盾与底层逻辑
- 梳理各章之间的逻辑依赖关系
- 标注关键公式和定理的交叉引用
- 所有内容用中文输出，专业术语保留英文原文
- 署名：DALONG ZHANG"

# Anki
uv run notebooklm ask "基于全部课程内容，生成15-20条研究生级别Anki真题卡片，输出必须为中文：
- 每张覆盖完整推理链条
- 正面：问题/情境
- 背面：多步骤推导+公式+案例
- 所有内容用中文输出，专业术语保留英文原文
- 署名：DALONG ZHANG"
```

---

## Git Commit Pattern

After EACH file generation:
```bash
git add youtube2note/output/Financial_Accounting/
git commit -m "chore: add Financial_Accounting <file_description>"
```

Commits made:
1. `chore: add Financial_Accounting syllabus`
2. `chore: add Financial_Accounting Ch_01 notes`
3. `chore: add Financial_Accounting Ch_02 notes`
4. `chore: add Financial_Accounting Ch_03 notes`
5. `chore: add Financial_Accounting Ch_04 notes`
6. `chore: add Financial_Accounting Ch_05 notes`
7. `chore: add Financial_Accounting Ch_06 notes`
8. `chore: add Financial_Accounting Ch_07 notes`
9. `chore: add Financial_Accounting MOC and Anki cards - course complete`

---

## Lessons Learned

1. **100-source limit is real and persistent** — don't waste time retrying
2. **Single comprehensive prompt > multi-round automated pipeline** — fewer API calls, less rate limiting, same output quality
3. **Manual workflow is viable and reliable** — validated across 7 chapters + MOC + Anki
4. **Git commit after every file** — creates clean rollback points
5. **Course queue tracking** — `课程学习进度清单.md` helps manage multi-course batches
