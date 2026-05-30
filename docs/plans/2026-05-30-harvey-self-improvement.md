# Harvey Self-Improvement Foundations Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Bring nano-hermes-inspired self-improvement mechanics into Harvey-on-Hermes without replacing Hermes and without running a separate nano-hermes sandbox.

**Architecture:** Extend existing Hermes mechanisms instead of adding a parallel runtime. Keep skill activity and skill quality as separate concepts: existing curator `state` remains `active/stale/archived`, while a new orthogonal `quality_state` handles `draft/active/deprecated`. Add reflection and trajectory summaries as opt-in, gated surfaces before any automatic skill rewrite is allowed.

**Tech Stack:** Python 3.11, Hermes Agent, existing `tools/skill_usage.py` sidecar (`~/.hermes/skills/.usage.json`), existing `agent/curator.py`, existing SQLite session store (`hermes_state.py`), pytest.

---

## Scope

Implement Saksham-approved points only:

1. Skill success/failure stats.
2. `draft → active → deprecated` skill quality lifecycle.
3. Reflection prompts after mistakes/corrections.
4. Trajectory-style summaries of completed work.
5. Gated “suggest skill rewrite” flow.

Explicitly skipped:

- Running nano-hermes as a separate Pi/sandbox side-agent.
- Fully automatic skill rewrites without human/agent approval.

---

## Current foundation already implemented in this branch/session

### Completed foundation slice

**Files:**
- Modified: `tools/skill_usage.py`
- Added: `tools/skill_quality_tool.py`
- Added: `tests/tools/test_skill_usage_outcomes.py`
- Added: `tests/tools/test_skill_quality_tool.py`

**Behavior:**
- Added orthogonal skill quality constants: `QUALITY_DRAFT`, `QUALITY_ACTIVE`, `QUALITY_DEPRECATED`.
- Added outcome fields to `.usage.json` records: `success_count`, `failure_count`, `outcome_count`, `success_rate`, `last_outcome`, `last_success_at`, `last_failure_at`, `needs_rewrite`.
- Added `record_outcome(skill_name, outcome)`.
- Added `skill_rate` in the `skills` toolset so Harvey can manually record skill success/failure outcomes after use.
- Agent-created skills now start `quality_state=draft` when marked via `mark_agent_created`.
- After 3 successes, agent-created skills promote to `quality_state=active`.
- After 5 outcomes with success rate ≤ 20%, agent-created skills become `quality_state=deprecated` and `needs_rewrite=true`.

**Verification command:**

```bash
python -m pytest tests/tools/test_skill_usage_outcomes.py tests/tools/test_skill_quality_tool.py -q
```

Expected: `7 passed`.

---

## Task 1: Show quality telemetry in curator reports/status — partially completed

**Objective:** Make skill quality visible so Harvey can reason about which skills are draft, trusted, or deprecated.

**Status:** Curator run reports now include `quality_counts`, `rewrite_candidates`, and a Markdown “Skill quality” section. CLI status display still needs a dedicated quality column/list.

**Files:**
- Modify: `tools/skill_usage.py`
- Modify: `agent/curator.py`
- Modify: `hermes_cli/curator.py`
- Test: `tests/agent/test_curator_reports.py`
- Test: `tests/hermes_cli/test_curator_status.py`

**Step 1: Write failing tests**

Add assertions that `agent_created_report()` includes:

```python
assert row["quality_state"] == "deprecated"
assert row["success_count"] == 1
assert row["failure_count"] == 4
assert row["success_rate"] == 0.2
assert row["needs_rewrite"] is True
```

Add CLI/status test asserting output includes `quality_state` or a compact `quality` column.

**Step 2: Run tests to verify failure**

```bash
python -m pytest tests/agent/test_curator_reports.py tests/hermes_cli/test_curator_status.py -q
```

Expected: FAIL because report/status does not yet display quality telemetry.

**Step 3: Implement minimal display support**

- Ensure `agent_created_report()` already backfills new fields.
- Update curator report Markdown to show quality fields.
- Update CLI `curator status` table/list to show `quality_state`, success/failure, and `needs_rewrite`.

**Step 4: Verify**

