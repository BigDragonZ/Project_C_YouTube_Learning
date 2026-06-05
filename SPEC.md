# YouTube Learning Agent Service — 设计规范

## 1. 项目定位

为 Hermes / Kimi-Word 等 Agent 提供可后台调用的 YouTube 课程转录与学习服务。解决当前手动处理异常、缺乏状态追踪、NotebookLM 不稳定等痛点。

---

## 2. 核心目标

| 目标 | 当前状态 | 期望状态 |
|------|---------|---------|
| Agent 调用 | 手动执行脚本 | CLI 提交任务，返回 task_id |
| 后台执行 | terminal(background=True) | Daemon 引擎自动消费队列 |
| 状态查询 | ls 文件数推测 | `status <task_id>` 结构化返回 |
| NotebookLM 故障 | 人工识别 + 写临时脚本 | 记录错误 + 提供重试脚本，不自动降级 |
| 质量检查 | 人工抽查文件大小 | 自动门禁（大小/语言/完整性） |
| 批量任务 | 逐个手动启动 | 批量提交 + 顺序执行 |

---

## 3. 架构设计

```
Project_C_YouTube_Learning/
├── SPEC.md                          # 本文档
├── input/                           # 转录精修输出 (01_Transcripts)
├── output/                          # NotebookLM 学习产出 (02_NotebookLM)
├── anki/                            # Anki 卡片产出 (03_Anki)
├── notes/                           # 学习笔记 (04_Notes)
├── logs/                            # 任务日志
├── agent_service/                   # Agent 服务层
│   ├── __init__.py
│   ├── cli.py                       # Agent 统一入口
│   ├── task_queue.py                # JSON 任务队列
│   ├── executor.py                  # 后台执行引擎
│   ├── logger.py                    # 结构化日志
│   ├── quality_gate.py              # 质量门禁
│   ├── retry_manager.py             # 错误重试与重试脚本生成
│   ├── prompt_registry.py           # Prompt 版本控制
│   ├── api_server.py                # HTTP API（可选）
│   └── tools/                       # 工具类封装（可复用）
│       ├── __init__.py
│       ├── youtube_tool.py          # YouTube 下载/字幕提取
│       ├── notebooklm_tool.py       # NotebookLM CLI 封装
│       └── gemini_tool.py           # Gemini API 封装
├── knowledge-base-youtube-download/ # 现有：转录 skill
└── youtube-course-pipeline/         # 现有：学习 skill
```

---

## 4. 配置中心化管理（config.json）

所有路径、API 参数、阈值集中配置，避免各模块硬编码。

### 4.1 配置文件结构

```json
{
  "paths": {
    "input": "./input",
    "output": "./output",
    "anki": "./anki",
    "notes": "./notes",
    "logs": "./logs"
  },
  "api": {
    "gemini_model": "gemini-2.5-pro",
    "gemini_fallback_model": "gemini-2.5-flash-lite",
    "notebooklm_timeout": 180,
    "yt_dlp_path": ".venv/bin/yt-dlp"
  },
  "quality": {
    "min_retention_ratio": 0.70,
    "min_chinese_ratio": 0.80,
    "min_chapter_size_kb": 10
  },
  "retry": {
    "max_retries": 3,
    "sleep_jitter": [0, 2]
  },
  "timeout": {
    "transcribe": 14400,
    "study": 7200,
    "anki": 1800
  },
  "daemon": {
    "poll_interval": 5,
    "lock_file": "./logs/.daemon.lock"
  }
}
```

### 4.2 配置加载优先级

1. `config.json`（项目级，版本控制）
2. `config_local.json`（用户级，gitignore，覆盖项目级）
3. 环境变量（覆盖配置文件）

---

## 5. 数据模型

### 4.1 Task（任务）

```python
@dataclass
class Task:
    task_id: str           # 格式: yl-{YYMMDD}-{NNN}
    playlist_url: str
    course_name: str
    task_type: TaskType    # enum: transcribe | study | anki
    priority: int          # 1=high, 2=normal, 3=low
    status: TaskStatus     # enum: pending → validating → running → quality_check → completed / failed / retrying
    progress_pct: int      # 0-100
    current_phase: str     # transcribe | study | anki | fallback
    error_msg: str | None
    log_file: Path
    created_at: datetime
    updated_at: datetime
    video_count: int | None
    video_completed: int
    quality_score: int | None  # 0-100
```

### 4.2 TaskType（任务类型）

