"""Skill quality telemetry tool.

Provides ``skill_rate`` so the agent can explicitly record whether a loaded
skill helped or failed.  This is separate from skill activity counters: activity
answers "was it used?", quality answers "did it work?".
"""

from __future__ import annotations

import json
from typing import Any, Dict

from tools.registry import registry
from tools import skill_usage


def check_skill_quality_requirements() -> bool:
    return True


def _recommendation(record: Dict[str, Any]) -> str:
    quality = record.get("quality_state")
    if record.get("needs_rewrite") or quality == skill_usage.QUALITY_DEPRECATED:
        return "Skill is deprecated by outcome telemetry; inspect recent failures and suggest a gated rewrite before using it again."
    if quality == skill_usage.QUALITY_DRAFT:
        return "Skill is still draft-quality; keep rating outcomes until it earns enough successful uses to promote."
    return "Skill is active-quality; continue using it when relevant and keep rating notable outcomes."


def skill_rate(name: str, outcome: str, note: str | None = None) -> str:
    """Record a success/failure outcome for a skill and return the updated record."""
    skill_name = str(name or "").strip()
    if not skill_name:
        return json.dumps({"success": False, "error": "name is required"})

    try:
        skill_usage.record_outcome(skill_name, outcome)
    except ValueError as exc:
        return json.dumps({"success": False, "error": str(exc), "name": skill_name})
    except Exception as exc:  # pragma: no cover - defensive; record_outcome is best-effort internally
        return json.dumps({"success": False, "error": f"failed to record outcome: {exc}", "name": skill_name})

    record = skill_usage.get_record(skill_name)
    result: Dict[str, Any] = {
        "success": True,
        "name": skill_name,
        "outcome": str(outcome or "").strip().lower(),
        "record": record,
        "recommendation": _recommendation(record),
    }
    if note:
        result["note"] = str(note).strip()
    return json.dumps(result, ensure_ascii=False)


SKILL_RATE_SCHEMA = {
    "name": "skill_rate",
    "description": (
        "Record whether using a skill succeeded or failed. Use after a skill materially helped "
        "or misled the task. This updates skill quality telemetry (draft/active/deprecated) "
        "but never edits, archives, or rewrites the skill."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Skill name to rate, e.g. hermes-cron-operations",
            },
            "outcome": {
                "type": "string",
                "enum": ["success", "failure"],
                "description": "Whether the skill helped complete the task or failed/misled it.",
            },
            "note": {
                "type": "string",
                "description": "Optional concise note about why the skill succeeded or failed.",
            },
        },
        "required": ["name", "outcome"],
    },
}


registry.register(
    name="skill_rate",
    toolset="skills",
    schema=SKILL_RATE_SCHEMA,
    handler=lambda args, **kw: skill_rate(
        name=args.get("name", ""),
        outcome=args.get("outcome", ""),
        note=args.get("note"),
    ),
    check_fn=check_skill_quality_requirements,
    emoji="📈",
)
