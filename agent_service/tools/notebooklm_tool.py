"""NotebookLM CLI wrapper for project creation, source upload, and queries."""

import json
import subprocess
import time
from pathlib import Path
from typing import List, Optional

from ..config import get_config


class NotebookLMTool:
    """Wrapper for NotebookLM CLI operations."""

    def __init__(self, cli_path: Optional[str] = None):
        cfg = get_config()
        self.cli_path = cli_path or cfg.get("api", "notebooklm_cli", default=".venv/bin/notebooklm")
        self.timeout = cfg.get("api", "notebooklm_timeout", default=180)

    def _run(self, args: List[str], timeout: Optional[int] = None) -> subprocess.CompletedProcess:
        cmd = [self.cli_path] + args
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout or self.timeout)

    def create_notebook(self, title: str) -> str:
        """Create a new notebook and return its ID."""
        result = self._run(["create", title])
        if result.returncode != 0:
            raise RuntimeError(f"notebooklm create failed: {result.stderr}")
        # Parse "Created notebook: <id> - <title>"
        for line in result.stdout.splitlines():
            if "Created notebook:" in line:
                parts = line.split("Created notebook: ")[1].split(" - ")
                return parts[0].strip()
        raise RuntimeError(f"Could not parse notebook ID from: {result.stdout}")

    def list_notebooks(self) -> List[dict]:
        """List all notebooks."""
        result = self._run(["list", "--json"])
        if result.returncode != 0:
            return []
        try:
            data = json.loads(result.stdout)
            if isinstance(data, dict) and "notebooks" in data:
                return data["notebooks"]
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
        return []

    def upload_sources(self, notebook_id: str, files: List[Path]) -> dict:
        """Upload multiple sources with deduplication and rate limiting."""
        existing = {s.get("name", s.get("title", "")) for s in self.list_sources(notebook_id)}
        uploaded = 0
        skipped = 0
        failed = 0
        for f in files:
            if f.name in existing or f.name.startswith("_"):
                skipped += 1
                continue
            result = self._run(["source", "add", "--notebook", notebook_id, str(f)])
            if result.returncode == 0 or "already exists" in result.stderr:
                uploaded += 1
            else:
                failed += 1
            time.sleep(1)  # Rate limit protection
        return {"uploaded": uploaded, "skipped": skipped, "failed": failed}

    def list_sources(self, notebook_id: str) -> List[dict]:
        """List sources in a notebook."""
        result = self._run(["source", "list", "--notebook", notebook_id, "--json"])
        if result.returncode != 0:
            return []
        try:
            data = json.loads(result.stdout)
            if isinstance(data, dict) and "sources" in data:
                return data["sources"]
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
        return []

    def ask(self, notebook_id: str, question: str, timeout: Optional[int] = None) -> str:
        """Ask a question to the notebook."""
        result = self._run(["ask", "--notebook", notebook_id, question], timeout=timeout)
        if result.returncode != 0:
            raise RuntimeError(f"notebooklm ask failed: {result.stderr}")
        return result.stdout

    def use_notebook(self, notebook_id: str) -> None:
        """Set the active notebook context."""
        self._run(["use", notebook_id])

    def delete_notebook(self, notebook_id: str) -> bool:
        """Delete a notebook."""
        result = self._run(["delete", "-n", notebook_id, "-y"])
        return result.returncode == 0
