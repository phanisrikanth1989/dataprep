// src/components/Callout.jsx
// A reasoning bubble anchored above its node, joined to it by a thin leader line. The
// text comes straight from the `callout` event (state.callouts). Fades in on mount.
//
// Horizontally-adjacent nodes are one COLW apart -- narrower than a bubble -- so the
// bubbles would collide if all sat at the same height. We STAGGER by column parity
// (derived from pos.x): even columns lift high, odd columns sit low, so neighbours are
// always at two different heights and never overlap. `--lift` (the leader-line length)
// is passed inline; the translate(-50%,-100%) that centers the bubble above the node
// is kept inline too, so Framer touching inline styles does not disturb it.

import { motion } from "framer-motion";

// Layout constants (mirror state/layout.js): first column at PADX, one COLW apart.
const PADX = 18;
const COLW = 152;
const LIFT_HI = 46; // even columns: lifted clear of their low neighbours
const LIFT_LO = 10; // odd columns: just above the node

export function Callout({ callout, pos }) {
  if (!pos) return null; // node not positioned (yet) -> nothing to anchor to

  const col = Math.round((pos.x - PADX) / COLW);
  const lift = col % 2 === 0 ? LIFT_HI : LIFT_LO;

  return (
    <motion.div
      className="callout"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
      style={{
        left: pos.x + pos.w / 2,
        top: pos.y - lift,
        transform: "translate(-50%,-100%)",
        "--lift": lift + "px",
      }}
    >
      {callout.text}
    </motion.div>
  );
}
