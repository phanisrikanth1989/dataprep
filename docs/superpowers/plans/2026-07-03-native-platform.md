# Native Platform (v1.122 subagents + skills) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build the VS Code 1.122 native platform that turns a recon requirement into a validated DataPrep job: an orchestrator custom-agent that autonomously drives six subagent-only specialists via `runSubagent`, backed by the recon knowledge as an Agent Skill, a per-run audit log, and the plan-3 harness as the deterministic PASS/FAIL — all model-agnostic.

**Architecture:** Deterministic Python (built + unit-tested here): `render_skills` turns the plan-2 curated schemas (enum_refs resolved to concrete value lists) + landmines + the job-envelope contract into a `.github/skills/dataprep-recon/` Agent Skill; `audit_log` records every run step; `validate_agents` gates the authored `.agent.md`/`SKILL.md` frontmatter. Authored artifacts (reviewed, not unit-run): six `.github/agents/*.agent.md` specialists + one orchestrator, whose instructions encode the free-agent loop + human gate. The **live subagent orchestration only runs inside Citi's VS Code Copilot** — this plan builds to that boundary and ships a Citi-verification checklist; local tests cover the deterministic tooling + the frontmatter gate.

**Tech Stack:** Python 3.12, stdlib + `PyYAML` (already a project dep), `pytest`. Consumes plan-2 (`agents/tools/component_schema.py`, `agents/knowledge/landmines.py`) and plan-3 (`agents/tools/{extract_doc,validate_config,run_and_validate}.py` CLIs).

## Global Constraints

- **Python 3.12+.** ASCII-only in all code, logs, and authored markdown (RHEL-clean).
- **No NEW third-party dependency** — stdlib + `PyYAML` (existing) + the plan-1/2/3 tools.
- **Model-agnostic (hard rule):** NO `model:` key in ANY `.agent.md`. `validate_agents` enforces this. Agents inherit the user's picker selection.
- **v1.122 native layout:** agents in `.github/agents/<name>.agent.md`; skills in `.github/skills/<name>/SKILL.md`. `.agent.md` frontmatter keys used: `name`, `description`, `tools` (array), `agents` (array, orchestrator only), `user-invocable` (bool), `disable-model-invocation` (bool). `SKILL.md` frontmatter: `name` (lowercase-alphanumeric-hyphens, matches folder, 1-64 chars), `description` (what+when, <=1024 chars).
- **No per-agent skill scoping in VS Code** — skills are workspace-global; each agent references the skill BY NAME in its instructions.
- **Free-agent loop with deterministic safety nets:** the orchestrator improvises delegation/stop; but pass/fail is the plan-3 harness (never LLM judgment), every step is audit-logged, and the final `job.json` passes a human gate.
- **Job-envelope contract (from plan-3 Task 4, engine-verified):** each component `schema` = `{"input":[...],"output":[...]}`; `flows` = `{"name","type":"flow","from","to"}` with each component carrying `inputs`/`outputs` referencing flow names; each component has a `subjob_id`. The Assembler emits this; the skill documents it.
- **Tool IDs in `.agent.md` follow the v1.122 docs** (`agent/runSubagent`, terminal/read/edit tools). `validate_agents` checks STRUCTURE, not that a tool ID resolves in a live install; PLATFORM.md lists tool-ID verification as a Citi step.
- Public functions/classes carry docstrings; per-module `logging.getLogger(__name__)`.

## File Structure

- `agents/tools/audit_log.py` — `AuditLog` (per-run JSONL record).
- `agents/tools/validate_agents.py` — frontmatter validator for `.agent.md` + `SKILL.md`.
- `agents/tools/render_skills.py` — render the plan-2 knowledge into the `dataprep-recon` skill.
- `.github/skills/dataprep-recon/SKILL.md` (+ `config-reference.md`, `landmines.md`, `job-envelope.md`) — generated + authored.
- `.github/agents/{doc-interpreter,flow-designer,configurator,assembler,test-runner,diagnostician}.agent.md` — the six specialists.
- `.github/agents/etl-orchestrator.agent.md` — the orchestrator.
- `agents/PLATFORM.md` — install + run + Citi-verification checklist.
- Tests under `tests/agents/tools/`.

