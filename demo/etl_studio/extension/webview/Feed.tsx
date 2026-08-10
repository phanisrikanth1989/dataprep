// The floating glass feed: cumulative run history (replay made visible),
// orchestrator bubbles as the only speaking voice, specialist work as
// observed windows that collapse into reopenable thinking pills, and the
// composer (command.ask). Ticket 12 vocabulary + ticket 13 surfaces.

import React, { useEffect, useRef, useState } from "react";
import { answer } from "./bridge";
import type { FeedItem, State, StreamView, ToolView } from "./state";
import { deriveFeedSub, latestPending, pendingOf } from "./state";

function StepLine({ text }: { text: string }): React.ReactElement {
  const i = text.indexOf(" · ");
  if (i < 0) {
    return <div className="fi step">{text}</div>;
  }
  return (
    <div className="fi step">
      <b>{text.slice(0, i)}</b>
      {text.slice(i)}
    </div>
  );
}

function ToolChip({ tool }: { tool: ToolView }): React.ReactElement {
  const [open, setOpen] = useState(false);
  const icon = !tool.done ? (
    <span className="sp" />
  ) : tool.warn ? (
    <span className="warn">↻</span>
  ) : tool.ok ? (
    <span className="ok">✓</span>
  ) : (
    <span className="warn">✕</span>
  );
  return (
    <div className={`tool${open ? " open" : ""}`}>
      <button className="tc" onClick={() => setOpen(!open)}>
        {icon}
        <span>
          {tool.name}
          {tool.args && Object.values(tool.args).length
            ? ` · ${String(Object.values(tool.args)[0])}`
            : ""}
          {tool.warn ? <span className="warn"> · {tool.warn}</span> : null}
        </span>
      </button>
      {tool.note ? <div className="tout">{tool.note}</div> : null}
    </div>
  );
}

const thinkingLines = (thinking: string): string[] =>
  thinking
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim())
    .filter(Boolean);

function OrchestratorBubble({ s }: { s: StreamView }): React.ReactElement {
  return (
    <div className="fi msg">
      <div className="who">{s.who ?? "Orchestrator"}</div>
      <div className={`body${s.finish ? "" : " caret"}`}>{s.text}</div>
    </div>
  );
}

