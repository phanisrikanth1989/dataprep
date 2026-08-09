# 11 - Engine knowledge in the owned runtime

Status: open
Type: grilling

## Question

How do the rebuilt/vendored specialists receive the engine knowledge that the
Copilot world served as the `dataprep-etl` Agent Skill -- `config-reference.md`
(resolved enums), `landmines.md`, `job-envelope.md`, and the SKILL index --
now that there is no skill auto-load?

To settle:

- Injection mechanism: per-stage system prompts assembled by the core,
  on-demand file reads via a tool, or both.
- Which stage gets which slice (flow-designer vs configurator vs assembler vs
  diagnostician need different cuts; oversized prompts burn credits).
- Freshness: `render_skills` code-generates the knowledge from live schemas --
  when does the owned runtime regenerate, and what guards drift?
- Where the rendered knowledge lives under `demo/etl_studio/` (vendored copy
  vs generated at build/startup).

(Graduated from the "how rebuilt agents receive the engine knowledge" fog by
ticket 04's stage roster.)
