// src/components/GraphNode.jsx
// One graph node, colored by node.kind (CSS class `k-<kind>`), showing label + sub.
// A code badge appears on `kind === "derive"`. Framer Motion's `layout` prop makes a
// node GLIDE when its computed position changes (the "nodes glide into place"
// refinement) -- e.g. when the `edges` event turns a flat skeleton into the real DAG.
//
// Choreography note: the prototype toggled `.show`/`.cfg`/`.active`/`.settled`/
// `.done-glow` from a timeline player. Here those are DERIVED FROM STATE:
//   - `.show`  : always on (a node present in state is a shown node); it also
//                neutralizes the CSS base offset so the enter fade is Framer-owned.
//   - `.cfg`   : node has a `sub` (i.e. node_config has configured it) -> reveal sub.
//   - active / settled / done-glow : passed in from the Canvas (see Canvas.jsx).

import { motion } from "framer-motion";

export function GraphNode({ node, pos, active, settled, glow, teaser, idx = 0 }) {
  if (!pos) return null; // guard a mid-stream node without a computed position

  const cls = ["node", "show", "k-" + node.kind];
  if (node.sub) cls.push("cfg");
  if (active) cls.push("active");
  if (settled) cls.push("settled");
  if (glow) cls.push("done-glow");

  // `source` crosswalk: link this graph node to its reading-beat teaser (shared
  // `source` key). Surfaced non-destructively as a tooltip; the authoritative
  // node_config label/sub still drive the visible text.
  const title = teaser ? `${teaser.label} -- ${teaser.sub}` : undefined;

  return (
    <motion.div
      layout
      className={cls.join(" ")}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{
        // Deliberate pacing: a staggered fade-in, then a slow 1s GLIDE when the skeleton
        // scatter resolves into the wired DAG (the "boxes travel to their place" beat).
        opacity: { duration: 0.7, ease: [0.2, 0.7, 0.2, 1], delay: Math.min(idx * 0.05, 0.5) },
        layout: { duration: 1.0, ease: [0.4, 0, 0.2, 1] },
      }}
      style={{ left: pos.x, top: pos.y, width: pos.w, minHeight: pos.h }}
      data-source={node.source || undefined}
      title={title}
    >
      {node.kind === "derive" && <div className="n-badge">&lt;/&gt;</div>}
      <div className="n-title">{node.label}</div>
      <div className="n-sub">{node.sub || ""}</div>
    </motion.div>
  );
}
