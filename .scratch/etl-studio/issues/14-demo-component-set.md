# 14 - Demo component set: pin and enrich to depth

Status: open
Type: task

## Question

Pin the demo component set -- the 10-15 components the product is thoroughly
tested for -- then verify and enrich the knowledge sources for each to
no-source-needed depth against `config-surfaces.md`, so no specialist ever
needs engine source for a set component (source access stays
diagnostician-only per ticket 11). The curated set already covers 12
components, so this is depth verification plus at most a few new curations,
not a breadth project.

**Explicitly deferred (user decision, 2026-08-09): do not start this ticket
until the entire product is developed and tested for those components.** It
is post-v1 hardening of the knowledge base, not a prerequisite for the build.
Ticket 11's delivery machinery absorbs enrichment without redesign: changes
land in the vendored knowledge sources and regenerate at every startup.

(Graduated from ticket 11's content-posture decision: fit-adaptation and
reactive fixes happen in v1; substantive enrichment happens here.)
