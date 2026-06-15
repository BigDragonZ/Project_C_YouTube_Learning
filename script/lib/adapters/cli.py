"""
CLI-based NotebookLM adapter (production backend).
Wraps the notebooklm-py CLI with retry logic.
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Optional

from config.notebooklm import load_config
from lib.adapters.base import NotebookLMAdapter


def _run(
    args: list[str],
    cwd: Optional[Path] = None,
    timeout: int = 120,
) -> tuple[str, str, int]:
    """Run notebooklm CLI command, return (stdout, stderr, rc)."""
    cfg = load_config()
    cmd = [cfg.notebooklm_bin] + args

    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout, result.stderr, result.returncode


def _retry_run(
    args: list[str],
    cwd: Optional[Path] = None,
    timeout: int = 120,
    max_retries: Optional[int] = None,
    delay: Optional[int] = None,
) -> str:
    """Run with retry, raising on persistent failure."""
    cfg = load_config()
    max_retries = max_retries or cfg.max_retries
    delay = delay or cfg.retry_delay

    last_err = ""
    for attempt in range(1, max_retries + 1):
        stdout, stderr, rc = _run(args, cwd, timeout)
        if rc == 0:
            return stdout

        last_err = stderr or stdout
        print(f"  [WARN] notebooklm attempt {attempt}/{max_retries} failed: {last_err[:200]}")
        if attempt < max_retries:
            time.sleep(delay * attempt)

    raise RuntimeError(f"notebooklm failed after {max_retries} attempts: {last_err[:500]}")


class CLIAdapter(NotebookLMAdapter):
    """Production adapter using notebooklm CLI."""

    def create_notebook(self, title: str) -> str:
        print(f"[INFO] Creating notebook: {title}")
        stdout = _retry_run(["create", title], timeout=60)
        for line in reversed(stdout.strip().splitlines()):
            line = line.strip()
            if line and len(line) > 20:
                return line.split()[-1]
        raise RuntimeError(f"Could not parse notebook ID from output: {stdout[:500]}")

    def list_notebooks(self) -> list[dict]:
        stdout = _retry_run(["list", "--json"], timeout=30)
        try:
            data = json.loads(stdout)
            if isinstance(data, dict) and "notebooks" in data:
                return data["notebooks"]
            if isinstance(data, list):
                return data
            return []
        except json.JSONDecodeError:
            return []

    def find_notebook(self, title_substring: str) -> Optional[str]:
        notebooks = self.list_notebooks()
        for nb in notebooks:
            if title_substring.lower() in nb.get("title", "").lower():
                return nb.get("id")
        return None

    def use_notebook(self, notebook_id: str) -> None:
        _retry_run(["use", notebook_id], timeout=30)
        print(f"[OK] Using notebook: {notebook_id}")

    def list_sources(self) -> list[dict]:
        stdout = _retry_run(["source", "list", "--json"], timeout=30)
        try:
            data = json.loads(stdout)
            if isinstance(data, dict) and "sources" in data:
                return data["sources"]
            if isinstance(data, list):
                return data
            return []
        except json.JSONDecodeError:
            return []

    def source_exists(self, filename: str) -> bool:
        sources = self.list_sources()
        for src in sources:
            name = src.get("name") or src.get("title", "")
            if filename.lower() in name.lower():
                return True
        return False

    def add_source(self, file_path: str) -> None:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Source file not found: {file_path}")

        filename = path.name
        if self.source_exists(filename):
            print(f"  [SKIP] Source already exists: {filename}")
            return

        print(f"  [INFO] Uploading source: {filename}")
        _retry_run(["source", "add", str(path)], timeout=120)
        print(f"  [OK] Uploaded: {filename}")

    def upload_sources_dir(self, dir_path: Path, pattern: str = "*.md") -> tuple[int, int]:
        files = sorted(dir_path.glob(pattern))
        uploaded = 0
        skipped = 0

        for f in files:
            if f.name.startswith("_"):
                continue
            if self.source_exists(f.name):
                skipped += 1
                continue
            self.add_source(str(f))
            uploaded += 1
            time.sleep(1)

        return uploaded, skipped

    def verify_upload(self, expected_count: int) -> bool:
        sources = self.list_sources()
        ready_count = sum(1 for s in sources if s.get("status") == "ready")
        print(f"[INFO] Sources ready: {ready_count}/{expected_count}")
        return ready_count >= expected_count

    def ask(self, question: str, timeout: int = 180) -> str:
        stdout = _retry_run(["ask", question], timeout=timeout, max_retries=2)
        return stdout

    def configure_persona(self, persona: str) -> None:
        _retry_run(["configure", "--persona", persona], timeout=30)
        print("[OK] Persona configured")

    def get_history(self) -> list[dict]:
        stdout = _retry_run(["history", "--json"], timeout=30)
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return []
