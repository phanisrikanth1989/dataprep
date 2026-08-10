// The canvas IS the app (ticket 12): full-bleed, drifting dot grid, the
// rules scatter during interpretation, the layered DAG with assembly
// choreography and camera leans afterwards. Everything drawn here is a
// verbatim artifact field from the run -- provenance bylines included.

import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Anchor,
  CodeGateCard,
  GapRoundCard,
  HoldCard,
  SpecGateCard,
  VerdictCard,
} from "./Cards";
import { C, Cam, DagLayout, SCATTER, camFit, camFocus, edgePath, layout, proj, region } from "./layout";
import type { QuestionView, Scene, State } from "./state";
import { latestPending, pendingOf } from "./state";

const REDUCED =
  typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;

// Deterministic scatter jitter for the assembly entrance (from the record).
const scatterPos = (i: number): { x: number; y: number } => ({
  x: 60 + i * (C.COLW * 0.66),
  y: C.MIDY + 70 + ((((i * 41 + 13) % 9) - 4) * 34),
});

interface CanvasProps {
  state: State;
  scene: Scene;
  vw: number;
  vh: number;
  setComposer: (v: string) => void;
}

function useAssembly(flowKey: string | null): boolean {
  // false = nodes still scattered; true = glided into the DAG.
  const [assembled, setAssembled] = useState(true);
  const last = useRef<string | null>(null);
  useEffect(() => {
    if (!flowKey || flowKey === last.current) {
      return;
    }
    last.current = flowKey;
    if (REDUCED) {
      setAssembled(true);
      return;
    }
    setAssembled(false);
    const t = setTimeout(() => setAssembled(true), 430);
    return () => clearTimeout(t);
  }, [flowKey]);
  return assembled;
}