| 类型 | 说明 | 输入 | 输出 |
|------|------|------|------|
| `transcribe` | 只执行转录精修 | playlist_url | `input/{course}/` |
| `study` | 只执行 NotebookLM 学习 | `input/{course}/` | `output/{course}/` |
| `anki` | 只生成 Anki 卡片 | `output/{course}/` | `anki/{course}/` |

**说明**：任务可按需指定单一阶段，避免不必要的完整流程执行。例如已有转录文本时，可直接提交 `study` 任务。

### 4.2 TaskStatus 状态机

```
pending → validating → transcribing → studying → quality_check → completed
   ↓         ↓            ↓              ↓             ↓
 failed ← retrying（最多3次）
```

---

## 5. Agent 调用接口（CLI）

### 5.1 提交任务

```bash
# 完整流程（默认）
python cli.py submit "<playlist_url>" --name "CourseName" --type transcribe --priority high

# 只执行 NotebookLM 学习（需已有转录文本）
python cli.py submit "" --name "CourseName" --type study --priority high

# 只生成 Anki 卡片（需已有学习产出）
python cli.py submit "" --name "CourseName" --type anki --priority high
```

**返回**（JSON）：
```json
{
  "task_id": "yl-260604-001",
  "status": "pending",
  "task_type": "transcribe",
  "log_file": "logs/yl-260604-001/main.log",
  "position_in_queue": 1
}
```

### 5.2 批量提交

```bash
python cli.py batch --file playlists.txt
# playlists.txt 格式：每行一个 URL，可选空格后接课程名
```

### 5.3 查询状态

```bash
python cli.py status <task_id>
```

**返回**（人类可读）：
```
任务: yl-260604-001 (MIT微观经济学)
状态: running
阶段: study (Phase 2: 章节深挖)
进度: 3/8 章 (37.5%)
当前动作: 生成第4章笔记 (Gemini Direct 模式)
质量评分: 92/100
最近日志: [10:06:00] WARN: NotebookLM上传失败，已自动降级
```

### 5.4 查看日志

```bash
python cli.py logs <task_id> --tail 50 --phase transcribe
```

### 5.5 任务列表

```bash
python cli.py list --status running --limit 10
```

### 5.6 重试失败任务

```bash
# 重试单个失败任务
python cli.py retry yl-001

# 批量重试所有 NotebookLM 失败的任务
python cli.py retry --filter-error notebooklm --batch-size 1

# 强制重试（忽略重试次数限制）
python cli.py retry yl-001 --force
```

### 5.7 后台引擎控制

```bash
python cli.py daemon start --workers 1 --log-level info
python cli.py daemon stop
python cli.py daemon status
```

---

## 6. 执行引擎（Executor）

### 6.1 执行流程（按任务类型）

```
消费任务（单 worker 串行）
    ↓
transcribe 任务:
  - 调用 run_pipeline.py
  - 每 video 完成后更新进度
  - 转录质量检查（quality_gate）
  - 输出到 input/{course}/
    ↓
study 任务:
  - 调用 note_pipeline.py（三阶段：大纲→章节→MOC）
  - NotebookLM 失败 → 记录错误到 error log，标记任务 failed
  - 提供 `retry_task.py` 脚本供后续手动/自动重试
  - 学习产出质量检查（含中文字符占比检查）
  - 输出到 output/{course}/
    ↓
anki 任务:
  - 读取 output/{course}/ 章节笔记
  - 调用 Anki 生成（NotebookLM 或 Gemini Direct）
  - 输出到 anki/{course}/
    ↓
标记 completed / failed
```

### 6.2 断点续传规则

1. 优先读取 `.checkpoint.json`
2. checkpoint 与文件系统不一致时，以文件系统为准（删除 stale checkpoint）
3. 自动检测当前阶段：
   - 无 syllabus → Phase 1
   - 有 syllabus 无 chapters → Phase 2
   - 有 chapters 无 MOC → Phase 3
   - 全部存在 → completed

### 6.3 错误重试策略

| 错误类型 | 重试次数 | 退避策略 | 最终动作 |
|---------|---------|---------|---------|
| Gemini API 429 | 3 | random(2,4)s → random(4,8)s → random(8,16)s | 标记 failed |
| NotebookLM RPC / timeout | 3 | random(5,10)s → random(10,20)s → random(20,40)s | 记录错误，标记 failed |
| NotebookLM 0 sources | 1 | 立即 | 记录错误，标记 failed |
| yt-dlp 403 | 2 | random(10,20)s → random(30,60)s | 标记 failed |
| 质量检查失败（含英文输出） | 2 | 立即重跑 | 标记 needs_review |

