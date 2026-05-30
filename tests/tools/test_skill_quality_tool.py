"""Tests for the skill_rate tool."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def skill_rate_env(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    (home / "skills").mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    import tools.skill_usage as skill_usage
    import tools.skill_quality_tool as skill_quality_tool

    importlib.reload(skill_usage)
    importlib.reload(skill_quality_tool)
    return skill_usage, skill_quality_tool


def test_skill_rate_records_success(skill_rate_env):
    usage, tool = skill_rate_env
    usage.mark_agent_created("research-skill")

    result = json.loads(tool.skill_rate("research-skill", "success"))

    assert result["success"] is True
    assert result["name"] == "research-skill"
    assert result["record"]["success_count"] == 1
    assert result["record"]["failure_count"] == 0
    assert result["record"]["quality_state"] == usage.QUALITY_DRAFT
    assert "draft" in result["recommendation"]


def test_skill_rate_returns_structured_error_for_invalid_outcome(skill_rate_env):
    _usage, tool = skill_rate_env

    result = json.loads(tool.skill_rate("research-skill", "maybe"))

    assert result["success"] is False
    assert "outcome must be" in result["error"]


def test_skill_rate_recommends_rewrite_for_deprecated_skill(skill_rate_env):
    usage, tool = skill_rate_env
    usage.mark_agent_created("bad-skill")
    usage.record_outcome("bad-skill", "success")
    for _ in range(3):
        usage.record_outcome("bad-skill", "failure")

    result = json.loads(tool.skill_rate("bad-skill", "failure"))

    assert result["success"] is True
    assert result["record"]["quality_state"] == usage.QUALITY_DEPRECATED
    assert result["record"]["needs_rewrite"] is True
    assert "rewrite" in result["recommendation"]
