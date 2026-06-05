"""Tests for prompt_registry.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prompt_registry import PromptRegistry, get_registry


def test_singleton():
    r1 = get_registry()
    r2 = get_registry()
    assert r1 is r2


def test_get_refine_prompt():
    r = PromptRegistry()
    prompt = r.get("refine", body="test content")
    assert "test content" in prompt
    assert "优化" in prompt


def test_version_switch():
    r = PromptRegistry()
    r.set_version("refine", "v1")
    p1 = r.get("refine", body="x")
    assert "输出必须为中文" not in p1
    r.set_version("refine", "v3")
    p3 = r.get("refine", body="x")
    assert "输出必须为中文" in p3


def test_global_flag():
    r = PromptRegistry()
    r.set_global_flag("enforce_chinese", True)
    assert r.get_global_flag("enforce_chinese") is True
    r.set_global_flag("enforce_chinese", False)
    assert r.get_global_flag("enforce_chinese") is False


def test_list_prompts():
    r = PromptRegistry()
    prompts = r.list_prompts()
    assert "refine" in prompts
    assert "syllabus" in prompts
    assert prompts["refine"] == "v3"


def test_missing_variable():
    r = PromptRegistry()
    try:
        r.get("chapter_deep_dive")  # missing required variables
        assert False, "Should have raised ValueError"
    except (ValueError, KeyError):
        pass


if __name__ == "__main__":
    test_singleton()
    test_get_refine_prompt()
    test_version_switch()
    test_global_flag()
    test_list_prompts()
    test_missing_variable()
    print("test_prompt_registry.py: ALL PASSED")