**Sleep Jitter 规则**：所有 API 调用间隔使用随机偏移，避免固定间隔被限流：
```python
import random
time.sleep(base_delay + random.uniform(0, 2))  # base_delay ± 2s 随机偏移
```

### 6.4 孤儿任务恢复（Orphan Task Recovery）

daemon 崩溃或进程被 kill 时，正在执行的任务状态停留在 `running`，重启后会永久挂死。

**启动时自动扫描**：
```python
def recover_orphan_tasks():
    """将状态为 running 但 updated_at > timeout * 2 的任务标记为 failed。"""
```

**触发条件**：
- daemon 启动时自动执行
- 扫描所有 `status == running` 的任务
- 如果 `updated_at` 超过该任务类型超时时间的 2 倍，标记为 `failed`，error_msg = "Orphan task: daemon crashed"

### 6.5 任务执行超时控制

| 任务类型 | 超时时间 | 超时后动作 |
|---------|---------|-----------|
| transcribe | 4 小时 | SIGTERM，标记 failed |
| study | 2 小时 | SIGTERM，标记 failed |
| anki | 30 分钟 | SIGTERM，标记 failed |

**实现**：使用 `threading.Timer` 或 `signal.alarm`，超时前发送 SIGTERM，保留已处理进度。

### 6.6 幂等性保证

**转录阶段**：执行前扫描 `input/{course}/`，跳过已精修的视频：
```python
def skip_existing_transcripts(course: str, total_videos: list) -> list:
    existing = set(Path(f"input/{course}").glob("*.md"))
    return [v for v in total_videos if v.expected_filename not in existing]
```

**学习阶段**：执行前扫描 `output/{course}/`，skip 已生成的章节文件。

### 6.7 文件锁防止多实例

daemon 启动时获取文件锁，防止用户意外启动多个实例：
```python
LOCK_FILE = PROJECT_ROOT / "logs" / ".daemon.lock"

def acquire_lock() -> bool:
    """尝试获取文件锁，失败返回 False（已有实例在运行）。"""
```

---

## 7. 输入验证与 Sanitization

### 7.1 URL 验证

```python
def validate_playlist_url(url: str) -> bool:
    """验证是否为 YouTube 播放列表 URL。"""
    return url.startswith(("https://www.youtube.com/playlist", 
                         "https://youtube.com/playlist",
                         "https://youtu.be/"))
```

### 7.2 Course Name Sanitization

```python
def sanitize_course_name(name: str) -> str:
    """只允许字母、数字、下划线、连字符、中文。"""
    return re.sub(r'[^\w\s\-一-鿿]', '_', name).strip()
```

---

## 8. 质量门禁（Quality Gate）

### 7.1 转录阶段检查

| 检查项 | 阈值 | 失败动作 |
|--------|------|---------|
| 精修后文件大小 / 原始大小 | ≥ 70% | retry with stricter prompt |
| 中文字符占比 | ≥ 80% | retry with "输出必须为中文" |
| 偶发性英文输出检查 | 英文段落占比 ≤ 20% | retry with explicit Chinese enforcement |
| 包含 "精修内容" 标记 | 是 | retry |
| 文件非空 | 行数 ≥ 10 | retry |

### 7.2 学习阶段检查

| 检查项 | 阈值 | 失败动作 |
|--------|------|---------|
| 章节文件大小 | ≥ 10 KB | retry with Gemini Direct |
| 大纲解析章节数 | ≥ 3 | retry with parser fix |
| MOC 文件存在 | 是 | manual create from chapters |
| Anki 文件存在 | 是 | manual create from chapters |

### 7.3 质量评分公式

```
quality_score = (
    转录保留率 * 30 +
    中文占比 * 20 +
    章节完整性 * 30 +
    MOC/Anki 完整性 * 20
)
```

---

## 8. 错误处理与重试机制

### 8.1 NotebookLM 失败处理（不降级）

**原则**：NotebookLM 失败时不自动降级到 Gemini Direct，而是记录错误并标记任务 failed，由用户决策是否重试。

**错误记录**：
```json
{
  "task_id": "yl-001",
  "phase": "study",
  "error_type": "notebooklm_source_upload_failed",
  "error_msg": "Failed to get SOURCE_ID from registration response",
  "notebook_id": "xxx",
  "sources_uploaded": 0,
  "timestamp": "2026-06-05T10:00:00"
}
```

