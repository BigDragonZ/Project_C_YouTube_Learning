"""NotebookLM CLI wrapper with upload, ask, and source management."""

import json
import subprocess
import time
from pathlib import Path
from typing import List, Optional


class NotebookLMTool:
    """封装 NotebookLM CLI 调用，支持项目创建、source 上传、ask 查询。"""

    def __init__(self, cli_path: str = ".venv/bin/notebooklm"):
        self.cli_path = cli_path

    def _run(self, args: list, timeout: int = 180, capture: bool = True) -> subprocess.CompletedProcess:
        cmd = [self.cli_path] + args
        return subprocess.run(cmd, capture_output=capture, text=True, timeout=timeout)

    def create_notebook(self, title: str) -> str:
        """创建项目，返回 notebook_id。"""
        result = self._run(["create", title])
        # Parse "Created notebook: <ID> - <title>"
        if "Created notebook:" in result.stdout:
            parts = result.stdout.strip().split("Created notebook: ")[1].split(" - ")
            return parts[0]
        raise RuntimeError(f"Failed to create notebook: {result.stderr}")

    def list_notebooks(self) -> list[dict]:
        """列出所有 notebooks。"""
        result = self._run(["list", "--json"])
        try:
            data = json.loads(result.stdout)
            if isinstance(data, dict) and "notebooks" in data:
                return data["notebooks"]
            if isinstance(data, list):
                return data
            return []
        except json.JSONDecodeError:
            return []

    def upload_sources(self, notebook_id: str, files: List[Path]) -> dict:
        """批量上传 source，返回上传结果统计。"""
        uploaded = 0
        skipped = 0
        failed = 0
        # Cache existing sources to avoid N+1 queries
        existing = {s.get("name") or s.get("title", "") for s in self.list_sources(notebook_id)}
        for f in files:
            if f.name in existing:
                skipped += 1
                continue
            try:
                result = self._run(["source", "add", "--notebook", notebook_id, str(f)])
                if result.returncode == 0:
                    uploaded += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
            time.sleep(1)  # Rate limiting
        return {"uploaded": uploaded, "skipped": skipped, "failed": failed}

    def ask(self, notebook_id: str, question: str, timeout: int = 180) -> str:
        """向 NotebookLM 提问，返回回答文本。"""
        self._run(["use", notebook_id], timeout=30)
        result = self._run(["ask", question], timeout=timeout)
        return result.stdout

    def list_sources(self, notebook_id: str) -> list[dict]:
        """获取已上传 source 列表。"""
        result = self._run(["source", "list", "--notebook", notebook_id, "--json"])
        try:
            data = json.loads(result.stdout)
            if isinstance(data, dict) and "sources" in data:
                return data["sources"]
            if isinstance(data, list):
                return data
            return []
        except json.JSONDecodeError:
            return []

    def delete_notebook(self, notebook_id: str) -> bool:
        """删除项目。"""
        result = self._run(["delete", "-n", notebook_id, "-y"])
        return result.returncode == 0
