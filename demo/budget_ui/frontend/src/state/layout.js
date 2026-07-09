// src/state/layout.js
// Pure layered-DAG layout, ported from the committed prototype
// (demo/budget_ui/frontend/prototype-thinking-state.html -> layout()).
//
// GENERIC: it positions whatever nodes/edges it is handed. Algorithm (verbatim from
// the prototype): topological (Kahn) sort -> longest-path layering -> sourceless nodes
// pulled toward their consumer -> the longest path becomes the main line at row 0, the
// rest stacked below per column. Same NW/NH/COLW constants.
//
// Signature adapts the prototype to the reducer's state shape: `layout(nodesById, edges)`.
// `ids` come from Object.keys(nodesById) (the only line changed); `edges` are
// [{from, to, reject}] -- the extra `reject` field is ignored, exactly as the prototype
// ignored anything beyond {from, to}. Returns { pos: {id:{x,y,w,h}}, W, H }.

export function layout(nodesById, edges) {
  const ids = Object.keys(nodesById);
  // Guard the empty graph FIRST: the Canvas renders during the reading/sources beats
  // before any node exists; an unguarded Math.max(...[]) would return -Infinity and
  // yield an invalid canvas (spec section 16.4: never a blank/invalid canvas).
  if (ids.length === 0) return { pos: {}, W: 640, H: 360 };
  const succ = {}, pred = {};
  ids.forEach(i => { succ[i] = []; pred[i] = []; });
  edges.forEach(f => {
    if (!(f.from in succ) || !(f.to in pred)) return;  // skip an edge to a not-yet-known node
    succ[f.from].push(f.to);
    pred[f.to].push(f.from);
  });
  const indeg = {}; ids.forEach(i => indeg[i] = pred[i].length);
  const q = ids.filter(i => indeg[i] === 0), topo = [];
  while (q.length) { const n = q.shift(); topo.push(n); succ[n].forEach(m => { if (--indeg[m] === 0) q.push(m); }); }
  const layer = {}; ids.forEach(i => layer[i] = 0);
  topo.forEach(n => pred[n].forEach(p => layer[n] = Math.max(layer[n], layer[p] + 1)));
  ids.forEach(i => { if (pred[i].length === 0 && succ[i].length) layer[i] = Math.min(...succ[i].map(s => layer[s])) - 1; });
  // longest path -> main line at row 0
  const dp = {}, back = {}; topo.forEach(n => { dp[n] = 0; back[n] = null; pred[n].forEach(p => { if (dp[p] + 1 > dp[n]) { dp[n] = dp[p] + 1; back[n] = p; } }); });
  let end = ids[0]; ids.forEach(i => { if (dp[i] > dp[end]) end = i; });
  const main = new Set(); for (let c = end; c; c = back[c]) main.add(c);
  const byCol = {}; ids.forEach(i => (byCol[layer[i]] || (byCol[layer[i]] = [])).push(i));
  const row = {};
  Object.values(byCol).forEach(col => { let below = 1; col.forEach(i => { if (main.has(i)) row[i] = 0; }); col.forEach(i => { if (!main.has(i)) row[i] = below++; }); });
  const COLW = 152, NODEW = 132, NODEH = 54, ROWH = 98, PADX = 18, MIDY = 118;
  const pos = {}; ids.forEach(i => pos[i] = { x: PADX + layer[i] * COLW, y: MIDY + row[i] * ROWH, w: NODEW, h: NODEH });
  const maxCol = Math.max(...ids.map(i => layer[i])), maxRow = Math.max(...ids.map(i => row[i]));
  return { pos, W: PADX + maxCol * COLW + NODEW + PADX, H: MIDY + maxRow * ROWH + NODEH + 24 };
}
