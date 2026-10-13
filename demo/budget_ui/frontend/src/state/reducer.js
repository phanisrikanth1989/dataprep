// src/state/reducer.js
// Pure (state, event) -> state reducer over the data-free SSE event stream.
//
// GENERIC by contract: no pipeline-specific ids, labels, or counts live here. The
// reducer aggregates whatever the events carry -- the recorded sample stream happens
// to be the trade_position_demo run, but nothing about that pipeline is hardcoded.
//
// Event contract: docs/superpowers/specs/2026-07-09-demo-ui-design.md section 8.

export const initialState = {
  stage: null,                       // { name, status } -- stepper + rail stage line + thinking-state
  sources: [],                       // [{ id, source, label, kind, sub }] -- reading-beat teasers
  rules: { count: 0, items: [] },    // { count, items: [{ id, kind, label }] } -- rail enumeration
  nodesById: {},                     // id -> { id, kind, label, sub?, source? }
  order: [],                         // node ids in arrival order
  edges: [],                         // [{ from, to, reject }]
  callouts: [],                      // [{ node, text, kind }] -- reasoning bubbles
  gate: null,                        // { kind, node, code, status } -- merged across events
  result: null,                      // { passed, tier, rows, graded, outputs, sample? }
  ended: false,                      // terminal `end` seen -> the hook closes the stream
};

export function reduce(state, event) {
  switch (event && event.type) {
    case "sources":
      // Reading beat: source teasers (name + column count). Rail north-star content.
      return { ...state, sources: event.nodes || [] };

    case "rules":
      // Interpreting beat: the enumerated business rules for the rail.
      return { ...state, rules: { count: event.count, items: event.items || [] } };

    case "nodes": {
      // Provisional skeleton (flow_plan ids). Add nodes + append their ids to order.
      // `key` is the STABLE React/Framer key (its own id here); node_config (below)
      // reuses it across a rename so the node GLIDES instead of fade-swapping.
      const nodesById = { ...state.nodesById };
      const order = state.order.slice();
      for (const n of event.nodes || []) {
        nodesById[n.id] = { id: n.id, kind: n.kind, label: n.label, key: n.id };
        if (!order.includes(n.id)) order.push(n.id);
      }
      return { ...state, nodesById, order };
    }

    case "node_config": {
      // AUTHORITATIVE: final assembled ids supersede the skeleton. REPLACE nodesById and
      // REBUILD order from these ids (a dropped skeleton id is gone from BOTH, so nothing
      // derefs undefined.kind). To keep the "glide into place" CONTINUOUS when the assembler
      // RENAMED a node (the terminal FileOutput id becomes the output name), each final node
      // reuses a stable React `key`: its own id if the skeleton already had it, else an unused
      // skeleton key of the same kind (a rename). A stable key is what lets Framer glide the
      // node rather than fade one out and another in.
      const prevKeyOf = {};              // skeleton id -> its stable key
      const freeByKind = {};             // kind -> [skeleton keys], for matching a rename
      for (const id of state.order) {
        const n = state.nodesById[id];
        if (!n) continue;
        const k = n.key || id;
        prevKeyOf[id] = k;
        (freeByKind[n.kind] || (freeByKind[n.kind] = [])).push(k);
      }
      const used = new Set();
      for (const n of event.nodes || []) {   // reserve exact-id keys before renames claim any
        if (prevKeyOf[n.id] != null) used.add(prevKeyOf[n.id]);
      }
      const nodesById = {};
      const order = [];
      for (const n of event.nodes || []) {    // preserve event order
        let key = prevKeyOf[n.id];
        if (key == null) {                     // new id -> inherit a same-kind skeleton key (rename)
          const pool = (freeByKind[n.kind] || []).filter((k) => !used.has(k));
          key = pool.length ? pool[0] : n.id;
          used.add(key);
        }
        nodesById[n.id] = { ...n, key };
        order.push(n.id);
      }
      return { ...state, nodesById, order };
    }

    case "edges":
      // Wiring beat: the DAG edges (final ids, id-consistent with node_config).
      return { ...state, edges: event.edges || [] };

    case "callout":
      // A reasoning bubble on a node. Accumulate in arrival order.
      return {
        ...state,
        callouts: [...state.callouts, { node: event.node, text: event.text, kind: event.kind }],
      };

    case "gate":
      // Code sign-off mirror beat. MERGE: a `signed` event omits `code`; preserve the
      // earlier `code` (and node) so the gate stays renderable under the signed stamp.
      return { ...state, gate: { ...state.gate, ...event } };

    case "result":
      // Finale: passed/tier/rows/graded/outputs (+ sample only in synthetic mode).
      return { ...state, result: event };

    case "stage":
      // Stepper + rail stage line + thinking-state, keyed by the daemon's stage name.
      return { ...state, stage: { name: event.stage, status: event.status } };

    case "end":
      // Terminal marker -> the hook closes the EventSource (no auto-reconnect replay).
      return { ...state, ended: true };

    default:
      // Unknown / envelope-only events (e.g. `note`) leave state unchanged.
      return state;
  }
}
