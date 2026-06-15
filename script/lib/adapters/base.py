"""
NotebookLM adapter interface.

Allows swapping between CLI-based and future API-based backends.
Also enables mock injection for unit testing.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class NotebookLMAdapter(ABC):
    """Abstract interface for NotebookLM operations."""

    @abstractmethod
    def create_notebook(self, title: str) -> str:
        """Create notebook, return ID."""
        ...

    @abstractmethod
    def list_notebooks(self) -> list[dict]:
        """List all notebooks."""
        ...

    @abstractmethod
    def find_notebook(self, title_substring: str) -> Optional[str]:
        """Find notebook ID by title substring."""
        ...

    @abstractmethod
    def use_notebook(self, notebook_id: str) -> None:
        """Set active notebook."""
        ...

    @abstractmethod
    def list_sources(self) -> list[dict]:
        """List sources in active notebook."""
        ...

    @abstractmethod
    def source_exists(self, filename: str) -> bool:
        """Check if source exists."""
        ...

    @abstractmethod
    def add_source(self, file_path: str) -> None:
        """Add a file as source."""
        ...

    @abstractmethod
    def upload_sources_dir(self, dir_path: Path, pattern: str = "*.md") -> tuple[int, int]:
        """Upload directory. Returns (uploaded, skipped)."""
        ...

    @abstractmethod
    def verify_upload(self, expected_count: int) -> bool:
        """Verify sources ready."""
        ...

    @abstractmethod
    def ask(self, question: str, timeout: int = 180) -> str:
        """Ask question, return answer."""
        ...

    @abstractmethod
    def configure_persona(self, persona: str) -> None:
        """Set chat persona."""
        ...

    @abstractmethod
    def get_history(self) -> list[dict]:
        """Get conversation history."""
        ...
