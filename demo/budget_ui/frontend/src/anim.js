// src/anim.js
// Shared animation timing so the graph build reads as ONE deliberate choreography:
// the scattered boxes settle into the chain ONE AT A TIME (staggered glide), each edge
// draws as its downstream node lands, and the code-execution gate rises only AFTER the
// whole pipeline is built. All values in seconds. Tune here -- every consumer stays in sync.

export const NODE_STAGGER = 0.5; // gap between consecutive node placements (the sequential chain build)
export const NODE_DUR = 0.7;     // one node's glide duration
export const EDGE_DUR = 0.6;     // one edge's draw duration
export const GATE_PAUSE = 0.9;   // pause after the LAST node lands, before the code gate appears

// Milliseconds from the wiring beat until the last of `n` nodes has finished gliding into place.
export function buildMs(n) {
  return (Math.max(0, n - 1) * NODE_STAGGER + NODE_DUR) * 1000;
}
