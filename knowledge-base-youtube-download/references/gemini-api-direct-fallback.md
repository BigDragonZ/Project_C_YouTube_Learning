# Gemini API Direct Fallback Workflow

## When to Use

Use this when NotebookLM source upload is completely broken (0 sources uploaded) or when you need to process >100 sources and splitting across notebooks is not viable.

**Validated**: Managerial Accounting course (45 videos, May 2026) — NotebookLM `source add` returned `Failed to get SOURCE_ID from registration response` for ALL files. Gemini API direct fallback produced complete 8-chapter notes + MOC + Anki.

## Prerequisites

- `google-genai` package installed in project `.venv`
- `GOOGLE_API_KEY` environment variable set (or gcloud ADC configured)
- Correct initialization: `Client(vertexai=True, api_key=..., http_options=HttpOptions(api_version="v1"))`

## Workflow

### Step 1: Verify Gemini API Access

```bash
cd ~/Documents/all-in-one
uv run python -c "
from google.genai import Client
from google.genai.types import HttpOptions
import os

client = Client(
    vertexai=True,
    api_key=os.environ.get('GOOGLE_API_KEY', ''),
    http_options=HttpOptions(api_version='v1')
)
response = client.models.generate_content(
    model='gemini-2.5-pro',
    contents='What is managerial accounting? Keep under 50 words.'
)
print(response.text)
"
```

Expected: A coherent response about managerial accounting.

### Step 2: Generate Syllabus from Video Titles

When transcripts are available but NotebookLM upload fails, generate the syllabus directly from video titles and content summaries:

```python
#!/usr/bin/env python3
import os
import glob

# Read all transcript files
files = sorted(glob.glob('youtube2note/input/CourseName/*.md'))
video_summaries = []
for f in files:
    with open(f, 'r') as file:
        content = file.read()
    basename = os.path.basename(f)
    title_line = content.split('\n')[0] if content else basename
    video_summaries.append(f"{basename}: {title_line[:120]}")

# Build prompt
video_list = '\n'.join(video_summaries)
prompt = f"""基于以下课程视频列表，生成一份研究生级别的课程大纲。

课程视频列表：
{video_list}

要求：
1. 将视频组织成6-8个逻辑章节
2. 每章包含：核心命题（Thesis）、视频编号范围、关键概念
3. 体现从基础到高阶的完整逻辑链条
4. 使用中文输出，专业术语保留英文
5. 格式：## 第X章：章节名

请生成完整的课程大纲。"""

# Call Gemini API
from google.genai import Client
from google.genai.types import HttpOptions

client = Client(
    vertexai=True,
    api_key=os.environ.get('GOOGLE_API_KEY', ''),
    http_options=HttpOptions(api_version='v1')
)

response = client.models.generate_content(
    model='gemini-2.5-pro',
    contents=prompt
)

# Save syllabus
output_dir = 'youtube2note/output/CourseName'
os.makedirs(output_dir, exist_ok=True)
with open(f'{output_dir}/CourseName_课程大纲.md', 'w') as f:
    f.write(response.text)
```

### Step 3: Generate Chapter Notes

For each chapter, read the relevant transcript files and call Gemini API:

```python
#!/usr/bin/env python3
import os
from google.genai import Client
from google.genai.types import HttpOptions

client = Client(
    vertexai=True,
    api_key=os.environ.get('GOOGLE_API_KEY', ''),
    http_options=HttpOptions(api_version='v1')
)

base_dir = 'youtube2note/input/CourseName'
output_dir = 'youtube2note/output/CourseName'

chapters = [
    {
        'num': 1,
        'title': '管理会计基础与成本分类体系',
        'files': ['01-MA1 _ Managerial Accounting Basics for Beginners.md', ...]
    },
    # ... more chapters
]

def generate_chapter(ch):
    content = ""
    for fname in ch['files']:
        fpath = os.path.join(base_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, 'r') as f:
                content += f"\n\n=== {fname} ===\n\n"
                content += f.read()[:8000]
    
    prompt = f"""基于以下管理会计课程第{ch['num']}章（{ch['title']}）的转录文本，生成研究生级别的学术笔记。

要求：
1. 核心概念的严格数学定义（使用LaTeX公式）
2. 关键公式的完整推导过程
3. 学术批判：理论边界条件、局限性
4. 跨章节链接提示
5. 使用中文，专业术语保留英文
6. 格式：Markdown，包含元信息头部

转录内容：
{content[:15000]}

请生成完整的第{ch['num']}章笔记。"""
    
    response = client.models.generate_content(
        model='gemini-2.5-pro',
        contents=prompt
    )
    
    output_path = os.path.join(output_dir, f"Ch_{ch['num']:02d}_{ch['title']}.md")
    with open(output_path, 'w') as f:
        f.write(response.text)
    
    return output_path

for ch in chapters:
    generate_chapter(ch)
```

