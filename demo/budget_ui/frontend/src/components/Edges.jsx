// src/components/Edges.jsx
// One cubic bezier per `state.edges`, drawn between the layout anchors (right edge of
// `from` -> left edge of `to`, vertically centered), matching the prototype's path.
// Framer Motion animates `pathLength` 0 -> 1 for the "draw" reveal.
//
// A `reject: true` edge is styled distinctly (see `.edge.reject` in styles.css). It is
// distinguished by COLOR rather than dashes because Framer's pathLength animation
// writes inline stroke-dasharray/offset, which would override a dashed style.

import { motion } from "framer-motion";
import { NODE_STAGGER, NODE_DUR, EDGE_DUR } from "../anim.js";

export function Edges({ edges, pos, W, H, indexById = {} }) {
  return (
    <svg className="edges" viewBox={`0 0 ${W} ${H}`}>
      {edges.map((e) => {
        const a = pos[e.from];
        const b = pos[e.to];
        // Guard a malformed / mid-stream-incomplete graph: skip an edge whose
        // endpoints are not both positioned (spec 16.4: never crash, never a false
        // graph). Post node_config + edges, all endpoints resolve.
        if (!a || !b) return null;
        const x1 = a.x + a.w;
        const y1 = a.y + a.h / 2;
        const x2 = b.x;
        const y2 = b.y + b.h / 2;
        const mx = (x1 + x2) / 2;
        const d = `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`;
        // Draw each edge as its DOWNSTREAM node lands -- the later of its two endpoints in
        // the chain -- so the connection appears just after the box it points at settles,
        // never across a still-travelling box (see GraphNode's staggered glide).
        const landIdx = Math.max(indexById[e.from] || 0, indexById[e.to] || 0);
        const delay = landIdx * NODE_STAGGER + NODE_DUR * 0.55;
        return (
          <motion.path
            key={`${e.from}->${e.to}`}
            className={"edge" + (e.reject ? " reject" : "")}
            d={d}
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: 1 }}
            transition={{ duration: EDGE_DUR, ease: "easeInOut", delay }}
          />
        );
      })}
    </svg>
  );
}
