# AGENTS.md — DataPrep

Shared agent instructions for this repo. Read by Claude Code, GitHub Copilot, and any
other coding agent that honours `AGENTS.md`.

> **Full project instructions live in [`CLAUDE.md`](./CLAUDE.md)** — architecture, tech
> stack, naming conventions, error handling, the coverage gate, and the git/branch rules
> (notably: never commit to `main`; stage files explicitly). Read it before changing code.
> This file covers only the agent-skill configuration layered on top.

## Agent skills

### Issue tracker

Issues live as markdown files under `.scratch/<feature-slug>/`, one file per ticket —
no GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical roles, each string equal to its name (`needs-triage`, `needs-info`,
`ready-for-agent`, `ready-for-human`, `wontfix`), recorded as a `Status:` line in each
issue file. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — a root `CONTEXT.md` plus `docs/adr/`, both created lazily.
See `docs/agents/domain.md`.
