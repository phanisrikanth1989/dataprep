# 08 - Flows and ports

Status: resolved
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

## Answer

Resolved 2026-10-05 by assumption. The dev stopped the question rounds and
asked for the build ("make your own assumptions based on the answers I have
given till now, and then go ahead and build the entire V2 ... when I test it
out, then we can make changes"). What follows is what was built. Each point
is a default the dev can overturn.

- v1's flow shape is the one read: `{name, from, to, type}`; `source` /
  `target` are v2 spellings of `from` / `to`, and `output` names a port
  outright. Types `flow`, `main`, `reject`, `filter`, `unique`, `duplicate`
  are mapped to an output port by the source component's `outputs`
  declaration; `iterate` is refused.
- A component gets its inputs as `{flow name: frame}` in the order of its
  own `inputs` list, then job-config order: v1's rule, so a join's first
  input is its main flow. Map tells main and lookups apart by flow name.
- Fan-out and two outputs meeting again work and read the source once.
- Refused at load: a flow from or to an unknown component, a duplicate flow
  name, a flow asking for an output the source does not have, too many or
  too few inputs, flows that form a loop.
- Order inside a subjob is v1's, reproduced from its execution plan and
  checked against it on generated graphs (`src/v2/job/graph.py`).
