"""NotebookLM CLI wrapper with retry logic, source management, and adapter interface."""

import json
import subprocess
import time
from pathlib import Path
from typing import List, Optional, Tuple


class NotebookLMTool:
    """封装 NotebookLM CLI 调用，支持重试、项目创建、source 上传、ask 查询。"""

    def __init__(self, cli_path: Optional[str] = None):
        if cli_path is None:
            from config import get_config
            cfg = get_config()
            cli_path = cfg.get("api", "notebooklm_bin", default=".venv/bin/notebooklm")
        self.cli_path = cli_path
        self._current_notebook: Optional[str] = None

    def _run(
        self,
        args: list,
        timeout: int = 180,
        capture: bool = True,
    ) -> subprocess.CompletedProcess:
        cmd = [self.cli_path] + args
        return subprocess.run(cmd, capture_output=capture, text=True, timeout=timeout)

    def _retry_run(
        self,
        args: list,
        timeout: int = 120,
        max_retries: Optional[int] = None,
        delay: Optional[int] = None,
    ) -> str:
        """Run with exponential backoff retry."""
        from config import get_config
        cfg = get_config()
        max_retries = max_retries or cfg.get("retry", "max_retries", default=3)
        delay = delay or cfg.get("retry", "sleep_jitter", default=[0, 2])[1]

        last_err = ""
        for attempt in range(1, max_retries + 1):
            stdout, stderr, rc = self._run(args, timeout)
            if rc == 0:
                return stdout
            last_err = stderr or stdout
            print(f"  [WARN] notebooklm attempt {attempt}/{max_retries} failed: {last_err[:200]}")
            if attempt < max_retries:
                time.sleep(delay * attempt)
        raise RuntimeError(f"notebooklm failed after {max_retries} attempts: {last_err[:500]}")

    def create_notebook(self, title: str) -> str:
        """创建项目，返回 notebook_id。"""
        result = self._run(["create", title])
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

    def find_notebook(self, title_substring: str) -> Optional[str]:
        """按标题子串查找 notebook ID。"""
        notebooks = self.list_notebooks()
        for nb in notebooks:
            if title_substring.lower() in nb.get("title", "").lower():
                return nb.get("id")
        return None

    def use_notebook(self, notebook_id: str) -> None:
        """设置当前 notebook 上下文。"""
        self._retry_run(["use", notebook_id], timeout=30)
        self._current_notebook = notebook_id
        print(f"[OK] Using notebook: {notebook_id}")

    def list_sources(self, notebook_id: Optional[str] = None) -> list[dict]:
        """获取已上传 source 列表。"""
        if notebook_id:
            self._run(["use", notebook_id], timeout=30)
        result = self._run(["source", "list", "--json"])
        try:
            data = json.loads(result.stdout)
            if isinstance(data, dict) and "sources" in data:
                return data["sources"]
            if isinstance(data, list):
                return data
            return []
        except json.JSONDecodeError:
            return []

    def source_exists(self, filename: str, notebook_id: Optional[str] = None) -> bool:
        """检查 source 是否已存在。"""
        sources = self.list_sources(notebook_id)
        for src in sources:
            name = src.get("name") or src.get("title", "")
            if filename.lower() in name.lower():
                return True
        return False

    def add_source(
        self,
        file_path: str,
        notebook_id: Optional[str] = None,
    ) -> None:
        """上传单个 source，自动跳过已存在文件。"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Source file not found: {file_path}")
        if notebook_id:
            self.use_notebook(notebook_id)
        if self.source_exists(path.name):
            print(f"  [SKIP] Source already exists: {path.name}")
            return
        print(f"  [INFO] Uploading source: {path.name}")
        self._retry_run(["source", "add", str(path)], timeout=120)
        print(f"  [OK] Uploaded: {path.name}")

    def upload_sources(
        self,
        notebook_id: str,
        files: List[Path],
    ) -> dict:
        """批量上传 source，返回上传结果统计。"""
        uploaded = 0
        skipped = 0
        failed = 0
        self.use_notebook(notebook_id)
        for f in files:
            try:
                self.add_source(str(f))
                uploaded += 1
            except RuntimeError:
                skipped += 1
            except Exception:
                failed += 1
            time.sleep(1)
        return {"uploaded": uploaded, "skipped": skipped, "failed": failed}

    def upload_sources_dir(
        self,
        dir_path: Path,
        notebook_id: Optional[str] = None,
        pattern: str = "*.md",
    ) -> Tuple[int, int]:
        """批量上传目录下所有匹配文件。返回 (uploaded, skipped)。"""
        if notebook_id:
            self.use_notebook(notebook_id)
        files = sorted(dir_path.glob(pattern))
        uploaded = 0
        skipped = 0
        for f in files:
            if f.name.startswith("_"):
                continue
            try:
                self.add_source(str(f))
                uploaded += 1
            except RuntimeError:
                skipped += 1
            time.sleep(1)
        return uploaded, skipped

    def verify_upload(self, expected_count: int, notebook_id: Optional[str] = None) -> bool:
        """验证已上传 source 数量是否达标。"""
        sources = self.list_sources(notebook_id)
        ready_count = sum(1 for s in sources if s.get("status") == "ready")
        print(f"[INFO] Sources ready: {ready_count}/{expected_count}")
        return ready_count >= expected_count

    def ask(
        self,
        question: str,
        notebook_id: Optional[str] = None,
        timeout: int = 180,
    ) -> str:
        """向 NotebookLM 提问，返回回答文本。"""
        if notebook_id:
            self.use_notebook(notebook_id)
        return self._retry_run(["ask", question], timeout=timeout, max_retries=2)

    def configure_persona(self, persona: str, notebook_id: Optional[str] = None) -> None:
        """配置对话角色。"""
        if notebook_id:
            self.use_notebook(notebook_id)
        self._retry_run(["configure", "--persona", persona], timeout=30)
        print("[OK] Persona configured")

    def get_history(self, notebook_id: Optional[str] = None) -> list[dict]:
        """获取对话历史。"""
        if notebook_id:
            self.use_notebook(notebook_id)
        stdout = self._retry_run(["history", "--json"], timeout=30)
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return []

    def delete_notebook(self, notebook_id: str) -> bool:
        """删除项目。"""
        result = self._run(["delete", "-n", notebook_id, "-y"])
        return result.returncode == 0
