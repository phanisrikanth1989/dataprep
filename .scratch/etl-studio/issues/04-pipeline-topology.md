# 04 - Pipeline topology: what survives the re-host?

Status: open
Type: grilling
Blocked by: 02

## Question

Which stages, loops, tiers and gates of the current pipeline survive into the
owned runtime, and which change?

To settle:

- Stage list given the front door(s) decided in ticket 02.
- Artifact bus: keep file-based artifacts under a work dir, or in-memory with
  persisted snapshots?
- Bounded repair loops and the 3-iteration caps: keep the semantics?
- Verification tiers (verified/smoke/build): keep, simplify, or rethink now
  that a human is live in the loop?
- Diagnostician rebuild: charting judged its data-blind design useless -- the
  rebuilt diagnostician is value-visible. What does it read, and what does
  its feedback artifact look like?
- Data-blindness posture generally: which stages keep it (if any) and why.