### Step 4: Generate MOC and Anki

```python
# Read all chapter notes
all_chapters = ""
for i in range(1, 9):
    for f in os.listdir(output_dir):
        if f.startswith(f'Ch_{i:02d}_'):
            with open(os.path.join(output_dir, f), 'r') as file:
                all_chapters += f"\n\n=== Chapter {i} ===\n\n"
                all_chapters += file.read()[:5000]

# Generate MOC
moc_prompt = f"""基于以下课程8章的笔记内容，生成一份知识地图 (MOC)。

要求：
1. 总结全课核心矛盾与底层逻辑
2. 梳理各章之间的逻辑依赖关系
3. 标注关键公式和定理的交叉引用
4. 给出后续进阶学习路径建议
5. 使用中文，专业术语保留英文

章节内容摘要：
{all_chapters[:20000]}

请生成知识地图。"""

moc_response = client.models.generate_content(
    model='gemini-2.5-pro',
    contents=moc_prompt
)

with open(f'{output_dir}/CourseName_知识地图_MOC.md', 'w') as f:
    f.write(moc_response.text)

# Generate Anki
anki_prompt = """基于管理会计课程全部8章内容，生成15条研究生级别Anki真题卡片。

课程章节：
1. 管理会计基础与成本分类体系
2. 财务报表分析与比率解读
3. 产品成本核算与成本流转
4. 分批成本法与分步成本法
5. 作业成本法与成本估计
6. 本量利分析与成本核算方法比较
7. 预算编制与标准成本控制
8. 资本预算与短期经营决策

要求：
1. 每张覆盖完整推理链条
2. 正面：问题/情境（包含具体数值或场景）
3. 背面：多步骤推导 + 关键公式 + 现实案例引用
4. 使用中文，专业术语保留英文

请生成Anki卡片。"""

anki_response = client.models.generate_content(
    model='gemini-2.5-pro',
    contents=anki_prompt
)

with open(f'{output_dir}/Anki_CourseName_15张真题卡.md', 'w') as f:
    f.write(anki_response.text)
```

## Key Differences from NotebookLM Workflow

| Aspect | NotebookLM | Gemini API Direct |
|--------|-----------|-------------------|
| Upload | Required (100 source limit) | Not required |
| Interaction | Conversational (ask → answer) | One-shot prompt → response |
| Context | Maintains conversation history | Each call is independent |
| Chapter depth | 5+ rounds per chapter | Single comprehensive prompt |
| Rate limits | NotebookLM-specific | Gemini API quotas |
| Best for | Stable upload, <100 sources | Upload broken, >100 sources |

## Time Estimates

For a 45-video course (Managerial Accounting):
- Syllabus generation: ~30s
- 8 chapters: ~8-10 minutes (1-2 min per chapter)
- MOC: ~30s
- Anki: ~30s
- **Total: ~12 minutes** of API time

## Lessons Learned

1. **Gemini API is more reliable than NotebookLM CLI for bulk operations**. When NotebookLM upload fails consistently, Gemini direct fallback is the fastest recovery path.

2. **Single comprehensive prompt per chapter is sufficient**. Unlike NotebookLM's 5-round pressure test, a single well-structured prompt produces comparable output quality.

3. **Content size matters**. Limit transcript content to ~15K chars per API call to avoid timeouts. For large chapters, split across multiple calls.

4. **Always verify API access first**. Run a simple test query before starting batch generation to confirm credentials and connectivity.

5. **Git commit after each phase**. Syllabus → commit → chapters → commit → MOC/Anki → commit. This matches the user's expectation of incremental commits.

6. **Add `time.sleep(2)` between API calls**. When generating multiple chapters back-to-back, Gemini API may return `RemoteProtocolError: Server disconnected without sending a response`. Adding a 2-second delay between calls prevents this.

7. **If Anki generation fails with RemoteProtocolError**, wait 10-30 seconds and retry with a shorter prompt. If still failing, create Anki cards manually from the syllabus and chapter titles.

8. **The "OK" message from NotebookLM CLI is misleading**. When `Failed to get SOURCE_ID from registration response` appears before "OK", the file was NOT uploaded. Always verify with `source list`.
