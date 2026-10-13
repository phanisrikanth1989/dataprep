---
status: accepted
date: 2026-08-09
---

# Two-layer orchestrator: code conductor under an LLM front

ETL Studio re-hosts a working Copilot pipeline — whose driver is an LLM
free-agent loop — onto an agent runtime we own. By the time the pipeline was
redesigned (wayfinder tickets 02/04), every between-stage decision was already
deterministic (fixed itinerary, loop counters, enumerated pause events, the
diagnostician's owner field), while a live human in the UI created a genuinely
model-shaped hub job: conversing. So the hub splits in two. A deterministic
**conductor** (code) computes every transition, enforces caps and gates, and
owns the question channel's events and resolutions; a persistent
**orchestrator** (LLM agent) fronts the run — non-blocking narration,
artifact-grounded answers to the human's questions, one voice over outgoing
prose, and propose-confirm on anything unplanned (free to stop, never to act
silently). A run's path cannot differ between rehearsal and the live demo;
only prose is sampled.

## Considered options

- **LLM hub (today's shape, re-hosted)** — rejected: the existing instruction
  file is a state machine written in English plus anti-deviation armor;
  re-deriving predetermined transitions with a model buys control-flow
  nondeterminism, per-transition latency, and a transcript-shaped
  crash-restart — and Copilot's free agent runtime does not come along in the
  re-host, so this was a build either way.
- **Pure code driver, no agent front** — rejected: the human can ask the
  studio questions mid-run and expects a narrated run in a single voice; that
  job needs a model, and it is the recognizable face of the multi-agent
  orchestrator pattern this team presents.

## Consequences

Rehearsal-grade replay needs only provider-port record/replay. The
orchestrator's authority can later widen to bounded autonomy (choosing among
legal moves unasked) as a policy change, not a re-architecture. Tickets 06/08
hang the thoughts stream and the message shapes off the conductor's events and
the orchestrator's prose channel. Full detail:
`.scratch/etl-studio/issues/05-orchestrator-llm-or-code.md`.