**重试脚本**：
```bash
# 重试单个失败任务
python cli.py retry yl-001 --force

# 批量重试所有 NotebookLM 失败的任务
python cli.py retry --filter-error notebooklm --batch-size 1
```

### 8.2 100-Source 限制处理

NotebookLM 硬性限制 100 sources。处理方式：
- 记录警告日志，继续处理已上传的 100 个 source
- 不创建 Part 2（避免复杂性）
- 在任务报告中注明："仅处理了前 100 个视频"

---

## 9. 工具类封装（tools/）

从现有 skill 代码中提取可复用组件，封装为独立工具类。

### 9.1 YouTubeTool（`tools/youtube_tool.py`）

```python
class YouTubeTool:
    """封装 yt-dlp 调用，支持字幕下载、播放列表解析、视频信息获取。"""
    
    def __init__(self, yt_dlp_path: str = ".venv/bin/yt-dlp"):
        self.yt_dlp_path = yt_dlp_path
    
    def get_playlist_info(self, url: str) -> dict:
        """获取播放列表信息（标题、视频数、时长）。"""
    
    def download_subtitles(self, url: str, output_dir: Path, lang: str = "en") -> list[Path]:
        """下载自动字幕并转换为 srt。"""
    
    def download_audio(self, url: str, output_path: Path) -> Path:
        """下载视频并提取音频。"""
    
    def parse_srt(self, srt_path: Path) -> str:
        """解析 srt 文件，去除重叠和重复文本。"""
```

### 9.2 NotebookLMTool（`tools/notebooklm_tool.py`）

```python
class NotebookLMTool:
    """封装 NotebookLM CLI 调用，支持项目创建、source 上传、ask 查询。"""
    
    def __init__(self, cli_path: str = ".venv/bin/notebooklm"):
        self.cli_path = cli_path
    
    def create_notebook(self, title: str) -> str:
        """创建项目，返回 notebook_id。"""
    
    def upload_sources(self, notebook_id: str, files: list[Path]) -> dict:
        """批量上传 source，返回上传结果统计。"""
    
    def ask(self, notebook_id: str, question: str, timeout: int = 180) -> str:
        """向 NotebookLM 提问，返回回答文本。"""
    
    def list_sources(self, notebook_id: str) -> list[dict]:
        """获取已上传 source 列表。"""
    
    def delete_notebook(self, notebook_id: str) -> bool:
        """删除项目。"""
```

### 9.3 GeminiTool（`tools/gemini_tool.py`）

```python
class GeminiTool:
    """封装 Gemini API 调用，支持内容生成、精修、重试机制。"""
    
    def __init__(self, api_key: str | None = None, vertexai: bool = True):
        self.client = Client(vertexai=vertexai, api_key=api_key)
    
    def generate(self, prompt: str, model: str = "gemini-2.5-pro",
                 max_retries: int = 3, sleep_jitter: tuple = (0, 2)) -> str:
        """生成内容，内置重试和 sleep jitter。"""
    
    def refine_transcript(self, raw_text: str, enforce_chinese: bool = True) -> str:
        """精修转录文本，可选强制中文输出。"""
    
    def generate_syllabus(self, transcripts: list[str]) -> str:
        """基于转录文本生成课程大纲。"""
    
    def generate_chapter(self, transcript: str, chapter_title: str) -> str:
        """生成单章深入分析。"""
    
    def generate_anki(self, chapters: list[str], count: int = 20) -> str:
        """生成 Anki 卡片。"""
```

**Sleep Jitter 实现**：
```python
import random
time.sleep(base_delay + random.uniform(*sleep_jitter))
```

---

## 10. 日志规范

### 9.1 日志格式（JSON Lines）

```json
{"ts":"2026-06-04T10:00:00+08:00","level":"INFO","task_id":"yl-001","phase":"transcribe","msg":"开始下载字幕","meta":{"video":"01-标题","progress":"1/25"}}
{"ts":"2026-06-04T10:05:00+08:00","level":"INFO","task_id":"yl-001","phase":"transcribe","msg":"精修完成","meta":{"output_size":25000}}
{"ts":"2026-06-04T10:06:00+08:00","level":"WARN","task_id":"yl-001","phase":"study","msg":"NotebookLM source upload failed","meta":{"sources":0,"action":"fallback_to_gemini"}}
```

### 9.2 日志文件结构