```bash
python -m pytest tests/agent/test_curator_reports.py tests/hermes_cli/test_curator_status.py -q
```

Expected: PASS.

---

## Task 2: Add a user/agent-facing skill outcome tool — completed

**Objective:** Let Harvey rate skills after using them without manually editing `.usage.json`.

**Status:** Implemented in `tools/skill_quality_tool.py` with tests in `tests/tools/test_skill_quality_tool.py`.

**Files:**
- Create: `tools/skill_quality_tool.py`
- Modify: `toolsets.py` to include tool in the `skills` toolset
- Test: `tests/tools/test_skill_quality_tool.py`

**Step 1: Write failing tests**

Test JSON tool behavior:

```python
def test_skill_rate_records_success(monkeypatch, tmp_path):
    result = json.loads(skill_rate({"name": "foo", "outcome": "success"}))
    assert result["success"] is True
    assert result["record"]["success_count"] == 1
```

Also test invalid outcome returns a structured error rather than raising into the agent loop.

**Step 2: Run test to verify failure**

```bash
python -m pytest tests/tools/test_skill_quality_tool.py -q
```

Expected: FAIL because tool does not exist.

**Step 3: Implement minimal tool**

Register one tool in `tools/skill_quality_tool.py`:

- name: `skill_rate`
- toolset: `skills`
- args: `name`, `outcome`, optional `note`
- calls `tools.skill_usage.record_outcome`
- returns updated record plus short recommendation:
  - active: trusted
  - draft: keep using/reviewing
  - deprecated: consider rewrite

**Step 4: Verify**

```bash
python -m pytest tests/tools/test_skill_quality_tool.py tests/tools/test_skill_usage_outcomes.py -q
```

Expected: PASS.

---

## Task 3: Add reflection nudges after mistakes/corrections

**Objective:** Nudge Harvey to write a compact reflection when the session shows failure signals, without forcing automatic memory writes.

**Files:**
- Modify: `run_agent.py` or the prompt-building path used after tool failures/user corrections
- Prefer creating helper: `agent/reflection_nudge.py`
- Test: `tests/run_agent/test_reflection_nudge.py`

**Step 1: Write failing tests**

Test pure helper behavior first:

```python
def test_correction_phrase_triggers_reflection_nudge():
    assert should_nudge_for_reflection(user_message="No, that's not what I asked") is True


def test_normal_message_does_not_trigger_nudge():
    assert should_nudge_for_reflection(user_message="thanks") is False
```

Add tool-error aggregation test:

```python
def test_repeated_tool_errors_trigger_reflection_nudge():
    tracker = ReflectionNudgeTracker(threshold=2)
    tracker.record_tool_error("terminal")
    tracker.record_tool_error("read_file")
    assert tracker.should_nudge() is True
```

**Step 2: Run test to verify failure**

```bash
python -m pytest tests/run_agent/test_reflection_nudge.py -q
```

Expected: FAIL because helper does not exist.

**Step 3: Implement helper only**

Implement a pure, dependency-light helper that returns a one-shot system instruction like:

```text
Before finalizing, briefly reflect on what failed, whether a memory/skill update is warranted, and do not save anything unless it is durable.
```

Do not yet wire it into every model call until pure tests are green.

**Step 4: Integrate carefully**

Wire into `AIAgent.run_conversation()` at a point that does not break role alternation or prompt caching assumptions. Prefer appending to the next user/system context only when a trigger fires.

**Step 5: Verify targeted tests**

```bash
python -m pytest tests/run_agent/test_reflection_nudge.py tests/run_agent/test_memory_nudge_counter_hydration.py -q
```

Expected: PASS.

---

## Task 4: Add trajectory summaries for completed sessions

**Objective:** Store high-signal task summaries separately from raw transcripts: task, outcome, skills used, failures, and follow-up opportunities.

**Files:**
- Modify: `hermes_state.py` or add `agent/trajectory_store.py`
- Modify: session completion path in `run_agent.py` / gateway session persistence
- Test: `tests/agent/test_trajectory_store.py`

**Step 1: Write failing storage tests**

