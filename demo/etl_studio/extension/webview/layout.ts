// Layered-DAG layout + camera math, ported verbatim from the ticket 12
// design record (prototype-webview-ui-v2.html), which itself ported the
// budget_ui layout() algorithm. Pure functions -- no DOM.

export interface NodeSpec {
  id: string;
  kind: string;
  label: string;
  sub?: string;
  code?: boolean;
}

export interface Pos {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface DagLayout {
  pos: Record<string, Pos>;
  W: number;
  H: number;
}

export interface Cam {
  s: number;
  tx: number;
  ty: number;
}

export interface Region {
  left: number;
  top: number;
  w: number;
  h: number;
  vw: number;
  vh: number;
}

export const C = { COLW: 268, NODEW: 224, NODEH: 96, ROWH: 140, PADX: 40, MIDY: 56 };

export function layout(nodes: NodeSpec[], edges: string[][], cfg = C): DagLayout {
  const ids = nodes.map((n) => n.id);
  const succ: Record<string, string[]> = {};
  const pred: Record<string, string[]> = {};
  ids.forEach((i) => {
    succ[i] = [];
    pred[i] = [];
  });
  edges.forEach(([f, t]) => {
    succ[f].push(t);
    pred[t].push(f);
  });
  const indeg: Record<string, number> = {};
  ids.forEach((i) => (indeg[i] = pred[i].length));
  const q = ids.filter((i) => indeg[i] === 0);
  const topo: string[] = [];
  while (q.length) {
    const n = q.shift() as string;
    topo.push(n);
    succ[n].forEach((m) => {
      if (--indeg[m] === 0) {
        q.push(m);
      }
    });
  }
  const layer: Record<string, number> = {};
  ids.forEach((i) => (layer[i] = 0));
  topo.forEach((n) => pred[n].forEach((p) => (layer[n] = Math.max(layer[n], layer[p] + 1))));
  ids.forEach((i) => {
    if (pred[i].length === 0 && succ[i].length) {
      layer[i] = Math.min(...succ[i].map((s) => layer[s])) - 1;
    }
  });
  const dp: Record<string, number> = {};
  const back: Record<string, string | null> = {};
  topo.forEach((n) => {
    dp[n] = 0;
    back[n] = null;
    pred[n].forEach((p) => {
      if (dp[p] + 1 > dp[n]) {
        dp[n] = dp[p] + 1;
        back[n] = p;
      }
    });
  });
  let end = ids[0];
  ids.forEach((i) => {
    if (dp[i] > dp[end]) {
      end = i;
    }
  });
  const main = new Set<string>();
  for (let c: string | null = end; c; c = back[c]) {
    main.add(c);
  }
  const byCol: Record<number, string[]> = {};
  ids.forEach((i) => (byCol[layer[i]] || (byCol[layer[i]] = [])).push(i));
  const row: Record<string, number> = {};
  Object.values(byCol).forEach((col) => {
    let below = 1;
    col.forEach((i) => {
      if (main.has(i)) {
        row[i] = 0;
      }
    });
    col.forEach((i) => {
      if (!main.has(i)) {
        row[i] = below++;
      }
    });
  });
  const pos: Record<string, Pos> = {};
  ids.forEach(
    (i) =>
      (pos[i] = {
        x: cfg.PADX + layer[i] * cfg.COLW,
        y: cfg.MIDY + row[i] * cfg.ROWH,
        w: cfg.NODEW,
        h: cfg.NODEH,
      })
  );
  const maxCol = Math.max(...ids.map((i) => layer[i]));
  const maxRow = Math.max(...ids.map((i) => row[i]));
  return {
    pos,
    W: cfg.PADX + maxCol * cfg.COLW + cfg.NODEW + cfg.PADX,
    H: cfg.MIDY + maxRow * cfg.ROWH + cfg.NODEH + 40,
  };
}

export function edgePath(a: Pos, b: Pos): string {
  const x1 = a.x + a.w;
  const y1 = a.y + a.h / 2;
  const x2 = b.x;
  const y2 = b.y + b.h / 2;
  const mx = (x1 + x2) / 2;
  return `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`;
}

export const vwNarrow = (vw: number): boolean => vw < 980;

// The region the canvas composes into: right of the feed, above the spine.
export function region(vw: number, vh: number): Region {
  const left = vwNarrow(vw) ? 24 : 432;
  const top = 84;
  const right = 28;
  const bottom = 150;
  return { left, top, w: vw - left - right, h: vh - top - bottom, vw, vh };
}

// Whole flow in the region.
export function camFit(r: Region, W: number, H: number, pad = 1): Cam {
  const s = Math.min(0.92, (r.w * pad) / W, (r.h * pad) / H);
  return { s, tx: r.left + (r.w - W * s) / 2, ty: r.top + (r.h - H * s) / 2 };
}

// Lean into a node (camera choreography).
export function camFocus(r: Region, L: DagLayout, nodeId: string, s: number): Cam {
  const p = L.pos[nodeId];
  if (!p) {
    return camFit(r, L.W, L.H, 0.96);
  }
  const cx = p.x + p.w / 2;
  const cy = p.y + p.h / 2;
  let tx = r.left + r.w / 2 - cx * s;
  let ty = r.top + r.h / 2 - cy * s;
  tx = Math.min(r.left, Math.max(r.left + r.w - L.W * s, tx));
  if (L.H * s > r.h) {
    ty = Math.min(r.top, Math.max(r.top + r.h - L.H * s, ty));
  }
  return { s, tx, ty };
}

export const proj = (cam: Cam, p: { x: number; y: number }): { x: number; y: number } => ({
  x: cam.tx + p.x * cam.s,
  y: cam.ty + p.y * cam.s,
});

// Scatter geometry for the rules beat (ported spot map).
export const SCATTER = {
  W: 1240,
  H: 720,
  spots: {
    R1: [80, 150],
    R2: [610, 120],
    R3: [130, 360],
    R4: [660, 350],
    R5: [380, 500],
    R6: [830, 470],
  } as Record<string, number[]>,
  srcAt: (i: number): { x: number; y: number } => ({ x: 90 + i * 230, y: 40 }),
};