```
logs/
├── executor.log          # 引擎全局日志
├── executor.2026-06-04.log  # 轮转历史日志
└── yl-260604-001/
    ├── main.log          # 任务主日志
    ├── transcribe.log    # 转录阶段详细日志
    ├── study.log         # 学习阶段详细日志
    └── quality.log       # 质量检查日志
```

### 9.3 日志轮转规则

| 条件 | 动作 |
|------|------|
| 单个日志文件 > 10MB | 自动切分，后缀加 `.1`、`.2` |
| 日期变化 | executor.log 自动归档为 `executor.YYYY-MM-DD.log` |
| 保留策略 | 只保留最近 7 天的轮转日志 |

---

## 10. Prompt 版本控制

### 10.1 注册表结构

```python
PROMPT_REGISTRY = {
    "refine": {
        "v1": "...",
        "v2": "...",  # 当前生产版本
    },
    "syllabus": {
        "v1": "...",
    },
    "chapter_deep_dive": {
        "v1": "...",
    }
}
```

### 10.2 精修 Prompt v3（防过度总结 + 强制中文）

```
这是一段音频转录文本，请进行以下优化，输出必须为中文：
1. 补全标点符号（句号、逗号等）
2. 修正识别错误的术语、人名、地名
3. 去除口语噪音（"嗯"、"啊"、"那个"等填充词）
4. 按语义分段（每段一个主题）
5. Obsidian 格式化（Markdown 标准格式）
6. 所有内容翻译成中文，保留专业术语的英文原文（首次出现可标注英文）

请直接输出优化后的中文文本，不要添加额外说明。
```

**规则**：
- 无 persona、无示例、无禁止性指令
- 顶部强制声明 `输出必须为中文`
- 所有 prompt 统一使用 `output_must_be_chinese = True` 开关控制

### 10.3 Prompt 版本切换

```python
# 切换精修 prompt 版本
prompt_registry.set_version("refine", "v3")

# 强制中文输出（全局开关）
prompt_registry.set_global_flag("enforce_chinese", True)
```

---

## 11. Metrics 与 Dashboard

### 11.1 指标收集

每次任务完成后更新 `logs/metrics.json`：

```json
{
  "updated_at": "2026-06-05T12:00:00",
  "total_tasks": 100,
  "completed": 85,
  "failed": 10,
  "pending": 5,
  "avg_transcribe_time": 3600,
  "avg_study_time": 1800,
  "success_rate": 0.85
}
```

### 11.2 CLI 查询

```bash
python cli.py metrics
# 输出：
# 总任务: 100 | 完成: 85 | 失败: 10 | 成功率: 85%
# 平均转录耗时: 60分钟 | 平均学习耗时: 30分钟
```

---

## 12. 健康检查接口

### 12.1 Daemon 心跳

daemon 每 5 秒更新 `logs/.health`：

```json
{"pid": 12345, "status": "running", "current_task": "yl-001", "last_heartbeat": "2026-06-05T12:00:00"}
```

### 12.2 CLI 健康检查

```bash
python cli.py health
# 输出：
# daemon: running (pid=12345)
# 当前任务: yl-001 (transcribe, 45%)
# 最后心跳: 2秒前
```

---

## 13. 错误分类精细化

### 13.1 错误码定义

```python
class ErrorCode(str, Enum):
    # YouTube 相关
    YT_DLP_403 = "yt_dlp_403"
    YT_DLP_TIMEOUT = "yt_dlp_timeout"
    YT_DLP_INVALID_URL = "yt_dlp_invalid_url"
    
    # Gemini API 相关
    GEMINI_429 = "gemini_429"
    GEMINI_CONTENT_FILTER = "gemini_content_filter"
    GEMINI_REMOTE_PROTOCOL = "gemini_remote_protocol"
    
    # NotebookLM 相关
    NOTEBOOKLM_RPC = "notebooklm_rpc"
    NOTEBOOKLM_ZERO_SOURCE = "notebooklm_zero_source"
    NOTEBOOKLM_100_SOURCE = "notebooklm_100_source"
    NOTEBOOKLM_TIMEOUT = "notebooklm_timeout"
    
    # 质量相关
    QUALITY_LOW_RETENTION = "quality_low_retention"
    QUALITY_ENGLISH_OUTPUT = "quality_english_output"
    QUALITY_EMPTY_OUTPUT = "quality_empty_output"
    
    # 系统相关
    DISK_FULL = "disk_full"
    ORPHAN_TASK = "orphan_task"
    TIMEOUT = "timeout"
```

