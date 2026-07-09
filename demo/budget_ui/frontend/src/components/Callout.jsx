// src/components/Callout.jsx
// A reasoning bubble anchored above its node (centered on the node's top edge). The
// text comes straight from the `callout` event (state.callouts). Fades in on mount.
// The translate(-50%,-100%) that centers it above the node is kept inline so it is
// not affected by Framer touching inline styles.

import { motion } from "framer-motion";

export function Callout({ callout, pos }) {
  if (!pos) return null; // node not positioned (yet) -> nothing to anchor to

  return (
    <motion.div
      className="callout"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
      style={{ left: pos.x + pos.w / 2, top: pos.y - 8, transform: "translate(-50%,-100%)" }}
    >
      {callout.text}
    </motion.div>
  );
}
