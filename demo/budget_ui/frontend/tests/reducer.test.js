// tests/reducer.test.js
import { describe, it, expect } from "vitest";
import { reduce, initialState } from "../src/state/reducer.js";
import sample from "../src/replay/sample-events.json";

describe("reducer", () => {
  it("builds the authoritative graph from the recorded stream", () => {
    const state = sample.reduce(reduce, initialState);
    // node_config authoritative -> final ids, no dangling skeleton output id
    const ids = Object.keys(state.nodesById);
    expect(ids).toContain("trade_positions");
    expect(ids).not.toContain("out_trade_positions");
    // every node has a kind (coloring) and the join resolved its lookup name
    expect(ids.every(id => state.nodesById[id].kind)).toBe(true);
    expect(Object.values(state.nodesById).some(n => n.label === "Match accounts")).toBe(true);
    // edges reference only real nodes
    const edgeIds = new Set(state.edges.flatMap(e => [e.from, e.to]));
    expect([...edgeIds].every(id => state.nodesById[id])).toBe(true);
    // finale + terminal
    expect(state.result.passed).toBe(true);
    expect(state.result.rows).toBe(4);
    expect(state.result.outputs).toEqual(["trade_positions"]);
    expect(state.ended).toBe(true);
    expect(state.gate && state.gate.status).toBe("signed");
    // rail + reasoning populated (north star), order has no dropped skeleton id, finale table + preserved code
    expect(state.sources.length).toBe(3);
    expect(state.rules.count).toBe(6);
    expect(state.callouts.length).toBe(5);
    expect(state.order).not.toContain("out_trade_positions");
    expect(state.result.sample.length).toBe(4);
    expect(state.gate.code).toContain("market_value");   // code preserved through the signed merge
  });

  it("reconciles a renamed terminal output to a stable key so it glides, not fade-swaps", () => {
    let s = reduce(initialState, {
      type: "nodes",
      nodes: [
        { id: "in", kind: "source", label: "Read" },
        { id: "out_x", kind: "output", label: "Write" },
      ],
    });
    expect(s.nodesById["out_x"].key).toBe("out_x"); // skeleton key = its own id
    s = reduce(s, {
      type: "node_config",
      nodes: [
        { id: "in", kind: "source", label: "Read in" },
        { id: "x", kind: "output", label: "Write x" }, // assembler renamed out_x -> x
      ],
    });
    expect(Object.keys(s.nodesById)).toEqual(["in", "x"]); // final ids (skeleton id dropped)
    expect(s.nodesById["in"].key).toBe("in"); // unchanged id keeps its key
    expect(s.nodesById["x"].key).toBe("out_x"); // renamed output reuses the same-kind skeleton key -> glide
  });
});