### 13.2 错误码使用

所有 failed 任务必须携带 `error_code`，便于 Agent 自动化决策：

```python
# Agent 可根据错误码自动决策
if task.error_code == ErrorCode.NOTEBOOKLM_RPC:
    # 建议：等待 10 分钟后重试
elif task.error_code == ErrorCode.GEMINI_429:
    # 建议：等待 1 小时后重试
elif task.error_code == ErrorCode.DISK_FULL:
    # 建议：清理磁盘，无法自动恢复
```

---

## 14. 实现路线图

### Phase 1：任务骨架（1-2 天）
- [ ] `config.py` — 配置中心化管理（config.json + config_local.json）
- [ ] `task_queue.py` — JSON 任务队列 + 状态机（支持 transcribe/study/anki 三种类型）
- [ ] `cli.py` — submit / status / logs / list / retry / metrics / health 命令
- [ ] `logger.py` — JSON Lines 结构化日志（按任务隔离 + 日志轮转）
- [ ] `executor.py` — 单 worker 串行执行壳（含超时控制、孤儿恢复、文件锁）

### Phase 2：执行引擎（2-3 天）
- [ ] 集成三种流水线（transcribe / study / anki）
- [ ] 断点续传（checkpoint + 文件系统扫描）
- [ ] 错误重试（指数退避 + 错误码分类，3 次后标记 failed）
- [ ] `daemon` 模式（单 worker + 文件锁 + 心跳机制）
- [ ] 幂等性保证（跳过已处理文件）
- [ ] 输入验证（URL 校验 + course name sanitization）

### Phase 3：质量与工具（2-3 天）
- [ ] `quality_gate.py` — 转录/产出质量检查（含中文字符占比、英文输出检测）
- [ ] `retry_manager.py` — 错误记录、重试脚本生成、批量重试
- [ ] `tools/` — YouTubeTool / NotebookLMTool / GeminiTool 封装
- [ ] Sleep Jitter 全局配置（随机偏移防限流）
- [ ] `prompt_registry.py` — Prompt 版本控制（强制中文输出 v3）
- [ ] 日志轮转（按大小/日期切分，保留 7 天）

### Phase 4：可观测性与 Agent 集成（1 天）
- [ ] `metrics.py` — 指标收集与 `cli.py metrics` 命令
- [ ] 健康检查接口（`cli.py health` + daemon 心跳）
- [ ] 任务完成通知（写入 Obsidian Dashboard）
- [ ] Hermes / Kimi-Word 调用示例（skill 风格）

---

## 15. 已确认事项

| 事项 | 决策 |
|------|------|
| **队列持久化** | JSON 文件（简单，无需额外依赖） |
| **任务类型** | 3 种：`transcribe`（转录精修）、`study`（NotebookLM 学习）、`anki`（Anki 生成），可按需指定 |
| **错误处理** | NotebookLM 失败时**不降级**，记录错误日志并提供重试脚本 |
| **质量标准** | 精修保留率 ≥ 70%、中文占比 ≥ 80%，阈值合理 |
| **执行并发** | **单 worker 串行**（安全，避免 API rate limit） |
| **通知机制** | 任务完成后**通知用户**（写入 Obsidian Dashboard 或日志标记） |
| **输入输出目录** | 在项目空间 `Project_C_YouTube_Learning/` 下建立：`input/`、`output/`、`anki/`、`notes/`、`logs/` |
| **Agent 调用风格** | 保留 skill 风格，CLI 接口简洁 |

---

## 16. 附录：Agent 调用示例

### Hermes 调用示例

```yaml
# hermes skill 配置
- name: youtube-course-agent
  command: |
    cd ~/Documents/my_ai_os_vault/03_Projects/Project_C_YouTube_Learning
    python agent_service/cli.py submit "{{playlist_url}}" --name "{{course_name}}"
  output_parser: json
```

### Kimi-Word 调用示例

```python
import subprocess

def submit_course(playlist_url: str, course_name: str) -> dict:
    result = subprocess.run(
        ["python", "cli.py", "submit", playlist_url, "--name", course_name],
        capture_output=True, text=True,
        cwd="~/Documents/my_ai_os_vault/03_Projects/Project_C_YouTube_Learning"
    )
    return json.loads(result.stdout)

def check_status(task_id: str) -> dict:
    result = subprocess.run(
        ["python", "cli.py", "status", task_id],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)
```

---

*版本: v1.2*
*日期: 2026-06-05*
*作者: DALONG ZHANG*
