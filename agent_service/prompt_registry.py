"""Prompt version registry for Agent Service.

Supports versioned prompts with global flags (e.g., enforce_chinese).
All prompts follow concise instruction-only style to prevent LLM summarization.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class PromptVersion:
    """A single version of a prompt."""
    version: str
    template: str
    description: str = ""


@dataclass
class PromptEntry:
    """A prompt with multiple versions."""
    name: str
    versions: Dict[str, PromptVersion]
    current_version: str = "v1"

    def get(self, **kwargs) -> str:
        pv = self.versions.get(self.current_version)
        if not pv:
            raise KeyError(f"Prompt '{self.name}' version '{self.current_version}' not found")
        try:
            return pv.template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing variable {e} for prompt '{self.name}'")


class PromptRegistry:
    """Global prompt registry with version control and feature flags."""

    def __init__(self):
        self._registry: Dict[str, PromptEntry] = {}
        self._global_flags: Dict[str, bool] = {
            "enforce_chinese": True,
        }
        self._init_defaults()

    def _init_defaults(self):
        # Refine prompt v3 — concise, instruction-only, content-preserving
        self.register(
            "refine",
            PromptEntry(
                name="refine",
                versions={
                    "v1": PromptVersion(
                        "v1",
                        """这是一段音频转录文本，请进行以下优化：
1. 补全标点符号（句号、逗号等）
2. 修正识别错误的术语、人名、地名
3. 去除口语噪音（"嗯"、"啊"、"那个"等填充词）
4. 按语义分段（每段一个主题）
5. Obsidian 格式化（Markdown 标准格式）
请直接输出优化后的文本，不要添加额外说明。

```
{body}
```""",
                        "Basic refine without Chinese enforcement",
                    ),
                    "v2": PromptVersion(
                        "v2",
                        """这是一段音频转录文本，请进行以下优化，输出必须为中文：
1. 补全标点符号（句号、逗号等）
2. 修正识别错误的术语、人名、地名
3. 去除口语噪音（"嗯"、"啊"、"那个"等填充词）
4. 按语义分段（每段一个主题）
5. Obsidian 格式化（Markdown 标准格式）
6. 所有内容翻译成中文，保留专业术语的英文原文（首次出现可标注英文）

请直接输出优化后的中文文本，不要添加额外说明。

```
{body}
```""",
                        "Chinese-enforced refine",
                    ),
                    "v3": PromptVersion(
                        "v3",
                        """这是一段音频转录文本，请进行以下优化，输出必须为中文：
1. 补全标点符号（句号、逗号等）
2. 修正识别错误的术语、人名、地名
3. 去除口语噪音（"嗯"、"啊"、"那个"等填充词）
4. 按语义分段（每段一个主题）
5. Obsidian 格式化（Markdown 标准格式）
6. 所有内容翻译成中文，保留专业术语的英文原文（首次出现可标注英文）

规则：
- 不要提炼总结，不要省略原文内容
- 保持原文的完整信息量
- 仅做格式化和语言转换优化

请直接输出优化后的中文文本，不要添加额外说明。

```
{body}
```""",
                        "Anti-summarization + Chinese enforcement",
                    ),
                },
                current_version="v3",
            ),
        )

        # Syllabus prompt
        self.register(
            "syllabus",
            PromptEntry(
                name="syllabus",
                versions={
                    "v1": PromptVersion(
                        "v1",
                        """基于以下转录文本，生成研究生级别课程大纲，输出必须为中文：

要求：
- 每章包含核心命题（Thesis）
- 标注每章对应的原始视频编号范围
- 体现从基础到高阶的完整逻辑链条
- 不预设章节数量，由内容自然决定
- 所有内容用中文输出，专业术语保留英文原文

格式：
## 第N章：章节名
- **核心命题**：...
- **视频范围**：XX-XX
- **关键概念**：...

{content}""",
                        "Content-driven syllabus generation",
                    ),
                },
                current_version="v1",
            ),
        )

        # Chapter deep dive prompt
        self.register(
            "chapter_deep_dive",
            PromptEntry(
                name="chapter_deep_dive",
                versions={
                    "v1": PromptVersion(
                        "v1",
                        """基于视频{video_range}的内容（{chapter_title}），请深入分析，输出必须为中文：

1. 核心概念与定义（所有关键术语的严格定义）
2. 理论框架与逻辑推导（公式用LaTeX格式）
3. 实务应用与案例分析（真实商业场景）
4. 批判性思考（理论边界、反例、学术争议）
5. 与其他章节的关联（前置知识、后续依赖）

要求：
- 研究生级别的学术深度
- 所有内容用中文输出，专业术语保留英文原文
- 署名：DALONG ZHANG

{transcript}""",
                        "Comprehensive chapter analysis",
                    ),
                },
                current_version="v1",
            ),
        )

        # MOC prompt
        self.register(
            "moc",
            PromptEntry(
                name="moc",
                versions={
                    "v1": PromptVersion(
                        "v1",
                        """所有章节已完成。请生成《{course_name}》知识地图，输出必须为中文：

1. 总结全课核心矛盾与底层逻辑
2. 梳理各章之间的逻辑依赖关系
3. 标注关键公式和定理的交叉引用
4. 给出后续进阶学习路径建议
5. 所有内容用中文输出，专业术语保留英文原文

{chapters}""",
                        "Knowledge map generation",
                    ),
                },
                current_version="v1",
            ),
        )

        # Anki prompt
        self.register(
            "anki",
            PromptEntry(
                name="anki",
                versions={
                    "v1": PromptVersion(
                        "v1",
                        """基于全部课程内容，生成{count}条研究生级别Anki真题卡片，输出必须为中文：

要求：
- 每张覆盖完整推理链条（不是简单概念记忆）
- 正面：问题/情境（包含具体数值或场景）
- 背面：多步骤推导 + 关键公式 + 现实案例引用
- 所有内容用中文输出，专业术语保留英文原文

格式：
---
卡片N
正面：...
背面：...
---

{chapters}""",
                        "Graduate-level Anki card generation",
                    ),
                },
                current_version="v1",
            ),
        )

    def register(self, name: str, entry: PromptEntry) -> None:
        self._registry[name] = entry

    def get(self, name: str, **kwargs) -> str:
        if name not in self._registry:
            raise KeyError(f"Prompt '{name}' not found in registry")
        entry = self._registry[name]
        # Inject global flags into kwargs
        if self._global_flags.get("enforce_chinese", False):
            kwargs.setdefault("enforce_chinese", True)
        return entry.get(**kwargs)

    def set_version(self, name: str, version: str) -> None:
        if name not in self._registry:
            raise KeyError(f"Prompt '{name}' not found")
        if version not in self._registry[name].versions:
            raise KeyError(f"Version '{version}' not found for prompt '{name}'")
        self._registry[name].current_version = version

    def set_global_flag(self, flag: str, value: bool) -> None:
        self._global_flags[flag] = value

    def get_global_flag(self, flag: str, default: bool = False) -> bool:
        return self._global_flags.get(flag, default)

    def list_prompts(self) -> Dict[str, str]:
        return {k: v.current_version for k, v in self._registry.items()}


# Singleton instance
_REGISTRY = None


def get_registry() -> PromptRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = PromptRegistry()
    return _REGISTRY