function SpecialistStream({ s }: { s: StreamView }): React.ReactElement {
  const [open, setOpen] = useState(false);
  if (!s.finish) {
    const lines = thinkingLines(s.thinking);
    const live = lines.length ? lines[lines.length - 1].slice(-72) : "…";
    return (
      <div className="fi act">
        <div className="ah">
          {s.stageLabel ? <span className="stg">{s.stageLabel}</span> : null}
          <span className="nm">{s.who ?? s.source.replace("specialist:", "")}</span>
          <span className="obs">observed · working</span>
        </div>
        <div className="live">
          <span className="shim">{live}</span>
        </div>
        <div className="tlines">
          {lines.slice(-3, -1).map((l, i) => (
            <div className="tline" key={i}>
              {l}
            </div>
          ))}
        </div>
        {s.tools.length ? (
          <div className="tools">
            {s.tools.map((t) => (
              <ToolChip key={t.callId} tool={t} />
            ))}
          </div>
        ) : null}
      </div>
    );
  }
  const secs = Math.max(1, Math.round(((s.closeTs ?? s.openTs) - s.openTs) / 1000));
  const lines = thinkingLines(s.thinking);
  return (
    <div className={`fi think${open ? " open" : ""}`}>
      <button className="th" onClick={() => setOpen(!open)}>
        <span className="ic">◈</span>
        <span className="who">{s.who ?? s.source.replace("specialist:", "")}</span>
        <span className="dur">thought for {secs}s</span>
        <span className="chev">▾</span>
      </button>
      <div className="bw">
        <div className="bd">
          <div className="bd-in">
            {lines.map((l, i) => (
              <div key={i}>{l}</div>
            ))}
            {s.finish === "error" ? <div>— stream ended early (error); retried.</div> : null}
          </div>
          {s.tools.length ? (
            <div className="tools">
              {s.tools.map((t) => (
                <ToolChip key={t.callId} tool={t} />
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function ProposeConfirm({ state, qid }: { state: State; qid: string }): React.ReactElement | null {
  const q = state.questions[qid];
  if (!q) {
    return null;
  }
  if (q.resolved) {
    return null; // its resolution chip (arm / res) carries the record
  }
  return (
    <div className="fi pcard">
      <div className="pv">{q.payload.voice ?? "Confirm?"}</div>
      <div className="row">
        {q.options.map((o) => (
          <button
            key={o.id}
            className={o.kind === "confirm" ? "go" : "ghostbtn"}
            onClick={() => answer(qid, o.id)}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function Item({ state, item }: { state: State; item: FeedItem }): React.ReactElement | null {
  switch (item.kind) {
    case "stream": {
      const s = state.streams[item.id];
      if (!s) {
        return null;
      }
      return s.source === "orchestrator" ? <OrchestratorBubble s={s} /> : <SpecialistStream s={s} />;
    }
    case "ask":
      return <div className="fi youask">you — {item.text}</div>;
    case "step":
      return <StepLine text={item.text} />;
    case "res":
      return (
        <div className="fi">
          <span className="res">
            <span>{item.text}</span>
          </span>
        </div>
      );
    case "warn":
      return (
        <div className="fi">
          <span className="warnpill">
            {item.spin ? <span className="sp" /> : "↻"}
            <span>{item.text}</span>
          </span>
        </div>
      );
    case "arm":
      return (
        <div className="fi">
          <span className="armchip">{item.text}</span>
        </div>
      );
    case "pc":
      return <ProposeConfirm state={state} qid={item.qid} />;
    case "sys":
      return <div className={`fi sysline${item.tone === "jade" ? " jade" : ""}`}>{item.text}</div>;
    default:
      return null;
  }
}

export interface FeedProps {
  state: State;
  composer: string;
  setComposer: (v: string) => void;
  onSend: () => void;
}

export function Feed({ state, composer, setComposer, onSend }: FeedProps): React.ReactElement {
  const itemsRef = useRef<HTMLDivElement | null>(null);
  const stick = useRef(true);

  useEffect(() => {
    const el = itemsRef.current;
    if (el && stick.current) {
      el.scrollTop = el.scrollHeight;
    }
  });

  const pipClass = state.ended
    ? state.ended.status === "approved"
      ? " ok"
      : " idle"
    : latestPending(state, "human_gate")
      ? " ok"
      : "";
  const liveTail = Object.values(state.streams).some((s) => !s.finish);
  const pastCut = state.feed.length - (liveTail ? 2 : 3);

  return (
    <div className="feed">
      <div className="feedh">
        <span className={`pip${pipClass}`} />
        <span className="t">Build feed</span>
        <span className="sub">{deriveFeedSub(state)}</span>
      </div>
      <div
        className="items"
        ref={itemsRef}
        onScroll={() => {
          const el = itemsRef.current;
          if (el) {
            stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
          }
        }}
      >
        {state.feed.length === 0 && !pendingOf(state, "gap").length ? (
          <div className="empty">
            <b>The build is starting.</b>
            <br />
            Everything that happens lands here — questions, thinking, gates, the verdict.
          </div>
        ) : null}
        {state.feed.map((item, i) => (
          <div key={`${item.kind}-${item.seq}-${i}`} className={i < pastCut ? "pastwrap" : "nowwrap"}>
            <Item state={state} item={item} />
          </div>
        ))}
      </div>
      <div className="composer">
        <div className="inwrap">
          <input
            value={composer}
            onChange={(e) => setComposer(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && composer.trim()) {
                onSend();
              }
            }}
            placeholder="Ask about this build…"
            aria-label="Ask about this build"
          />
          <button className="send" title="Send" onClick={() => composer.trim() && onSend()}>
            ↑
          </button>
        </div>
      </div>
    </div>
  );
}
