"""Tests for skill success/failure telemetry used by Harvey self-improvement."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest


@pytest.fixture
def skill_usage_env(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    (home / "skills").mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    import tools.skill_usage as skill_usage

    importlib.reload(skill_usage)
    return skill_usage


def test_record_outcome_tracks_success_and_failure_counts(skill_usage_env):
    usage = skill_usage_env

    usage.record_outcome("research-skill", "success")
    usage.record_outcome("research-skill", "failure")

    rec = usage.get_record("research-skill")
    assert rec["success_count"] == 1
    assert rec["failure_count"] == 1
    assert rec["last_success_at"] is not None
    assert rec["last_failure_at"] is not None
    assert rec["last_outcome"] == "failure"
    assert rec["outcome_count"] == 2
    assert rec["success_rate"] == pytest.approx(0.5)


def test_record_outcome_promotes_draft_after_success_threshold(skill_usage_env):
    usage = skill_usage_env
    usage.mark_agent_created("new-skill")

    assert usage.get_record("new-skill")["quality_state"] == usage.QUALITY_DRAFT

    usage.record_outcome("new-skill", "success")
    usage.record_outcome("new-skill", "success")
    assert usage.get_record("new-skill")["quality_state"] == usage.QUALITY_DRAFT

    usage.record_outcome("new-skill", "success")
    assert usage.get_record("new-skill")["quality_state"] == usage.QUALITY_ACTIVE


def test_record_outcome_deprecates_chronically_failing_agent_skill(skill_usage_env):
    usage = skill_usage_env
    usage.mark_agent_created("bad-skill")
    usage.record_outcome("bad-skill", "success")

    for _ in range(4):
        usage.record_outcome("bad-skill", "failure")

    rec = usage.get_record("bad-skill")
    assert rec["outcome_count"] == 5
    assert rec["success_rate"] == pytest.approx(0.2)
    assert rec["quality_state"] == usage.QUALITY_DEPRECATED
    assert rec["needs_rewrite"] is True


def test_record_outcome_rejects_invalid_outcome(skill_usage_env):
    usage = skill_usage_env

    with pytest.raises(ValueError):
        usage.record_outcome("some-skill", "maybe")