export function Canvas({ state, scene, vw, vh, setComposer }: CanvasProps): React.ReactElement {
  const r = region(vw, vh);

  // ---- scatter camera ------------------------------------------------------
  const scatterCam: Cam = useMemo(() => {
    const s = Math.min(0.95, r.w / SCATTER.W, r.h / SCATTER.H);
    return { s, tx: r.left + (r.w - SCATTER.W * s) / 2, ty: r.top + (r.h - SCATTER.H * s) / 2 };
  }, [r.left, r.top, r.w, r.h]);

  // ---- dag layout + camera -------------------------------------------------
  const L: DagLayout | null = useMemo(
    () => (state.flow ? layout(state.flow.nodes, state.flow.edges as string[][]) : null),
    [state.flow]
  );
  const flowKey = state.flow ? `flow-${state.flow.iteration}` : null;
  const assembled = useAssembly(flowKey);

  let cam: Cam = scatterCam;
  if (scene.mode === "dag" && L) {
    cam =
      scene.camera.type === "focus"
        ? camFocus(r, L, scene.camera.node, scene.camera.s)
        : camFit(r, L.W, L.H, scene.camera.pad);
  }

  // Snap (no camera glide) when the composition mode changes.
  const modeRef = useRef(scene.mode);
  const snap = modeRef.current !== scene.mode;
  useEffect(() => {
    modeRef.current = scene.mode;
  });

  const canvasClass = [
    "canvas",
    scene.mode === "scatter" && scene.spot ? "spot" : "",
    scene.mode === "dag" && scene.gatehold ? "gatehold" : "",
  ]
    .filter(Boolean)
    .join(" ");

  // ---- cards ---------------------------------------------------------------
  const gaps = pendingOf(state, "gap");
  const specQ = latestPending(state, "spec_gate");
  const codeQ = latestPending(state, "code_gate");
  const humanQ = latestPending(state, "human_gate");
  const holdQ = latestPending(state, "hold");

  // Leaders pin to the rule's TOP-CENTER: the exact edge is known (no height
  // guess), and a curve leaving upward can never slice through the rule card
  // on its way to the card at the top right.
  const ruleAnchor = (ruleId: string): Anchor | null => {
    const p = SCATTER.spots[ruleId];
    return p ? proj(scatterCam, { x: p[0] + 106, y: p[1] }) : null;
  };
  const gapAnchors: Anchor[] = gaps
    .map((q) => ruleAnchor(String(q.payload.rule_id ?? "")))
    .filter((a): a is Anchor => a !== null);
  const specAnchors: Anchor[] = (state.spec?.rules ?? [])
    .filter((rl: any) => rl.gap)
    .map((rl: any) => ruleAnchor(String(rl.id)))
    .filter((a: Anchor | null): a is Anchor => a !== null);

  const nodeAnchor = (nodeId: string | null): Anchor[] => {
    if (!nodeId || !L || !L.pos[nodeId]) {
      return [];
    }
    const p = L.pos[nodeId];
    return [proj(cam, { x: p.x + p.w / 2, y: p.y + p.h })];
  };

  const onAskCell = (cell: { id: string }) => setComposer(`About ${cell.id}: `);

  return (
    <div className={canvasClass}>
      <div className="dots" />

      {scene.mode === "scatter" && state.spec ? (
        <ScatterStage state={state} cam={scatterCam} />
      ) : null}

      {scene.mode === "dag" && L && state.flow ? (
        <div key={flowKey} className={`cam${snap ? " snap" : ""}`} style={{ transform: `translate(${cam.tx}px,${cam.ty}px) scale(${cam.s})` }}>
          <DagStage state={state} scene={scene} L={L} assembled={assembled} />
        </div>
      ) : null}

      {scene.mode === "dag" && scene.wash ? <div className="wash" /> : null}
      {scene.mode === "dag" && scene.jsweep ? <div className="jsweep" /> : null}

      {scene.mode === "scatter" && scene.card === "gaps" && gaps.length ? (
        <GapRoundCard qs={gaps} vw={vw} vh={vh} anchors={gapAnchors} />
      ) : null}
      {scene.mode === "scatter" && scene.card === "spec" && specQ ? (
        <SpecGateCard q={specQ} vw={vw} vh={vh} anchors={specAnchors} />
      ) : null}
      {scene.mode === "dag" && scene.card === "code" && codeQ ? (
        <CodeGateCard
          q={codeQ}
          vw={vw}
          vh={vh}
          anchors={nodeAnchor(scene.hot)}
          onAskCell={onAskCell}
        />
      ) : null}
      {scene.mode === "dag" && scene.card === "verdict" && humanQ ? (
        <VerdictCard q={humanQ} vw={vw} vh={vh} anchors={nodeAnchor(scene.glow)} />
      ) : null}
      {scene.mode === "dag" && scene.card === "hold" && holdQ ? (
        <HoldCard q={holdQ} vw={vw} vh={vh} />
      ) : null}
    </div>
  );
}

// ---- the rules scatter (interpret era) -------------------------------------

