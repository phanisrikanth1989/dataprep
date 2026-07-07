# Copilot ETL Agents — VS Code 1.122 Platform Pivot (decision record)

*Date: 2026-07-03. User-approved. Supersedes the 1.106 platform assumptions in the v3.1 design spec (`2026-07-03-copilot-etl-agents-design.md`) sections 4, 6.3, 7-9, 12, and adds a threat-model decision to section 2. Fold into that spec next; this file is the authoritative delta until then.*

## Trigger
Citi VS Code updated **1.106 -> v1.122.1**. Every 1.106 platform constraint the original design worked around is now lifted. Verified against primary docs: native subagents GA (~1.109), Agent Skills GA + on-by-default (1.109), custom-agent-as-subagent GA at 1.122, MCP sampling now deprecated (MCP spec SEP-2577). User confirmed on their actual install: `#runSubagent` present and custom-agent-as-subagent works with NO experimental flag; Claude Opus is in the model picker; `chat.tools.terminal.autoApprove` is editable.

## Decisions (all user-approved 2026-07-03)

1. **Native architecture, not MCP-emulated.** An orchestrator custom-agent with an `agents:` allowlist drives 6 subagent-only specialists via the built-in `agent/runSubagent` tool. Domain knowledge lives as native `.github/skills/` `SKILL.md` modules. Deterministic Python tools are invoked via auto-approved terminal. **The MCP server + `sampling/createMessage` are DROPPED** (native subagents supersede them; sampling is deprecated regardless).

2. **Model-agnostic (locked).** OMIT `model:` from every `.agent.md` so each agent inherits the user's picker selection. Opus is allowed but usage-control is unknown; no premium-model dependency. See memory `model-agnostic-citi-copilot`.

3. **Free-agent loop** (user chose this over the prescribed-recipe option). The orchestrator improvises delegation and stop-conditions from its own judgment. Three orthogonal deterministic safety nets are retained: (a) pass/fail is the Python parity harness, NEVER LLM judgment; (b) a human gate on the final `job.json`; (c) an audit log of every run. Trivially tightenable to a prescribed recipe later if compliance requires -- a few lines in the orchestrator's instructions, no re-architecture.

4. **Don't minimize egress** (user chose this). Real recon sample/expected values MAY reach the model -- Citi's internal Copilot is the sanctioned enclave; the earlier "particular on data" meant no external servers/egress, which is still honored. Simplifies: `extract_doc` emits ONE JSON artifact (no two-artifact split), the harness verdict may include raw values (no redaction), and `agents/work/<job>/` is one flat agent-readable dir. `derived_facts` stays as a convenience summary, no longer a security boundary. Reversible: the split can be bolted on later.

## Native architecture
- `.github/agents/etl-orchestrator.agent.md` -- `user-invocable: true`; `tools:` includes `agent/runSubagent`; `agents:` allowlist naming the 6 specialists; NO `model:`. Instructions encode the free-agent loop + safety rules (use the harness for green/red, ~3 iterations then escalate, surface for human approval).
- 6 subagent-only specialists (`.github/agents/*.agent.md`, `user-invocable: false`, narrow `tools:`, NO `model:`): doc-interpreter, flow-designer, configurator, assembler, test-runner (runs the harness via terminal), diagnostician. Isolated context each; only results flow back.
- `.github/skills/*/SKILL.md` -- knowledge as progressive-disclosure skills, rendered from plan-2 (schemas with `enum_ref`s RESOLVED to concrete value lists, landmines, job-schema, authoring guidance). NOTE: VS Code has NO per-agent skill scoping (skills are workspace-global); agents bias to the right skill via their instructions.
- Artifact bus = `agents/work/<job>/` workspace files (all agent-readable).

## Code-grounded impact on the built work (verified by reading the final code 2026-07-03)
Plans 1-2 LOGIC is 100% reused -- no rewrite. But every built tool is an in-process Python API, and native subagents invoke via terminal + read files. Adapter layer to ADD:
- `agents/tools/extract_doc.py` -- `extract_doc() -> ExtractResult` dataclass; NO `__main__`/CLI/JSON output. ADD a CLI that writes one JSON artifact.
- `agents/tools/validate_config.py` -- `validate_config() -> list`; NO `__main__`. ADD a CLI.
- `agents/tools/component_schema.py` -- `enum_ref` stores POINTERS resolved only by `importlib` (lines 34-44); a subagent reading a schema JSON sees the pointer, not the values. ADD a "render schema with enum_refs resolved to value lists" step for the skills.
- `agents/knowledge/landmines.py` -- pure Python `LANDMINES` list. RENDER to `SKILL.md`/JSON.
- `agents/tools/check_schema_drift.py` -- already has `__main__` (fine; maintenance tool).
- Plan 3 (harness/oracle) unwritten -> design native-first (CLI + JSON verdict; verbose OK given the egress decision).

## Reshaped plan set
- Plans 1-2 built code: unchanged logic; ADD the adapter tasks (2 CLIs + enum-resolved schema render + landmines->skill).
- Plan 3: test harness + multi-signal oracle + reference matcher -- write native-first (CLI + JSON verdict).
- New Plan 4 (replaces old plans 4 + 5): the 7 custom agents + skills packaging + orchestrator instructions + human gate + audit log + terminal auto-approve wiring. MCP server + sampling deleted.

## Status
- Plan 1 (extract_doc) built + review-clean (through commit `fe67c19`).
- Plan 2 (knowledge layer) built + review-clean (`91bbaa7..800e404`; 45 `tests/agents/` green; drift clean over 116 fixture components).
- Design approved 2026-07-03.
- NEXT: fold these decisions into the main design spec (sections 2/4/6.3/7-9/12), user reviews the spec, then writing-plans for plan 3 (harness/oracle) + plan 4 (native platform) + the plan-1/2 adapter tasks.
