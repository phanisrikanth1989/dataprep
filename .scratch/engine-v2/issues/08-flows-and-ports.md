# 08 - Flows and ports

Status: open
Type: grilling

## Question

How are components wired to each other? v1 names every flow and gives it a
type: `{name, from, to, type}` with types flow, reject, filter, unique,
duplicate and iterate. v2 as found names ports instead: `{source, output,
target, input}`. The engine as found loses data on exactly this seam
(findings 1 to 4 in
[v2 engine as found](../research/2026-10-05-v2-as-found.md#verified-findings)).

To settle:

- The verdict for each flow key and each flow type under the five-verdict
  scheme, and how a v1 flow becomes what a component receives. Map identifies
  its main input and its lookups by flow name.
- Fan-in: several flows into one component (unite, Map lookups), and what
  fixes the order of rows across inputs. As found it follows Python set
  order and changes between runs.
- Fan-out: one output read by several consumers; two outputs of one component
  sent to the same target.
- Wiring errors -- a flow asking for an output the source never emits, a
  required input missing, duplicate flow names. All are refused at load and
  listed in the refusal report; settle the cases and the wording.
- A deterministic execution order.

Iterate flows are not decided here; they depend on
[Pin the component list](27-pin-the-component-list.md).
