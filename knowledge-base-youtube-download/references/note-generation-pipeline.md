# Note Generation Pipeline Reference

Session: 2026-05-15 — Building automated note generation from transcription to Obsidian knowledge base.

## Problem

After transcription produces raw markdown files, manual note-taking is:
- Time-consuming (hours per chapter)
- Inconsistent quality
- Difficult to maintain cross-references
- Hard to generate Anki cards at graduate level

## Solution: NotebookLM-Powered Automated Pipeline

Three-phase automated pipeline that converts raw transcripts into structured knowledge base.

### Phase 1 Prompt (Syllabus Generation)

```
基于全部转录文本，生成研究生级别的课程逻辑大纲：

要求：
1. 根据实际课程内容拆分章节，不预设章数，以知识模块的自然边界为准
2. 每章必须包含核心命题（Thesis）
3. 标注每章对应的原始视频编号范围
4. 体现从基础到高阶的完整逻辑链条
5. 使用学术语言，密度达到研究生水平

输出格式（严格遵循）：

## 第N章：章节标题

- **核心命题**：一句话概括本章核心论点
- **视频范围**：XX-XX
- **前置知识**：[[Ch_XX_...]] | [[Ch_XX_...]]
- **本章概要**：200字以内的学术摘要

---
```

**Key user preference**: Do NOT preset chapter count. Let content determine natural boundaries.

### Phase 2 Prompt (Chapter Deep Dive)

```
基于视频{video_range}的内容，请深入分析本章：

分析维度（按优先级）：
1. **数学推导** — 核心公式的完整推导、边界条件、假设过强之处
2. **风险边界** — 机制在什么条件下失效、什么条件下引发系统性风险
3. **金融逻辑链** — 从微观机制到宏观后果的完整因果链
4. **历史案例对撞** — 理论与具体案例的偏差分析

要求：
- 研究生水平，严禁口语化
- 优先使用LaTeX渲染公式
- 必须包含「逻辑推导」和「跨笔记链接」
- 署名：DALONG ZHANG
```

### Pressure Test Round Prompts

**Round 1 — 定义与分类**:
```
基于视频{video_range}的内容，请回答：
1) [{concept_a}]的数学定义是什么？
2) [{concept_b}]与[{concept_c}]的根本区别？
3) 给出[{concept_a}]的严格数学表达（LaTeX）
4) 该定义的边界条件是什么？
要求：研究生水平，LaTeX公式，署名DALONG ZHANG。
```

**Round 2 — 数学推导**:
```
基于视频{video_range}的内容，请完成：
1) [{theorem}]的完整数学推导
2) 每一步的假设条件
3) 假设过强之处的批判性分析
4) 推导中的潜在漏洞
要求：研究生水平，LaTeX公式，署名DALONG ZHANG。
```

**Round 3 — 案例对撞**:
```
基于视频{video_range}的内容，请分析：
1) 用具体案例说明[{mechanism}]如何在现实中体现？
2) 该案例与理论预测的偏差
3) 偏差产生的原因（制度/行为/信息因素）
4) 对理论框架的修正建议
要求：研究生水平，引用真实历史案例，署名DALONG ZHANG。
```

**Round 4 — 学术批判**:
```
基于视频{video_range}的内容，请批判：
1) 为什么[{mechanism}]会导致系统性风险？
2) 风险传导的完整链条
3) 历史上类似的危机事件
4) 监管框架的缺陷与改进方向
要求：研究生水平，引用历史案例，署名DALONG ZHANG。
```

**Round 5 — 跨章关联**:
```
基于视频{video_range}及已学内容，请关联：
1) 本章内容与[[Ch_XX_...]]的内在逻辑联系
2) 不同章节方法论的比较
3) 知识网络中的关键节点
4) 后续深入研究的方向
要求：研究生水平，跨章节链接，署名DALONG ZHANG。
```

### Phase 3 Prompts

**MOC Generation**:
```
所有章节已完成。请生成《{course_name}》知识地图：

要求：
1. 总结全课核心矛盾与底层逻辑
2. 梳理各章之间的逻辑依赖关系（用箭头图或表格）
3. 标注关键公式和定理的交叉引用
4. 给出从基础到高阶的学习路径建议
5. 署名：DALONG ZHANG

输出格式：
- 使用Obsidian [[wikilink]]语法链接各章节
- LaTeX公式优先
- 研究生水平学术语言
```

**Anki Cards**:
```
从全课笔记中提取{card_count}条高难度真题级Anki卡片：

要求：
- 正面：问题/情境（具体、有深度）
- 背面：多步骤推导 + 公式 + 案例引用
- 避免简单概念记忆，每张覆盖一个完整推理链条
- 难度达到研究生入学考试或CFA三级水平
- 署名：DALONG ZHANG
```

## Output File Naming Convention

| Type | Format | Example |
|------|--------|---------|
| Transcription | `NN-Title.md` | `01-Introduction.md` |
| Chapter Note | `Ch_XX_章节名.md` | `Ch_01_估值哲学.md` |
| Syllabus | `{course}_课程大纲.md` | `Valuation_课程大纲.md` |
| MOC | `{course}_知识地图_MOC.md` | `Valuation_知识地图_MOC.md` |
| Anki | `Anki_{course}_N张真题卡.md` | `Anki_Valuation_20张真题卡.md` |

## NotebookLM CLI Response Formats

### `list --json`
Returns dict-wrapped format:
```json
{
  "notebooks": [
    {"index": 1, "id": "...", "title": "...", "is_owner": true, "created_at": "..."}
  ],
  "count": 8
}
```

NOT a raw list. Parser must handle both formats for forward compatibility.

### `source list --json`
Returns list of source objects:
```json
[
  {"name": "01-Intro.md", "status": "ready", "type": "document"}
]
```

Status values: `ready`, `processing`, `error`.

### `ask`
Returns plain text with conversation context header:
```
Continuing conversation abc123...
Answer:
[response text]
```

Can take 60-180s for complex analytical questions.

## Resume State Machine

The pipeline auto-detects phase from filesystem state:

```
01_Permanent/{course}/
├── {course}_课程大纲.md     → Phase 1 complete
├── Ch_01_*.md               → Phase 2 in progress
├── Ch_NN_*.md               → Phase 2 complete
├── {course}_知识地图_MOC.md  → Phase 3 complete
└── Anki_{course}_*.md       → All complete
```

To resume: `--phase N --notebook-id "xxx"`

## Testing

Unit tests for note generation (14 tests):
```bash
cd ~/Documents/all-in-one/flow/script_py
uv run python tests/test_syllabus_parser.py
uv run python tests/test_note_paths.py
uv run python tests/test_course_loader.py
```

Integration test (dry-run):
```bash
uv run flow/script_py/note_pipeline.py --course "TestCourse" --dry-run
```