---

### Task 1: `audit_log` — per-run structured audit trail

**Files:**
- Create: `agents/tools/audit_log.py`
- Test: `tests/agents/tools/test_audit_log.py`

**Interfaces:**
- Produces: `AuditLog(job_dir)` with `record(iteration: int, role: str, event: str, detail: dict | None = None) -> None` (appends one JSON object per line to `<job_dir>/audit.jsonl`, each `{"iteration","role","event","detail"}`), and `read() -> list[dict]` (parse the file back; `[]` if absent). ASCII-only JSON.

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/tools/test_audit_log.py
from agents.tools.audit_log import AuditLog


def test_record_and_read_roundtrip(tmp_path):
    log = AuditLog(str(tmp_path))
    log.record(1, "configurator", "artifact_written", {"file": "job_draft.json"})
    log.record(1, "test-runner", "oracle_verdict", {"passed": False, "reasons": ["output matched differs"]})
    rows = log.read()
    assert len(rows) == 2
    assert rows[0] == {"iteration": 1, "role": "configurator", "event": "artifact_written",
                       "detail": {"file": "job_draft.json"}}
    assert rows[1]["detail"]["passed"] is False


def test_read_missing_is_empty(tmp_path):
    assert AuditLog(str(tmp_path / "nope")).read() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_audit_log.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agents.tools.audit_log'`

- [ ] **Step 3: Write minimal implementation**

```python
# agents/tools/audit_log.py
"""Per-run structured audit trail for the ETL orchestration (one JSON line per step)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class AuditLog:
    """Append-only JSONL audit trail under a job's work dir."""

    def __init__(self, job_dir: str):
        self._path = Path(job_dir) / "audit.jsonl"

    def record(self, iteration: int, role: str, event: str, detail: dict | None = None) -> None:
        """Append one audit entry: {iteration, role, event, detail}."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"iteration": iteration, "role": role, "event": event, "detail": detail or {}}
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")

    def read(self) -> list:
        """Return all audit entries (empty list if the log does not exist)."""
        if not self._path.exists():
            return []
        with self._path.open(encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_audit_log.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add agents/tools/audit_log.py tests/agents/tools/test_audit_log.py
git commit -m "feat(agents): per-run structured audit log"
```

---

### Task 2: `validate_agents` — `.agent.md` / `SKILL.md` frontmatter gate

**Files:**
- Create: `agents/tools/validate_agents.py`
- Test: `tests/agents/tools/test_validate_agents.py`

**Interfaces:**
- Produces:
  - `parse_frontmatter(text: str) -> dict` — extract + `yaml.safe_load` the leading `---`-delimited YAML block (raises `ValueError` if absent/malformed).
  - `validate_agent(text: str, filename: str) -> list[str]` — errors for a `.agent.md`: missing `name`/`description`; **presence of a `model:` key** (model-agnostic violation); `tools`/`agents` not a list when present; `user-invocable`/`disable-model-invocation` not a bool when present.
  - `validate_skill(text: str, dirname: str) -> list[str]` — errors for a `SKILL.md`: missing `name`/`description`; `name` not matching `dirname`; `name` not lowercase-alphanumeric-hyphen or >64 chars; `description` >1024 chars.
  - `validate_tree(agents_dir, skills_dir) -> list[str]` — validate every `*.agent.md` and every `*/SKILL.md`, PLUS cross-check: every name in an orchestrator's `agents:` list resolves to an existing agent `name`. Returns all errors (empty = clean).

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/tools/test_validate_agents.py
from agents.tools.validate_agents import validate_agent, validate_skill, parse_frontmatter

_GOOD_AGENT = """---
name: configurator
description: Fills component config for a recon job.
tools: ['edit/files', 'search/codebase']
user-invocable: false
---
You configure components.
"""