function ScatterStage({ state, cam }: { state: State; cam: Cam }): React.ReactElement {
  const spec = state.spec ?? {};
  const sources: any[] = spec.sources ?? [];
  const rules: any[] = spec.rules ?? [];
  const gapState = (ruleId: string): "none" | "open" | "resolved" => {
    const rule = rules.find((r) => r.id === ruleId);
    if (!rule?.gap) {
      return "none";
    }
    const q = Object.values(state.questions).find(
      (qq) => qq.kind === "gap" && qq.payload.gap_id === rule.gap
    ) as QuestionView | undefined;
    if (!q) {
      return "open";
    }
    return q.resolved ? "resolved" : "open";
  };
  return (
    <div className="cam snap" style={{ transform: `translate(${cam.tx}px,${cam.ty}px) scale(${cam.s})` }}>
      <div className="stage" style={{ width: SCATTER.W, height: SCATTER.H }}>
        {sources.map((s, i) => {
          const p = SCATTER.srcAt(i);
          return (
            <div key={s.file ?? i} className="srcpill" style={{ left: p.x, top: p.y, animationDelay: `${i * 90}ms` }}>
              {s.file} · {s.cols} cols
            </div>
          );
        })}
        {rules.map((rl, i) => {
          const p = SCATTER.spots[rl.id];
          if (!p) {
            return null;
          }
          const gs = gapState(rl.id);
          const cls = ["rule"];
          if (gs === "open") {
            cls.push("gap", "hot");
          }
          if (gs === "resolved") {
            cls.push("resolved", "hot");
          }
          return (
            <div key={rl.id} className={cls.join(" ")} style={{ left: p[0], top: p[1], animationDelay: `${140 + i * 90}ms` }}>
              {gs === "open" ? <span className="gaptag">gap {rl.gap}</span> : null}
              {gs === "resolved" ? <span className="gaptag ok">answered</span> : null}
              <span className="rid">
                {rl.id} · {String(rl.kind ?? "").toUpperCase()}
              </span>
              <div className="rt">{rl.label}</div>
              <div className="rd">{rl.detail}</div>
              <div className="rby">Interpreter</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---- the DAG (design era onward) -------------------------------------------

function DagStage({
  state,
  scene,
  L,
  assembled,
}: {
  state: State;
  scene: Extract<Scene, { mode: "dag" }>;
  L: DagLayout;
  assembled: boolean;
}): React.ReactElement {
  const nodes: any[] = state.flow?.nodes ?? [];
  const edges = (state.flow?.edges ?? []) as string[][];
  const cfg = state.progress;
  const isCfgd = (id: string) => cfg[id] === "configured";
  const lit = (e: string[]) =>
    !scene.settled && Boolean(cfg[e[0]]) && Boolean(cfg[e[1]]) && !state.ended;

  return (
    <div className="stage" style={{ width: L.W, height: L.H }}>
      <svg className="edges" viewBox={`0 0 ${L.W} ${L.H}`} style={{ width: L.W, height: L.H }}>
        {edges.map((e, i) => {
          const d = edgePath(L.pos[e[0]], L.pos[e[1]]);
          const cls = ["edge", "draw"];
          if (lit(e)) {
            cls.push("lit");
          }
          if (scene.settled) {
            cls.push("jade");
          }
          if (assembled) {
            cls.push("drawn");
          }
          return (
            <React.Fragment key={`${e[0]}-${e[1]}`}>
              <path
                className={cls.join(" ")}
                d={d}
                pathLength={1}
                style={{ transitionDelay: assembled && !REDUCED ? `${1.0 + i * 0.095}s` : "0s" }}
              />
              {lit(e) ? (
                <path
                  className="edge-flow"
                  d={d}
                  style={{ opacity: assembled ? 1 : 0, transitionDelay: assembled && !REDUCED ? "2.3s" : "0s" }}
                />
              ) : null}
            </React.Fragment>
          );
        })}
      </svg>
      {nodes.map((n, i) => {
        const p = assembled ? L.pos[n.id] : { ...L.pos[n.id], ...scatterPos(i) };
        const active = state.activeNode === n.id;
        const cls = ["node", `k-${n.kind}`];
        if (active) {
          cls.push("active");
        }
        if (scene.settled) {
          cls.push("settled");
        }
        if (scene.glow === n.id) {
          cls.push("bloom");
        }
        if (scene.hot === n.id) {
          cls.push("hot");
          if (n.kind === "derive") {
            cls.push("vio");
          }
        }
        const configured = isCfgd(n.id);
        return (
          <div
            key={n.id}
            className={cls.join(" ")}
            style={{
              left: p.x,
              top: p.y,
              opacity: assembled ? 1 : 0,
              transitionDelay: REDUCED ? "0s" : `${i * 0.07}s`,
            }}
          >
            {n.code ? <span className="codetag">code</span> : null}
            <div className="head">
              <span className="dot" />
              <span className="t">{n.label}</span>
            </div>
            <div className="cfg">{configured ? n.sub : active ? <span className="cfgbar" /> : null}</div>
            {configured ? (
              <span className="by cfgd">Configurator</span>
            ) : active ? (
              <span className="by cfgd">Configurator · now</span>
            ) : (
              <span className="by">Flow Designer</span>
            )}
          </div>
        );
      })}
    </div>
  );
}