```python
def test_trajectory_store_writes_summary(tmp_path):
    store = TrajectoryStore(tmp_path / "state.db")
    row_id = store.add(task="fix cron", outcome="ok", skills=["hermes-cron-operations"])
    row = store.get(row_id)
    assert row["task"] == "fix cron"
    assert row["skills"] == ["hermes-cron-operations"]
```

**Step 2: Run test to verify failure**

```bash
python -m pytest tests/agent/test_trajectory_store.py -q
```

Expected: FAIL because store does not exist.

**Step 3: Implement storage**

Use SQLite table in `state.db` or a dedicated `trajectories.db` under Hermes home:

```sql
CREATE TABLE IF NOT EXISTS trajectories (
  id INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL,
  session_id TEXT,
  source TEXT,
  task TEXT NOT NULL,
  outcome TEXT NOT NULL,
  skills_json TEXT NOT NULL DEFAULT '[]',
  summary TEXT NOT NULL,
  followups_json TEXT NOT NULL DEFAULT '[]'
)
```

Start without embeddings. Keep it reliable and queryable first.

**Step 4: Add search/read API**

Add a small read helper and tests for latest/search by task text. Use FTS later only if needed.

**Step 5: Verify**

```bash
python -m pytest tests/agent/test_trajectory_store.py -q
```

Expected: PASS.

---

## Task 5: Add gated skill rewrite suggestions

**Objective:** Surface rewrite suggestions for deprecated/high-failure skills, but never apply them automatically.

**Files:**
- Modify: `agent/curator.py`
- Modify: `tools/skill_manager_tool.py` only if needed for draft patches
- Test: `tests/agent/test_curator_skill_rewrite_suggestions.py`

**Step 1: Write failing tests**

Create a fake deprecated skill record with `needs_rewrite=true`, then assert curator dry-run/report includes:

```python
assert "rewrite suggested" in report
assert "skill_manage(action='patch'" in report or suggested next action is structured
```

**Step 2: Run test to verify failure**

```bash
python -m pytest tests/agent/test_curator_skill_rewrite_suggestions.py -q
```

Expected: FAIL because curator ignores `quality_state`/`needs_rewrite`.

**Step 3: Implement report-only suggestion**

Curator should list deprecated skills and include:

- skill name
- success/failure counts
- recent activity timestamps
- suggested next step: inspect recent sessions and patch skill manually

No automatic LLM rewrite yet.

**Step 4: Add optional explicit command later**

Only after report-only behavior is stable, consider:

```bash
hermes curator suggest-rewrite SKILL_NAME --dry-run
```

This should produce a proposed patch for approval, not apply it.

**Step 5: Verify**

```bash
python -m pytest tests/agent/test_curator_skill_rewrite_suggestions.py tests/agent/test_curator_reports.py -q
```

Expected: PASS.

---

## Task 6: Documentation and Harvey operating convention

**Objective:** Make the behavior understandable and safe for future Harvey sessions.

**Files:**
- Modify: `website/docs/user-guide/features/curator.md`
- Modify or create: `docs/harvey-self-improvement.md`
- Optional skill patch: `~/.hermes/skills/devops/hermes-cron-operations/SKILL.md` only if cron-related lessons are discovered.

**Step 1: Write docs update**

Explain:

- activity lifecycle vs quality lifecycle
- when to call `skill_rate`
- how `deprecated` differs from archived/deleted
- rewrite suggestions are gated/manual

**Step 2: Verify docs links/build if relevant**

```bash
python -m pytest tests/tools/test_skill_usage_outcomes.py -q
```

If docs site dependencies are available:

```bash
cd website && npm run build
```

---

## Rollout order

1. Foundation outcome telemetry — already started.
2. Visible curator status/reporting.
3. Manual `skill_rate` tool.
4. Reflection nudges.
5. Trajectory summaries.
6. Gated rewrite suggestions.
7. Docs.

## Safety notes

- Do not auto-delete skills.
- Do not auto-apply rewrites.
- Keep `state` and `quality_state` separate to avoid breaking existing stale/archive curator behavior.
- Keep outcome tracking best-effort except invalid direct API calls; tool-facing wrappers should return structured errors.
- Run targeted pytest after each task; run wider curator/skills tests before merging.