_MODEL_PINNED = """---
name: bad
description: has a model pin
model: Claude Opus 4.7
---
body
"""


def test_parse_frontmatter_ok():
    assert parse_frontmatter(_GOOD_AGENT)["name"] == "configurator"


def test_good_agent_has_no_errors():
    assert validate_agent(_GOOD_AGENT, "configurator.agent.md") == []


def test_model_key_is_flagged():
    errs = validate_agent(_MODEL_PINNED, "bad.agent.md")
    assert any("model" in e for e in errs)


def test_missing_description_flagged():
    text = "---\nname: x\n---\nbody\n"
    assert any("description" in e for e in validate_agent(text, "x.agent.md"))


def test_skill_name_must_match_dir():
    text = "---\nname: other-name\ndescription: d\n---\nbody\n"
    assert any("match" in e for e in validate_skill(text, "dataprep-recon"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_validate_agents.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agents.tools.validate_agents'`

- [ ] **Step 3: Write minimal implementation**

```python
# agents/tools/validate_agents.py
"""Validate authored .agent.md / SKILL.md frontmatter against the v1.122 schema.

Structural + model-agnostic gate; it does NOT verify that a tool id resolves in
a live VS Code install (that is a Citi-side check, see PLATFORM.md).
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_NAME_RE = re.compile(r"^[a-z0-9-]{1,64}$")


def parse_frontmatter(text: str) -> dict:
    """Return the leading ----delimited YAML frontmatter as a dict."""
    if not text.startswith("---"):
        raise ValueError("no frontmatter block")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("unterminated frontmatter block")
    data = yaml.safe_load(parts[1])
    if not isinstance(data, dict):
        raise ValueError("frontmatter is not a mapping")
    return data


def _common(fm: dict, errors: list) -> None:
    if not fm.get("name"):
        errors.append("missing 'name'")
    if not fm.get("description"):
        errors.append("missing 'description'")


def validate_agent(text: str, filename: str) -> list:
    """Return frontmatter errors for a .agent.md (empty = valid)."""
    errors: list = []
    try:
        fm = parse_frontmatter(text)
    except ValueError as exc:
        return [f"{filename}: {exc}"]
    _common(fm, errors)
    if "model" in fm:
        errors.append("'model' key is forbidden (model-agnostic: omit it)")
    for key in ("tools", "agents"):
        if key in fm and not isinstance(fm[key], list):
            errors.append(f"'{key}' must be a list")
    for key in ("user-invocable", "disable-model-invocation"):
        if key in fm and not isinstance(fm[key], bool):
            errors.append(f"'{key}' must be a boolean")
    return [f"{filename}: {e}" for e in errors]


def validate_skill(text: str, dirname: str) -> list:
    """Return frontmatter errors for a SKILL.md (empty = valid)."""
    errors: list = []
    try:
        fm = parse_frontmatter(text)
    except ValueError as exc:
        return [f"{dirname}/SKILL.md: {exc}"]
    _common(fm, errors)
    name = fm.get("name", "")
    if name and name != dirname:
        errors.append(f"name {name!r} must match dir {dirname!r}")
    if name and not _NAME_RE.match(name):
        errors.append(f"name {name!r} must be lowercase-alphanumeric-hyphen, <=64 chars")
    if len(str(fm.get("description", ""))) > 1024:
        errors.append("description exceeds 1024 chars")
    return [f"{dirname}/SKILL.md: {e}" for e in errors]


def validate_tree(agents_dir, skills_dir) -> list:
    """Validate all agents + skills and cross-check orchestrator `agents:` references."""
    errors: list = []
    agents_dir, skills_dir = Path(agents_dir), Path(skills_dir)
    names = set()
    allowlists = []
    for af in sorted(agents_dir.glob("*.agent.md")):
        text = af.read_text(encoding="utf-8")
        errors.extend(validate_agent(text, af.name))
        try:
            fm = parse_frontmatter(text)
            if fm.get("name"):
                names.add(fm["name"])
            if isinstance(fm.get("agents"), list):
                allowlists.append((af.name, fm["agents"]))
        except ValueError:
            pass
    for sd in sorted(p for p in skills_dir.glob("*") if p.is_dir()):
        sf = sd / "SKILL.md"
        if sf.exists():
            errors.extend(validate_skill(sf.read_text(encoding="utf-8"), sd.name))
    for fname, allow in allowlists:
        for ref in allow:
            if ref != "*" and ref not in names:
                errors.append(f"{fname}: agents: references unknown agent {ref!r}")
    return errors
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_validate_agents.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add agents/tools/validate_agents.py tests/agents/tools/test_validate_agents.py
git commit -m "feat(agents): .agent.md/SKILL.md frontmatter validator (model-agnostic gate)"
```

---

### Task 3: `render_skills` — render plan-2 knowledge into the `dataprep-recon` skill

**Files:**
- Create: `agents/tools/render_skills.py`
- Create (generated): `.github/skills/dataprep-recon/{SKILL.md, config-reference.md, landmines.md, job-envelope.md}`
- Test: `tests/agents/tools/test_render_skills.py`

**Interfaces:**
- Consumes: `agents.tools.component_schema.load_schema`/`resolve_enum_ref`/`_index`, `agents.knowledge.landmines.LANDMINES`.
- Produces:
  - `render_config_reference() -> str` — a markdown section per curated component: its keys with type/default/required and, for enum/enum_ref keys, the **resolved value list** (never the `enum_ref` pointer).
  - `render_landmines() -> str` — a markdown list of every landmine (`id`, component, summary, guidance).
  - `render_job_envelope() -> str` — the fixed job-envelope contract text (schema input/output, flows type:flow+name+inputs/outputs, subjob_id) with a minimal example.
  - `write_skill(root=".github/skills/dataprep-recon") -> None` — write `SKILL.md` (frontmatter `name: dataprep-recon` + a description + pointers to the resources) and the three resource files.

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/tools/test_render_skills.py
from agents.tools.render_skills import render_config_reference, render_landmines, write_skill
from agents.tools.validate_agents import validate_skill


def test_config_reference_resolves_enum_refs_not_pointers():
    md = render_config_reference()
    assert "FilterRows" in md
    assert "IS_NULL" in md and "==" in md          # live _OPERATOR_MAP values, resolved
    assert "_OPERATOR_MAP" not in md               # the pointer must NOT leak into the skill


def test_landmines_rendered():
    md = render_landmines()
    assert "tmap-operator-noop" in md and "die-on-error-dual-default" in md


def test_write_skill_produces_valid_skill(tmp_path):
    root = tmp_path / "dataprep-recon"
    write_skill(str(root))
    skill_md = (root / "SKILL.md").read_text(encoding="utf-8")
    assert validate_skill(skill_md, "dataprep-recon") == []
    assert (root / "config-reference.md").exists()
    assert (root / "job-envelope.md").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_render_skills.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agents.tools.render_skills'`

- [ ] **Step 3: Write minimal implementation + generate the skill**

Implement `agents/tools/render_skills.py`:
```python
"""Render the plan-2 curated knowledge into the workspace-global dataprep-recon Agent Skill.

enum_ref pointers are resolved to concrete value lists so an agent reading the
skill sees the real allowed values, not a Python import path.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from agents.knowledge.landmines import LANDMINES
from agents.tools.component_schema import _SCHEMA_DIR, load_schema, resolve_enum_ref

logger = logging.getLogger(__name__)


def _index() -> dict:
    with (_SCHEMA_DIR / "_index.json").open(encoding="utf-8") as fh:
        return json.load(fh)


def _resolved_values(spec: dict):
    if "enum" in spec:
        return [v for v in spec["enum"]]
    if "enum_ref" in spec:
        return sorted(resolve_enum_ref(spec["enum_ref"]), key=str)
    return None


def _render_keys(keys: dict, indent: str = "") -> list:
    lines = []
    for name, spec in keys.items():
        bits = [f"type={spec.get('type', 'any')}"]
        if "default" in spec:
            bits.append(f"default={spec['default']!r}")
        if spec.get("required"):
            bits.append("REQUIRED")
        vals = _resolved_values(spec)
        if vals is not None:
            bits.append("one of " + ", ".join(str(v) for v in vals))
        lines.append(f"{indent}- `{name}`: {'; '.join(bits)}")
        if spec.get("type") == "list" and isinstance(spec.get("item_keys"), dict):
            lines.append(f"{indent}  items:")
            lines.extend(_render_keys(spec["item_keys"], indent + "    "))
    return lines


def render_config_reference() -> str:
    """Markdown reference of every curated component's config keys (enum_refs resolved)."""
    files = sorted(set(_index().values()))
    out = ["# Component config reference (code-verified)", ""]
    for filename in files:
        schema = json.loads((_SCHEMA_DIR / filename).read_text(encoding="utf-8"))
        out.append(f"## {schema['type']}")
        aliases = schema.get("aliases", [])
        if aliases:
            out.append(f"Aliases: {', '.join(aliases)}")
        out.extend(_render_keys(schema.get("keys", {})))
        out.append("")
    return "\n".join(out)


def render_landmines() -> str:
    """Markdown list of the code-verified config landmines."""
    out = ["# Config landmines (respect these)", ""]
    for lm in LANDMINES:
        comp = lm.get("component") or "GLOBAL"
        out.append(f"- **{lm['id']}** ({comp}): {lm['summary']}")
        out.append(f"  - guidance: {lm['guidance']}")
    return "\n".join(out)


def render_job_envelope() -> str:
    """The engine-verified job.json envelope contract (from plan-3 Task 4)."""
    return (
        "# Job envelope contract (engine-verified)\n\n"
        "Every component needs a `subjob_id`. Component `schema` is "
        "`{\"input\": [...], \"output\": [...]}` (NOT a flat list). Flows are "
        "`{\"name\": <flow>, \"type\": \"flow\", \"from\": <id>, \"to\": <id>}` and each "
        "component carries `inputs`/`outputs` lists referencing flow names. `type:\"main\"` "
        "on a flow routes NOTHING; use `\"flow\"`. tMap one-sided breaks use an output with "
        "`inner_join_reject: true` (NOT `is_reject`, which stays empty for a join miss).\n"
    )


_SKILL_FRONTMATTER = (
    "---\n"
    "name: dataprep-recon\n"
    "description: >-\n"
    "  Code-verified knowledge for building DataPrep recon ETL jobs: per-component config keys and\n"
    "  allowed values, config landmines, the job.json envelope contract, and the tMap match/break\n"
    "  patterns. Use when interpreting a recon requirement, designing the flow, configuring components,\n"
    "  or assembling/repairing a recon job.json.\n"
    "---\n"
)


def write_skill(root: str = ".github/skills/dataprep-recon") -> None:
    """Write SKILL.md + the three resource files for the dataprep-recon skill."""
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    (root_path / "config-reference.md").write_text(render_config_reference(), encoding="utf-8")
    (root_path / "landmines.md").write_text(render_landmines(), encoding="utf-8")
    (root_path / "job-envelope.md").write_text(render_job_envelope(), encoding="utf-8")
    body = (
        _SKILL_FRONTMATTER
        + "# DataPrep recon knowledge\n\n"
        "Load the resource that fits the task:\n\n"
        "- `config-reference.md` - every allowed component config key + its resolved allowed values.\n"
        "- `landmines.md` - config traps that silently produce wrong output; respect each.\n"
        "- `job-envelope.md` - the exact job.json wiring shape the engine requires.\n\n"
        "Validate any component config with `python -m agents.tools.validate_config --type T --config c.json` "
        "and test a whole job with `python -m agents.tools.run_and_validate --job job.json --golden-dir DIR` "
        "before claiming it is correct.\n"
    )
    (root_path / "SKILL.md").write_text(body, encoding="utf-8")
    logger.info("[render_skills] wrote dataprep-recon skill to %s", root)


if __name__ == "__main__":
    write_skill()
```
Then GENERATE the committed skill: run `python -m agents.tools.render_skills` (writes `.github/skills/dataprep-recon/`).

- [ ] **Step 4: Run test to verify it passes + generate**

Run: `python -m pytest tests/agents/tools/test_render_skills.py -v` (PASS, 3 tests), then `python -m agents.tools.render_skills` and confirm `.github/skills/dataprep-recon/SKILL.md` + the 3 resource files exist and `python -c "from agents.tools.validate_agents import validate_skill; import pathlib; print(validate_skill(pathlib.Path('.github/skills/dataprep-recon/SKILL.md').read_text(), 'dataprep-recon'))"` prints `[]`.

- [ ] **Step 5: Commit**

```bash
git add agents/tools/render_skills.py tests/agents/tools/test_render_skills.py .github/skills/dataprep-recon
git commit -m "feat(agents): render dataprep-recon Agent Skill from code-verified knowledge"
```

---

### Task 4: The six specialist agents

**Files:**
- Create: `.github/agents/{doc-interpreter,flow-designer,configurator,assembler,test-runner,diagnostician}.agent.md`
- Test: `tests/agents/tools/test_specialist_agents.py`

**Interfaces:**
- Consumes: `validate_agents.validate_agent`. Each file's frontmatter: `name`, `description`, `tools` (array), `user-invocable: false`, `disable-model-invocation: false`, NO `model:`. Each body encodes the role's job, its input/output artifact (under `agents/work/<job>/`), and which the `dataprep-recon` skill to consult.

- [ ] **Step 1: Author the six agents**

Author each `.agent.md` per the spec roster (Sec 5) + the pivot. Every file: frontmatter with `user-invocable: false`, `disable-model-invocation: false`, NO `model:`, a narrow `tools` list, and a body (ASCII) covering: role responsibility, the input artifact it reads + the output artifact it writes (JSON, under `agents/work/<job>/`), the contracts (below), and "consult the `dataprep-recon` skill" where knowledge is needed.
- `doc-interpreter` (tools: read/edit/search): reads the `extract_doc` JSON artifact -> writes `requirement_spec.json` (schema + rules with `kind/cardinality/keys/direction/on_tolerance_fail/duplicate_disposition`, per spec Sec 5.2) + the derived facts; flags ambiguity for the human.
- `flow-designer` (tools: read/edit/search): reads `requirement_spec.json` -> writes `flow_plan.json` (components + the recon pattern); picks from the allowlist (Sec 11.2); tMap is the match primitive.
- `configurator` (tools: read/edit): reads `flow_plan.json` + the skill -> writes `job_draft.json` (`{components:[{id,type,config,schema}]}`); MUST run `python -m agents.tools.validate_config` on each component and fix every error before finishing.
- `assembler` (tools: read/edit): reads `job_draft.json` -> writes `job.json` adding the **job-envelope** (`flows` type:flow+name, per-component `inputs`/`outputs`, `subjob_id`, `schema` as `{input,output}`) per `job-envelope.md`. Wiring only.
- `test-runner` (tools: terminal only): runs `python -m agents.tools.run_and_validate --job job.json --golden-dir DIR`, returns the `test_report.json` verdict verbatim. Makes NO judgment about correctness — the harness decides.
- `diagnostician` (tools: read/edit): reads a FAILED `test_report.json` -> writes `feedback.json` naming the likely owner stage + a value-blind why/fix (per spec Sec 9 owner routing). Does not see raw data values.

- [ ] **Step 2: Write the failing gate test**

```python
# tests/agents/tools/test_specialist_agents.py
from pathlib import Path

from agents.tools.validate_agents import validate_agent, parse_frontmatter

_AGENTS = Path(".github/agents")
_SPECIALISTS = ["doc-interpreter", "flow-designer", "configurator", "assembler",
                "test-runner", "diagnostician"]


def test_all_specialists_exist_and_valid():
    for name in _SPECIALISTS:
        f = _AGENTS / f"{name}.agent.md"
        assert f.exists(), f"missing {f}"
        text = f.read_text(encoding="utf-8")
        assert validate_agent(text, f.name) == []
        fm = parse_frontmatter(text)
        assert fm["name"] == name
        assert fm.get("user-invocable") is False          # subagent-only
        assert "model" not in fm                            # model-agnostic
```

- [ ] **Step 3: Run test to verify it fails then passes**

Run: `python -m pytest tests/agents/tools/test_specialist_agents.py -v`
Expected: FAIL first (files absent), then PASS once all six are authored and pass `validate_agent`.

- [ ] **Step 4: Commit**

```bash
git add .github/agents/doc-interpreter.agent.md .github/agents/flow-designer.agent.md .github/agents/configurator.agent.md .github/agents/assembler.agent.md .github/agents/test-runner.agent.md .github/agents/diagnostician.agent.md tests/agents/tools/test_specialist_agents.py
git commit -m "feat(agents): six subagent-only recon specialists (.agent.md)"
```

---

### Task 5: The orchestrator agent

**Files:**
- Create: `.github/agents/etl-orchestrator.agent.md`
- Test: `tests/agents/tools/test_orchestrator_agent.py`

**Interfaces:**
- Consumes: `validate_agents.validate_tree`. Frontmatter: `name: etl-orchestrator`, `description`, `tools` (array incl. the subagent tool `agent/runSubagent` + a terminal tool), `agents` (array = the six specialist names), `user-invocable: true`, NO `model:`. Body = the free-agent loop + safety rules + human gate.

- [ ] **Step 1: Author the orchestrator**

Author `.github/agents/etl-orchestrator.agent.md`. Frontmatter as above (`agents:` lists exactly the six specialist `name`s). Body (ASCII) must encode:
- **The loop:** delegate via `#runSubagent` in order doc-interpreter -> flow-designer -> configurator -> assembler -> test-runner; on a FAILED `test_report.json`, delegate to diagnostician, then re-run the owner stage it names; repeat at most **3** iterations.
- **Safety nets (non-negotiable):** correctness is ONLY the `test-runner`/harness verdict, never the orchestrator's own reading of the data; call `AuditLog.record` (via `python -m agents.tools.audit_log`-style logging or by writing to `agents/work/<job>/audit.jsonl`) at each step; on green OR budget-exhausted, STOP and present the `job.json` + `test_report.json` to the human for approval — never auto-approve.
- **Artifact bus:** every stage reads/writes JSON under `agents/work/<job>/`.
- **Knowledge:** instruct stages to consult the `dataprep-recon` skill.

- [ ] **Step 2: Write the failing gate test**

```python
# tests/agents/tools/test_orchestrator_agent.py
from pathlib import Path

from agents.tools.validate_agents import parse_frontmatter, validate_tree

_AGENTS = Path(".github/agents")
_SKILLS = Path(".github/skills")


def test_orchestrator_valid_and_references_all_specialists():
    text = (_AGENTS / "etl-orchestrator.agent.md").read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    assert fm["name"] == "etl-orchestrator"
    assert fm.get("user-invocable") is True
    assert "model" not in fm
    allow = fm["agents"]
    for name in ["doc-interpreter", "flow-designer", "configurator", "assembler",
                 "test-runner", "diagnostician"]:
        assert name in allow
    # human gate + harness-decides must be stated in the body
    low = text.lower()
    assert "human" in low and "approv" in low
    assert "run_and_validate" in text or "test-runner" in low


def test_whole_tree_validates():
    assert validate_tree(_AGENTS, _SKILLS) == []
```

- [ ] **Step 3: Run test to verify it fails then passes**

Run: `python -m pytest tests/agents/tools/test_orchestrator_agent.py -v`
Expected: FAIL first, then PASS once the orchestrator is authored; `validate_tree` returns `[]` (all agents + skills valid, `agents:` references resolve).

- [ ] **Step 4: Commit**

```bash
git add .github/agents/etl-orchestrator.agent.md tests/agents/tools/test_orchestrator_agent.py
git commit -m "feat(agents): etl-orchestrator (free-agent loop + human gate + audit)"
```

---

### Task 6: PLATFORM.md + Citi-verification checklist

**Files:**
- Create: `agents/PLATFORM.md`
- Test: `tests/agents/tools/test_platform_doc.py`

**Interfaces:**
- `PLATFORM.md` documents: the architecture (orchestrator + 6 specialists + skill + harness); how to run (open the orchestrator agent in Copilot, point it at a requirements doc); and a **Citi-verification checklist** — the things that can only be confirmed in the 1.122 install (the exact `tools:` ids resolve; `#runSubagent` fires against the `agents:` allowlist; Opus/any model in the picker; `chat.tools.terminal.autoApprove` allows the `python -m agents.tools.*` commands; the skill auto-loads by description). It also records that the LIVE loop is Citi-verified, not locally tested.

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/tools/test_platform_doc.py
from pathlib import Path


def test_platform_doc_has_citi_checklist_and_run_commands():
    text = Path("agents/PLATFORM.md").read_text(encoding="utf-8")
    low = text.lower()
    assert "citi" in low and "checklist" in low
    assert "runsubagent" in low
    assert "run_and_validate" in text          # names the deterministic harness command
    assert "terminal" in low and "autoapprove" in low.replace(" ", "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_platform_doc.py -v`
Expected: FAIL (file absent)

- [ ] **Step 3: Author `agents/PLATFORM.md`** covering the sections above (ASCII), then run the test to PASS.

- [ ] **Step 4: Full gate + commit**

Run the whole suite: `python -m pytest tests/agents/ -v` (all green) and `python -c "from agents.tools.validate_agents import validate_tree; print(validate_tree('.github/agents', '.github/skills'))"` (prints `[]`).

```bash
git add agents/PLATFORM.md tests/agents/tools/test_platform_doc.py
git commit -m "docs(agents): PLATFORM.md + Citi-verification checklist"
```

---

## Self-Review

**1. Spec coverage:** native orchestrator + 6 specialists via runSubagent (pivot) — Tasks 4,5. Knowledge as an Agent Skill with enum_refs resolved (pivot adapter) — Task 3. Audit log (safety net) — Task 1. Human gate + harness-decides-correctness (free-agent loop safety nets) — Task 5. Job-envelope contract for the Assembler (plan-3 Task 4) — Tasks 3,4. Model-agnostic enforced — Task 2 + gate tests. Owner-routing diagnostician (Sec 9) — Task 4. Citi-verify boundary for the live loop — Task 6.

**2. Placeholder scan:** no TBD/TODO; Tasks 1-3 have complete code; Tasks 4-6 are authoring tasks bounded by the spec roster + the `validate_agents`/`validate_tree` gate + the reviewer, exactly like plan-2's schema authoring.

**3. Type consistency:** `AuditLog.record/read`, `parse_frontmatter`/`validate_agent`/`validate_skill`/`validate_tree`, `render_config_reference`/`render_landmines`/`render_job_envelope`/`write_skill`, and the frontmatter key set (`name`/`description`/`tools`/`agents`/`user-invocable`, no `model`) are consistent across tasks.

## Boundary note (verified in Citi, not here)
The live subagent orchestration (the actual `#runSubagent` loop, model selection, terminal auto-approve, skill auto-load) runs only inside the 1.122 Copilot host. This plan builds + unit-tests the deterministic tooling and gates the authored artifacts' structure; PLATFORM.md's checklist is the acceptance for the live behavior.
