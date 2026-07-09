// tests/layout.test.js
import { describe, it, expect } from "vitest";
import { reduce, initialState } from "../src/state/reducer.js";
import { layout } from "../src/state/layout.js";
import sample from "../src/replay/sample-events.json";
describe("layout", () => {
  it("positions every node with finite coords and a sane canvas", () => {
    const s = sample.reduce(reduce, initialState);
    const { pos, W, H } = layout(s.nodesById, s.edges);
    for (const id of Object.keys(s.nodesById)) {
      expect(Number.isFinite(pos[id].x)).toBe(true);
      expect(Number.isFinite(pos[id].y)).toBe(true);
    }
    expect(W).toBeGreaterThan(0); expect(H).toBeGreaterThan(0);
  });
  it("guards the empty graph (early beats) with finite dimensions", () => {
    const { W, H } = layout({}, []);
    expect(Number.isFinite(W)).toBe(true); expect(Number.isFinite(H)).toBe(true);
    expect(W).toBeGreaterThan(0); expect(H).toBeGreaterThan(0);
  });
  it("does not crash on an edge to an unknown node", () => {
    expect(() => layout({ a: { id: "a" } }, [{ from: "a", to: "ghost" }])).not.toThrow();
  });
  it("lays the pre-wiring skeleton (nodes, no edges) in a horizontal scatter, not a vertical column", () => {
    const nodes = { a: { id: "a" }, b: { id: "b" }, c: { id: "c" }, d: { id: "d" } };
    const { pos } = layout(nodes, []);
    const xs = Object.values(pos).map((p) => p.x);
    // Distinct x per node (spread left-to-right), not one shared column -> not the old vertical stack.
    expect(new Set(xs).size).toBe(xs.length);
    expect(Math.max(...xs) - Math.min(...xs)).toBeGreaterThan(200);
  });
});
