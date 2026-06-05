# Content Refinement via Gemini

## Purpose

Academic-grade text refinement for knowledge base articles transcribed from video/audio. Converts raw transcription into structured, polished Markdown with proper terminology, LaTeX math, and semantic formatting.

## Prompt Template (Concise — Preferred)

**CRITICAL**: The refinement prompt must preserve ALL original content. Do NOT summarize, condense, or rephrase. The goal is cleanup — NOT content reduction.

User explicitly corrected verbose prompts: "直接告诉他，这是一段音频文本，请补全标点、修正术语、去除噪音、语意分段、Obsidian格式化，这就行了。"

**Final working prompt** (concise, no persona framing):

```
这是一段音频转录文本，请进行以下优化：

1. 补全标点符号（句号、逗号等）
2. 修正识别错误的术语、人名、地名
3. 去除口语噪音（"嗯"、"啊"、"那个"等填充词）
4. 按语义分段（每段一个主题）
5. Obsidian 格式化（Markdown 标准格式）

请直接输出优化后的文本，不要添加额外说明。
```

### Why Concise Prompts Work Better

- **Verbose prompts** (7 sections with examples) cause LLM to over-interpret → summarization, condensation, 98% content loss
- **Concise prompts** (5 bullet points) give LLM clear boundaries → cleanup only, full content preservation
- **No persona framing** ("你是一位专业的...") — persona triggers academic rewriting behavior
- **No explicit prohibitions** needed — short prompts naturally stay within scope

### Prompt Evolution

| Version | Prompt Style | Result | Content Retention |
|---------|-------------|--------|-------------------|
| v1 | "学术编辑精修" | Summarized heavily | ~2% |
| v2 | "课程笔记优化 + 6禁止条款" | Better but still condensed | ~12% |
| v3 | **"音频转录文本，5点优化"** | Cleanup only, full preservation | ~88% |

**Lesson**: For content-preserving tasks, use the shortest prompt that specifies the transformation. Every extra instruction increases the chance of unwanted behavior.

## LaTeX Math Examples

| Concept | LaTeX | Rendered |
|---------|-------|----------|
| DCF formula | `$\\text{Value} = \\sum_{t=1}^{n} \\frac{CF_t}{(1+r)^t}$` | Value = Σ CFₜ/(1+r)ᵗ |
| CAPM | `$E[R] = R_f + \\beta(E[R_m] - R_f)$` | E[R] = Rƒ + β(E[Rₘ] - Rƒ) |
| Beta | `$\\beta_i = \\frac{\\text{Cov}(R_i, R_m)}{\\text{Var}(R_m)}$` | βᵢ = Cov(Rᵢ,Rₘ)/Var(Rₘ) |
| WACC | `$\\text{WACC} = \\frac{E}{V} r_e + \\frac{D}{V} r_d (1-T_c)$` | WACC = E/V·rₑ + D/V·rᵈ(1-Tᶜ) |

## Model Availability (as of 2026-05)

| Model | Vertex AI (api_key) | Vertex AI (project+location) | Gemini Standard API |
|-------|---------------------|------------------------------|---------------------|
| gemini-2.5-flash-lite | ✅ | ✅ | ✅ |
| gemini-2.5-pro | ✅ | ❌ 404 | ❓ |
| gemini-3.1-pro-preview | ✅ | ❌ 404 | ❌ 403 (key blocked) |

**Key finding**: `api_key` parameter is REQUIRED for Vertex AI to access newer models like gemini-3.1-pro-preview. Using `project`+`location` without `api_key` results in 404.

## Implementation

Uses unified `lib/gemini_client.py` with fault-tolerant backend chain.

```python
def refine_markdown(content: str) -> str:
    """
    Refine markdown content using Gemini.
    Fault-tolerant: Vertex AI -> Gemini fallback.
    """
    from google.genai.types import GenerateContentConfig
    from lib.gemini_client import generate_content
    
    REFINE_PROMPT = """这是一段音频转录文本，请进行以下优化：

1. 补全标点符号（句号、逗号等）
2. 修正识别错误的术语、人名、地名
3. 去除口语噪音（"嗯"、"啊"、"那个"等填充词）
4. 按语义分段（每段一个主题）
5. Obsidian 格式化（Markdown 标准格式）

请直接输出优化后的文本，不要添加额外说明。"""
    
    text = generate_content(
        contents=REFINE_PROMPT + content,
        config=GenerateContentConfig(temperature=0.2, max_output_tokens=8192, top_p=0.95),
    )
    return text
```

See `lib/refine.py` for full implementation.

## Usage

```bash
cd ~/Documents/all-in-one
PYTHONPATH=flow/script_py python3 flow/script_py/refine_markdown.py \
  "flow/Course/01-Transcription Course.md" \
  "flow/Course/01-Refined.md"
```

## Output Structure

```markdown
# Transcription

## 元信息

- **序号**: 1
- **课程**: Course_Name
- **模型**: gemini-2.5-pro
- **处理时间**: 2026-05-15

---

## 精修内容

... (polished text with LaTeX and bolded terms)
```
