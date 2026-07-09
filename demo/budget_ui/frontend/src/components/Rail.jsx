// src/components/Rail.jsx
// The narrating rail: one line per stage reached (derived from state), a reading-beat
// source-teaser list (the `source` crosswalk), and the thinking-state pill (the star).
//
// GENERIC / no pipeline literals: counts, rule text and the result line come from
// `state`; only the generic stage lead-ins are authored here, re-keyed to the daemon
// stage names. Static markup (b/i) is authored as JSX; state-derived text is inserted
// as escaped children (never dangerouslySetInnerHTML).

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { STAGE_ORDER, STAGE_BY_NAME, THOUGHTS } from "../stages.js";

// How far down STAGE_ORDER the rail has narrated. `done` shows every stage's lines.
function reachedIndex(name) {
  if (!name) return -1;
  if (name === "done") return STAGE_ORDER.length - 1;
  return STAGE_ORDER.indexOf(name);
}

function distinctLabels(items) {
  const seen = new Set();
  const out = [];
  for (const it of items || []) {
    if (it && it.label && !seen.has(it.label)) {
      seen.add(it.label);
      out.push(it.label);
    }
  }
  return out;
}

function joinPhrases(list) {
  if (list.length <= 1) return list.join("");
  return list.slice(0, -1).join(", ") + ", and " + list[list.length - 1];
}

// State-derived narration for one daemon stage -> an array of { node, done? } lines.
function narrationFor(name, state) {
  switch (name) {
    case "reading": {
      const lines = [{ node: <>Reading your document&hellip;</> }];
      // Sources are known here (from extract_doc); the rule COUNT only arrives one stage
      // later (requirement_spec). Show sources now, and append the rule count only once it
      // is actually known -- never render a premature "0 rules".
      if (state.sources.length) {
        lines.push({
          node: state.rules.count ? (
            <>
              Found <b>{state.sources.length} sources</b> and <b>{state.rules.count} rules</b>.
            </>
          ) : (
            <>
              Found <b>{state.sources.length} sources</b>.
            </>
          ),
        });
      }
      return lines;
    }
    case "interpreting": {
      const lines = [{ node: <>Understanding what you need:</> }];
      const labels = distinctLabels(state.rules.items);
      if (labels.length) lines.push({ node: <>{joinPhrases(labels)}.</> });
      return lines;
    }
    case "designing":
      return [{ node: <>Designing the pipeline &mdash; the fastest components that fit.</> }];
    case "configuring":
      return [{ node: <>Configuring each step &mdash; choosing <i>how</i>, not just what.</> }];
    case "wiring":
      return [{ node: <>Wiring it all into one runnable job.</> }];
    case "signoff":
      return [
        { node: <>One step writes code to compute a value.</> },
        { node: <>A human reviews and signs off before it runs.</> },
      ];
    case "testing": {
      const lines = [{ node: <>Running it against your sample data&hellip;</> }];
      if (state.result) {
        lines.push(
          state.result.passed
            ? { done: true, node: <b>Ran clean. {state.result.rows} rows. Matched your expected output.</b> }
            : { node: <>Not a match yet &mdash; refining before it ships.</> }
        );
      }
      return lines;
    }
    default:
      return [];
  }
}

function railLines(state) {
  const idx = reachedIndex(state.stage && state.stage.name);
  const out = [];
  for (let i = 0; i <= idx && i < STAGE_ORDER.length; i++) {
    const name = STAGE_ORDER[i];
    narrationFor(name, state).forEach((ln, j) => out.push({ key: name + "-" + j, ...ln }));
  }
  return out;
}

// Reading-beat teasers: each shares its `source` key with a graph FileInput node.
function SourceTeasers({ sources }) {
  if (!sources.length) return null;
  return (
    <ul className="rl-srcs">
      {sources.map((s) => (
        <li className="rl-src" key={s.id} data-source={s.source}>
          {s.label}
          {s.sub ? <> &middot; {s.sub}</> : null}
        </li>
      ))}
    </ul>
  );
}

// The thinking-state pill: spinner + the active stage's line + a rotating "thought".
function ThinkingPill({ stage }) {
  const name = stage && stage.name;
  const done = name === "done";
  const meta = name ? STAGE_BY_NAME[name] : null;
  const label = done ? "Done" : meta ? meta.l : "Starting";
  const thoughts = (name && THOUGHTS[name]) || [];

  const [idx, setIdx] = useState(0);
  useEffect(() => {
    setIdx(0);
  }, [name]);
  useEffect(() => {
    if (done || thoughts.length === 0) return undefined;
    const t = setInterval(() => setIdx((i) => (i + 1) % thoughts.length), 1600);
    return () => clearInterval(t);
  }, [name, done, thoughts.length]);

  const sub = done ? "pipeline built and verified" : thoughts[idx] || "";
  const cls = "think" + (name ? " on" : "") + (done ? " done-state" : "");

  return (
    <div className={cls}>
      <div className="now">
        <span className="spin" />
        <span>{label}</span>
      </div>
      <div className="sub">{sub}</div>
    </div>
  );
}

export function Rail({ state }) {
  const lines = railLines(state);
  const showTeasers = reachedIndex(state.stage && state.stage.name) >= 0;
  return (
    <div className="rail">
      <div className="rail-h">
        <span className="pip" /> Assistant
      </div>
      <div className="rail-lines">
        {lines.map((l) => (
          <motion.p
            key={l.key}
            className={"rl" + (l.done ? " done" : "")}
            initial={{ opacity: 0, x: -5 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4 }}
          >
            {l.node}
          </motion.p>
        ))}
        {showTeasers && <SourceTeasers sources={state.sources} />}
      </div>
      <ThinkingPill stage={state.stage} />
    </div>
  );
}
