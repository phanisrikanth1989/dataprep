# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring
the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root — the glossary / ubiquitous language.
- **`docs/adr/`** — read the ADRs that touch the area you're about to work in.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't
suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs`
and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually
get resolved. Neither exists in this repo yet — that is expected.

## File structure

This is a **single-context** repo:

```
/
├── CONTEXT.md
├── docs/adr/
│   ├── 0001-py4j-arrow-java-bridge.md
│   └── 0002-converter-json-format-frozen.md
└── src/
```

If the repo ever splits into genuinely separate contexts, add a root `CONTEXT-MAP.md`
pointing at one `CONTEXT.md` per context (plus optional `src/<context>/docs/adr/` for
context-scoped decisions) and update this file.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a
hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms
the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing
language the project doesn't use (reconsider) or there's a real gap (note it for
`/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently
overriding:

> _Contradicts ADR-0007 (event-sourced orders) — but worth reopening because…_
