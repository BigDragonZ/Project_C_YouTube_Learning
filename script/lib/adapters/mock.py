"""
Mock NotebookLM adapter for unit testing and dry-run mode.
"""

from pathlib import Path
from typing import Optional

from lib.adapters.base import NotebookLMAdapter


class MockAdapter(NotebookLMAdapter):
    """In-memory mock adapter. Records all calls for verification."""

    def __init__(self):
        self.notebooks: dict[str, str] = {}  # title -> id
        self.sources: dict[str, list[str]] = {}  # notebook_id -> [filenames]
        self.calls: list[dict] = []
        self._next_id = 1

    def _record(self, method: str, **kwargs) -> None:
        self.calls.append({"method": method, **kwargs})

    def create_notebook(self, title: str) -> str:
        self._record("create_notebook", title=title)
        nb_id = f"mock-{self._next_id:04d}"
        self._next_id += 1
        self.notebooks[title] = nb_id
        return nb_id

    def list_notebooks(self) -> list[dict]:
        self._record("list_notebooks")
        return [
            {"id": nid, "title": title}
            for title, nid in self.notebooks.items()
        ]

    def find_notebook(self, title_substring: str) -> Optional[str]:
        self._record("find_notebook", title_substring=title_substring)
        for title, nid in self.notebooks.items():
            if title_substring.lower() in title.lower():
                return nid
        return None

    def use_notebook(self, notebook_id: str) -> None:
        self._record("use_notebook", notebook_id=notebook_id)

    def list_sources(self) -> list[dict]:
        self._record("list_sources")
        # Return empty for simplicity; override in tests if needed
        return []

    def source_exists(self, filename: str) -> bool:
        self._record("source_exists", filename=filename)
        return False

    def add_source(self, file_path: str) -> None:
        self._record("add_source", file_path=file_path)

    def upload_sources_dir(self, dir_path: Path, pattern: str = "*.md") -> tuple[int, int]:
        self._record("upload_sources_dir", dir_path=str(dir_path), pattern=pattern)
        files = list(dir_path.glob(pattern))
        return len(files), 0

    def verify_upload(self, expected_count: int) -> bool:
        self._record("verify_upload", expected_count=expected_count)
        return True

    def ask(self, question: str, timeout: int = 180) -> str:
        self._record("ask", question=question[:100], timeout=timeout)
        return f"[MOCK RESPONSE for: {question[:50]}...]"

    def configure_persona(self, persona: str) -> None:
        self._record("configure_persona", persona=persona[:50])

    def get_history(self) -> list[dict]:
        self._record("get_history")
        return []
