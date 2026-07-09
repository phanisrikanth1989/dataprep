// src/components/Rail.jsx
// The assistant panel as a TAGGED TRANSCRIPT: one block per pipeline stage reached, each tagged
// with the specialist AGENT that owns it (avatar + name). Past agents settle to a done check;
// the active agent shows a live spinner + a rotating "thought". The Reader's block anchors the
// source list (so it no longer follows the latest line). The sign-off beat is the HUMAN.
//
// GENERIC / data-free: every message is AUTHORED here, re-keyed to the daemon stage names; only
// counts, rule labels and the result line come from `state` (never LLM prose). Static markup is
// JSX; state-derived text is escaped children (never dangerouslySetInnerHTML).

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { STAGE_ORDER, AGENTS, THOUGHTS } from "../stages.js";

// A small "person" glyph for the human sign-off avatar (not an agent initial).
const PERSON = (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
       strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="8" r="3.5" /><path d="M5 21c0-3.6 3.4-5.5 7-5.5s7 1.9 7 5.5" />
  </svg>
);

// How far down STAGE_ORDER the transcript has reached. `done` shows every stage's block.
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

// State-derived narration for one daemon stage -> an array of { node } message lines.
function narrationFor(name, state) {
  switch (name) {
    case "reading": {
      const lines = [{ node: <>Reading your document&hellip;</> }];
      if (state.sources.length) {
        lines.push({
          node: state.rules.count ? (
            <>Found <b>{state.sources.length} sources</b> and <b>{state.rules.count} rules</b>.</>
          ) : (
            <>Found <b>{state.sources.length} sources</b>.</>
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
        { node: <>Review and sign off before it runs.</> },
      ];
    case "testing": {
      const lines = [{ node: <>Running it against your sample data&hellip;</> }];
      if (state.result) {
        lines.push(
          state.result.passed
            ? { node: <b>Ran clean. {state.result.rows} rows. Matched your expected output.</b> }
            : { node: <>Not a match yet &mdash; refining before it ships.</> }
        );
      }
      return lines;
    }
    default:
      return [];
  }
}

// Reading-beat teasers, anchored UNDER the Reader block. Each shares its `source` key with a
// graph FileInput node.
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

// The active agent's rotating "thought" (the spinner lives in the avatar).
function ThinkingLine({ stageName }) {
  const thoughts = (stageName && THOUGHTS[stageName]) || [];
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    setIdx(0);
  }, [stageName]);
  useEffect(() => {
    if (thoughts.length === 0) return undefined;
    const t = setInterval(() => setIdx((i) => (i + 1) % thoughts.length), 1600);
    return () => clearInterval(t);
  }, [stageName, thoughts.length]);
  if (!thoughts.length) return null;
  return <div className="agent-think">{thoughts[idx]}</div>;
}

// One agent's transcript block: an ACCORDION row. The active agent (and the final one, which
// has no successor to hand off to) is OPEN; a finished agent COLLAPSES to just its header when
// the next agent takes over, and the user can click it back open to re-read it.
function AgentBlock({ stageName, isActive, isLast, isPrev, state }) {
  const agent = AGENTS[stageName];
  // manual: null = follow the auto state; true/false = the user's explicit open/collapsed override.
  const [manual, setManual] = useState(null);
  // When the DEFAULT open-state changes (this agent activates, becomes the just-finished one, or
  // that role passes to the next agent), drop the manual override so it follows the new default.
  useEffect(() => {
    setManual(null);
  }, [isActive, isPrev]);
  if (!agent) return null;

  // OPEN = the active agent, the one that JUST handed off (isPrev -- stays readable the whole time
  // the current agent works, then collapses at the next handoff), or the final agent. Gives ample
  // reading time and stays deterministic (never more than "current + just-did" auto-open).
  const autoOpen = isActive || isLast || isPrev;
  const open = manual === null ? autoOpen : manual;
  const collapsible = !isActive; // anything not actively working can be toggled open/closed
  const toggle = collapsible ? () => setManual(open ? false : true) : undefined;
  const lines = narrationFor(stageName, state);
  const cls =
    "agent " + (isActive ? "active" : "done") + (agent.human ? " human" : "") +
    (open ? " open" : "") + (collapsible ? " clickable" : "");

  return (
    <motion.div
      className={cls}
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.4 }}
    >
      <div
        className="agent-h"
        onClick={toggle}
        role={collapsible ? "button" : undefined}
        tabIndex={collapsible ? 0 : undefined}
        onKeyDown={
          collapsible
            ? (e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setUserOpen((o) => !o);
                }
              }
            : undefined
        }
      >
        <span className="avatar">{agent.human ? PERSON : agent.initial}</span>
        <span className="agent-name">{agent.name}</span>
        <span className="agent-state">
          {isActive ? (
            <span className="spin" />
          ) : open ? (
            <span className="chk">&#10003;</span>
          ) : (
            <span className="chev">&#9656;</span>
          )}
        </span>
      </div>
      <div className="agent-bodywrap">
        <div className="agent-body">
          {lines.map((l, j) => (
            <p className="agent-msg" key={stageName + "-" + j}>
              {l.node}
            </p>
          ))}
          {stageName === "reading" && <SourceTeasers sources={state.sources} />}
          {isActive && <ThinkingLine stageName={stageName} />}
        </div>
      </div>
    </motion.div>
  );
}

export function Rail({ state }) {
  const currentName = state.stage && state.stage.name;
  const idx = reachedIndex(currentName);
  const reached = idx >= 0 ? STAGE_ORDER.slice(0, idx + 1) : [];
  // The stage that JUST handed off to the active one (immediately before it) stays open too, so
  // its output is readable the whole time the current agent works -- then it collapses next handoff.
  const activeIdx = currentName && currentName !== "done" ? STAGE_ORDER.indexOf(currentName) : -1;
  const prevStage = activeIdx > 0 ? STAGE_ORDER[activeIdx - 1] : null;
  return (
    <div className="rail">
      <div className="rail-h">
        <span className="pip" /> Assistant
      </div>
      <div className="rail-blocks">
        {reached.map((stageName, i) => (
          <AgentBlock
            key={stageName}
            stageName={stageName}
            isActive={stageName === currentName && currentName !== "done"}
            isLast={i === reached.length - 1}
            isPrev={stageName === prevStage}
            state={state}
          />
        ))}
        {currentName === "done" && (
          <div className="agent done all-done open">
            <div className="agent-h">
              <span className="avatar">&#10003;</span>
              <span className="agent-name">Done</span>
            </div>
            <div className="agent-bodywrap">
              <div className="agent-body">
                <p className="agent-msg">Pipeline built and verified.</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
