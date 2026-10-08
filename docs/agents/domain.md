# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring
the codebase.

## Before exploring, read these

- **`CONTEXT-MAP.md`** at the repo root — lists the contexts. Read the `CONTEXT.md` of
  the one you're working in: ETL Studio's is the root `CONTEXT.md`, the v2 engine's is
  `src/v2/CONTEXT.md`.
- **`docs/adr/`** — read the ADRs that touch the area you're about to work in.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't
suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs`
and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually
get resolved. Neither exists in this repo yet — that is expected.

## File structure

This is a **multi-context** repo:

```
/
├── CONTEXT-MAP.md        ← lists the contexts and how they relate
├── CONTEXT.md            ← ETL Studio
├── docs/adr/             ← system-wide decisions
└── src/
    └── v2/
        └── CONTEXT.md    ← v2 engine
```

To add a context, give it its own `CONTEXT.md` and a line in `CONTEXT-MAP.md`.
Context-scoped decisions may live in `src/<context>/docs/adr/`.

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
