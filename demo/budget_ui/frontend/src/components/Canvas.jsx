// src/components/Canvas.jsx
// The right-hand canvas: the SVG edge layer + Framer-Motion graph nodes positioned by
// the pure `layout(nodesById, edges)`, the reasoning callouts, the code-gate overlay,
// the finale panel, and (below the grid) the stepper -- matching the prototype's DOM.
//
// `active` / `settled` / `done-glow` are DERIVED FROM STATE (the prototype drove them
// from a timeline player):
//   - active   : by the current stage -- source nodes while reading, transforms while
//                designing, all while configuring, the gate node during signoff.
//   - settled  : once a result exists (the testing beat).
//   - done-glow: the passed result's output node(s).
// All by node kind / state fields, never by hardcoded ids.

import { useEffect, useMemo, useRef, useState } from "react";
import { layout } from "../state/layout.js";
import { buildMs, GATE_PAUSE } from "../anim.js";
import { Edges } from "./Edges.jsx";
import { GraphNode } from "./GraphNode.jsx";
import { Callout } from "./Callout.jsx";
import { CodeGate } from "./CodeGate.jsx";
import { Finale } from "./Finale.jsx";
import { Stepper } from "./Stepper.jsx";

function activeIds(state) {
  const name = state.stage && state.stage.name;
  const kindOf = (id) => state.nodesById[id] && state.nodesById[id].kind;
  if (name === "reading") return state.order.filter((id) => kindOf(id) === "source");
  if (name === "designing") return state.order.filter((id) => kindOf(id) !== "source");
  if (name === "configuring") return state.order.slice();
  if (name === "signoff") return state.gate && state.gate.node ? [state.gate.node] : [];
  return [];
}

export function Canvas({ state }) {
  // Recompute layout only when the graph actually changes (node_config / edges). The
  // reducer preserves nodesById/edges identity across other events, so this is stable
  // -- which also means Framer's `layout` glide fires exactly on the edges beat.
  const L = useMemo(() => layout(state.nodesById, state.edges), [state.nodesById, state.edges]);

  // Fit-to-width: scale the stage down to the grid width (ported from the prototype's
  // fitScale). Guarded so setting the grid height cannot loop the ResizeObserver.
  const gridRef = useRef(null);
  const [fit, setFit] = useState({ scale: 1, left: 12, height: 360 });
  useEffect(() => {
    const grid = gridRef.current;
    if (!grid) return undefined;
    const measure = () => {
      const avail = grid.clientWidth - 24;
      const scale = Math.min(1, avail / L.W);
      const left = Math.max(12, (grid.clientWidth - L.W * scale) / 2);
      const height = L.H * scale + 28;
      setFit((prev) =>
        prev.scale === scale && prev.left === left && prev.height === height
          ? prev
          : { scale, left, height }
      );
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(grid);
    return () => ro.disconnect();
  }, [L.W, L.H]);

  const active = useMemo(
    () => new Set(activeIds(state)),
    [state.stage, state.gate, state.nodesById, state.order]
  );
  const settled = !!(state.result && state.result.passed);
  const glow = useMemo(
    () => new Set(state.result && state.result.passed ? state.result.outputs || [] : []),
    [state.result]
  );
  // `source` crosswalk: teaser (with column count) keyed by its source, for the nodes.
  const teaserBySource = useMemo(() => {
    const m = {};
    for (const s of state.sources) if (s && s.source) m[s.source] = s;
    return m;
  }, [state.sources]);
  // Chain index per node id -> the staggered edge draw (Edges) keys off the downstream node.
  const indexById = useMemo(() => {
    const m = {};
    state.order.forEach((id, i) => { m[id] = i; });
    return m;
  }, [state.order]);
  // The code gate rises only AFTER the last node has glided into place (+ a pause) -- never
  // suddenly, mid-build. Scales with node count so it always follows the chain assembly.
  const gateRevealMs = buildMs(state.order.length) + GATE_PAUSE * 1000;

  return (
    <div className="canvaswrap">
      <div className="canvasgrid" ref={gridRef} style={{ height: fit.height }}>
        <div className="fit" style={{ transform: `scale(${fit.scale})`, left: fit.left, top: 14 }}>
          <div className="stage" style={{ width: L.W, height: L.H }}>
            <Edges edges={state.edges} pos={L.pos} W={L.W} H={L.H} indexById={indexById} />
            {state.order.map((id, i) => {
              const node = state.nodesById[id];
              if (!node) return null;
              return (
                <GraphNode
                  key={node.key || id}
                  idx={i}
                  node={node}
                  pos={L.pos[id]}
                  active={active.has(id)}
                  settled={settled}
                  glow={glow.has(id)}
                  teaser={node.source ? teaserBySource[node.source] : null}
                />
              );
            })}
            {state.callouts.map((c, i) => (
              <Callout key={(c.node || "c") + "-" + i} callout={c} pos={L.pos[c.node]} />
            ))}
          </div>
        </div>
        <CodeGate gate={state.gate} result={state.result} revealMs={gateRevealMs} />
        <Finale result={state.result} />
      </div>
      <Stepper state={state} />
    </div>
  );
}
