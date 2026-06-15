"""
NotebookLM adapter implementations.
"""

from lib.adapters.base import NotebookLMAdapter
from lib.adapters.cli import CLIAdapter
from lib.adapters.mock import MockAdapter

__all__ = ["NotebookLMAdapter", "CLIAdapter", "MockAdapter"]
