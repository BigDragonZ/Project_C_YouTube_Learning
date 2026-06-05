# NotebookLM 批量上传脚本（带去重、间隔、验证）

## 问题

NotebookLM 的 `source add` 命令在批量上传 20+ 文件时容易超时或触发 rate limit。

## 解决方案

使用带间隔和去重检查的循环脚本：

```bash
#!/bin/bash
# 用法: ./upload_to_notebooklm.sh <notebook_id> <course_dir>

NOTEBOOK_ID="$1"
COURSE_DIR="$2"

for f in "$COURSE_DIR"/*.md; do
  basename=$(basename "$f")
  
  # 去重检查
  if uv run notebooklm source list --notebook "$NOTEBOOK_ID" 2>/dev/null | grep -q "$basename"; then
    echo "SKIP (exists): $basename"
    continue
  fi
  
  # 上传
  uv run notebooklm source add --notebook "$NOTEBOOK_ID" "$f" 2>/dev/null
  echo "OK: $basename"
  
  # 间隔避免 rate limit
  sleep 1
done

# 验证
expected=$(ls "$COURSE_DIR"/*.md | wc -l)
actual=$(uv run notebooklm source list --notebook "$NOTEBOOK_ID" 2>/dev/null | grep -c "ready")
echo "Expected: $expected, Actual: $actual"
```

## 注意事项

1. **Notebook ID 格式**: 使用 `--notebook` 参数，不是 `--notebook-id`
2. **重复上传**: NotebookLM 会报错但不影响已有文件
3. **大文件**: 单个 Markdown 文件超过 1MB 时可能需要拆分
4. **验证**: 上传后务必运行 `source list` 确认数量

## 手动上传（文件较少时）

```bash
# 单文件上传
uv run notebooklm source add --notebook "$NOTEBOOK_ID" file.md

# 查看已上传
uv run notebooklm source list --notebook "$NOTEBOOK_ID"
```
