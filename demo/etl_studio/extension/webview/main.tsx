// ETL Studio webview (walking skeleton). Engineering surface only --
// ticket 12 owns the real look and feel. Everything shown is real run
// state: envelopes from the journal, shim lifecycle, streamed parts.

import React, { useEffect, useReducer, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import type { AttachResult, Envelope, HostMessage, LifecycleState } from "./types";

declare function acquireVsCodeApi(): { postMessage(msg: unknown): void };
const vscodeApi = acquireVsCodeApi();

// ---- shim bridge -----------------------------------------------------------

let nextRequestId = 1;
const pending = new Map<
  number,
  { resolve: (v: unknown) => void; reject: (e: Error & { code?: unknown }) => void }
>();

function sendRequest<T>(method: string, params?: unknown): Promise<T> {
  const id = nextRequestId++;
  const promise = new Promise<T>((resolve, reject) => {
    pending.set(id, { resolve: resolve as (v: unknown) => void, reject });
  });
  vscodeApi.postMessage({ kind: "request", id, method, params });
  return promise;
}

function sendNotify(method: string, params?: unknown): void {
  vscodeApi.postMessage({ kind: "notify", method, params });
}

// ---- state -----------------------------------------------------------------

interface StreamState {
  streamId: string;
  provider?: string;
  model?: { vendor: string; id: string; name: string } | null;
  prompt?: string;
  text: string;
  thinking: string;
  usage?: { raw?: Record<string, unknown>; total_nano_aiu?: number | null };
  finish?: string; // set on close
}

interface State {
  lastSeq: number;
  events: Envelope[];
  streams: Record<string, StreamState>;
  streamOrder: string[];
  lifecycle: { state: LifecycleState; detail?: string; pid?: number } | null;
  run: { run_id: string; last_seq: number } | null;
}

const initialState: State = {
  lastSeq: 0,
  events: [],
  streams: {},
  streamOrder: [],
  lifecycle: null,
  run: null,
};

type Action =
  | { kind: "event"; envelope: Envelope }
  | { kind: "lifecycle"; state: LifecycleState; detail?: string; pid?: number }
  | { kind: "attached"; run: { run_id: string; last_seq: number } | null };

const FEED_CAP = 500;

function reduceEnvelope(state: State, env: Envelope): State {
  if (env.seq <= state.lastSeq) {
    return state; // replay overlap: seq-idempotent by design
  }
  const events = [...state.events, env].slice(-FEED_CAP);
  let { streams, streamOrder } = state;
  const p = env.payload ?? {};
  const sid = typeof p.stream_id === "string" ? p.stream_id : undefined;

  if (env.type === "stream.open" && sid) {
    streams = {
      ...streams,
      [sid]: {
        streamId: sid,
        provider: p.provider,
        model: p.model ?? null,
        prompt: p.prompt,
        text: "",
        thinking: "",
      },
    };
    streamOrder = [...streamOrder, sid];
  } else if (env.type === "stream.delta" && sid && streams[sid]) {
    const part = p.part ?? {};
    const s = streams[sid];
    if (part.kind === "text_delta") {
      streams = { ...streams, [sid]: { ...s, text: s.text + String(part.text ?? "") } };
    } else if (part.kind === "thinking_delta") {
      streams = {
        ...streams,
        [sid]: { ...s, thinking: s.thinking + String(part.text ?? "") },
      };
    } else if (part.kind === "usage") {
      streams = {
        ...streams,
        [sid]: { ...s, usage: { raw: part.raw, total_nano_aiu: part.total_nano_aiu } },
      };
    }
    // unknown part kinds: skipped here, still visible in the feed
  } else if (env.type === "stream.close" && sid && streams[sid]) {
    streams = {
      ...streams,
      [sid]: { ...streams[sid], finish: String(p.finish_reason ?? "unknown") },
    };
  }
  return { ...state, lastSeq: env.seq, events, streams, streamOrder };
}

function reducer(state: State, action: Action): State {
  switch (action.kind) {
    case "event":
      return reduceEnvelope(state, action.envelope);
    case "lifecycle":
      return {
        ...state,
        lifecycle: { state: action.state, detail: action.detail, pid: action.pid },
      };
    case "attached":
      return { ...state, run: action.run };
    default:
      return state;
  }
}

// ---- app -------------------------------------------------------------------

function summarizePayload(env: Envelope): string {
  try {
    const text = JSON.stringify(env.payload);
    return text.length > 140 ? text.slice(0, 140) + "..." : text;
  } catch {
    return "(unrenderable payload)";
  }
}

function App(): React.ReactElement {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [prompt, setPrompt] = useState("stream me an echo");
  const [attachNote, setAttachNote] = useState<string>("attaching...");
  const lastSeqRef = useRef(0);
  const feedRef = useRef<HTMLDivElement | null>(null);
  lastSeqRef.current = state.lastSeq;

  useEffect(() => {
    const onMessage = (e: MessageEvent) => {
      const msg = e.data as HostMessage;
      if (!msg || typeof msg !== "object") {
        return;
      }
      if (msg.kind === "event") {
        dispatch({ kind: "event", envelope: msg.envelope });
      } else if (msg.kind === "lifecycle") {
        dispatch({
          kind: "lifecycle",
          state: msg.state,
          detail: msg.detail,
          pid: msg.pid,
        });
        if (msg.state === "spawned") {
          // Fresh load, reload mid-run, or return after a crash: declare
          // what we last saw; the journal replays everything since.
          void attach();
        }
      } else if (msg.kind === "response") {
        const entry = pending.get(msg.id);
        if (entry) {
          pending.delete(msg.id);
          if (msg.error) {
            const err = new Error(msg.error.message) as Error & { code?: unknown };
            err.code = msg.error.code;
            entry.reject(err);
          } else {
            entry.resolve(msg.result);
          }
        }
      }
    };
    window.addEventListener("message", onMessage);
    void attach(); // core may already be up (webview reload)
    return () => window.removeEventListener("message", onMessage);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const el = feedRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [state.events.length]);

  async function attach(): Promise<void> {
    try {
      const res = await sendRequest<AttachResult>("attach", {
        v: 1,
        since_seq: lastSeqRef.current,
      });
      dispatch({ kind: "attached", run: res.run ?? null });
      setAttachNote(`attached v${res.v}`);
    } catch (e) {
      const err = e as Error & { code?: unknown };
      setAttachNote(
        err.code === "core_down" ? "core not running yet" : `attach failed: ${err.message}`
      );
    }
  }

  const life = state.lifecycle;
  const coreUp = life?.state === "spawned";
  const openStreams = state.streamOrder
    .map((id) => state.streams[id])
    .filter((s) => s && !s.finish);

  return (
    <div className="app">
      <header>
        <div className={`dot ${life?.state ?? "unknown"}`} />
        <h1>ETL Studio</h1>
        <span className="tag">walking skeleton</span>
        <span className="meta">
          core: {life ? `${life.state}${life.pid ? ` (pid ${life.pid})` : ""}` : "-"}
          {" | "}
          {attachNote}
          {state.run ? ` | run ${state.run.run_id}, journal seq ${state.lastSeq}` : ""}
        </span>
      </header>

      {life && (life.state === "crashed" || life.state === "restarting") && (
        <div className="banner warn">
          Agent core {life.state === "crashed" ? "crashed" : "is restarting"}
          {life.detail ? ` -- ${life.detail}` : ""}. Restarting automatically...
        </div>
      )}
      {life?.state === "dead" && (
        <div className="banner error">
          Agent core is down{life.detail ? ` -- ${life.detail}` : ""}.
          <button onClick={() => sendNotify("shim.restart")}>Restart core</button>
        </div>
      )}

      <section className="controls">
        <button
          disabled={!coreUp}
          onClick={() => sendNotify("skeleton.ping", { nonce: `n${Date.now()}` })}
        >
          Ping core
        </button>
        <input
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && coreUp) {
              sendNotify("skeleton.echo", { prompt });
            }
          }}
          placeholder="prompt for the LM echo"
        />
        <button disabled={!coreUp} onClick={() => sendNotify("skeleton.echo", { prompt })}>
          LM echo
        </button>
        {openStreams.map((s) => (
          <button
            key={s.streamId}
            className="cancel"
            onClick={() => sendNotify("skeleton.cancel", { stream_id: s.streamId })}
          >
            Cancel {s.streamId}
          </button>
        ))}
        <span className="spacer" />
        <button
          className="danger"
          disabled={!coreUp}
          title="Hard-exit the core to prove the restart banner + seq continuity"
          onClick={() => sendNotify("skeleton.crash")}
        >
          Crash core (dev)
        </button>
      </section>

      <section className="streams">
        {state.streamOrder.length === 0 && (
          <div className="empty">
            No streams yet. Ping proves the webview-&gt;core round trip; LM echo
            streams through the provider port.
          </div>
        )}
        {state.streamOrder.map((id) => {
          const s = state.streams[id];
          if (!s) {
            return null;
          }
          const credits =
            s.usage?.total_nano_aiu != null ? s.usage.total_nano_aiu / 1e9 : null;
          return (
            <div key={id} className={`stream ${s.finish ?? "live"}`}>
              <div className="stream-head">
                <code>{id}</code>
                <span>
                  {s.provider ?? "?"}
                  {s.model ? ` / ${s.model.vendor}:${s.model.id}` : ""}
                </span>
                <span className={`chip ${s.finish ?? "live"}`}>{s.finish ?? "streaming"}</span>
                {credits != null && (
                  <span className="chip usage">{credits.toFixed(4)} AIU</span>
                )}
              </div>
              {s.prompt && <div className="prompt">&gt; {s.prompt}</div>}
              {s.thinking && <div className="thinking">{s.thinking}</div>}
              <div className="text">{s.text || "..."}</div>
            </div>
          );
        })}
      </section>

      <section className="feed" ref={feedRef}>
        {state.events.map((env) => (
          <div key={env.seq} className="feed-line">
            <span className="seq">#{env.seq}</span>
            <span className="source">[{env.source}]</span>
            <span className={`type ${env.type.split(".")[0]}`}>{env.type}</span>
            <span className="payload">{summarizePayload(env)}</span>
          </div>
        ))}
      </section>
    </div>
  );
}

// ---- styles (VS Code theme tokens only; ticket 12 owns real design) --------

const css = `
  * { box-sizing: border-box; }
  body { margin: 0; padding: 0; font-family: var(--vscode-font-family); color: var(--vscode-foreground); background: var(--vscode-editor-background); }
  .app { display: flex; flex-direction: column; height: 100vh; }
  header { display: flex; align-items: center; gap: 8px; padding: 8px 12px; border-bottom: 1px solid var(--vscode-panel-border); }
  header h1 { font-size: 14px; margin: 0; }
  .tag { font-size: 11px; opacity: 0.7; border: 1px solid var(--vscode-panel-border); border-radius: 8px; padding: 1px 8px; }
  .meta { margin-left: auto; font-size: 11px; opacity: 0.75; }
  .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--vscode-charts-yellow); }
  .dot.spawned { background: var(--vscode-charts-green); }
  .dot.crashed, .dot.dead { background: var(--vscode-charts-red); }
  .dot.restarting { background: var(--vscode-charts-orange); }
  .banner { padding: 6px 12px; font-size: 12px; display: flex; align-items: center; gap: 10px; }
  .banner.warn { background: color-mix(in srgb, var(--vscode-charts-orange) 18%, transparent); }
  .banner.error { background: color-mix(in srgb, var(--vscode-charts-red) 20%, transparent); }
  .controls { display: flex; align-items: center; gap: 8px; padding: 8px 12px; flex-wrap: wrap; }
  .controls .spacer { flex: 1; }
  .controls input { flex: 1 1 220px; min-width: 160px; padding: 4px 8px; background: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--vscode-input-border, transparent); }
  button { background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; padding: 4px 10px; cursor: pointer; }
  button:disabled { opacity: 0.45; cursor: default; }
  button.cancel { background: var(--vscode-button-secondaryBackground); color: var(--vscode-button-secondaryForeground); }
  button.danger { background: color-mix(in srgb, var(--vscode-charts-red) 55%, var(--vscode-button-background)); }
  .streams { padding: 4px 12px; overflow-y: auto; max-height: 45%; }
  .empty { font-size: 12px; opacity: 0.65; padding: 12px 0; }
  .stream { border: 1px solid var(--vscode-panel-border); border-radius: 6px; padding: 8px 10px; margin: 6px 0; }
  .stream-head { display: flex; gap: 10px; align-items: center; font-size: 11px; opacity: 0.9; margin-bottom: 6px; }
  .chip { border-radius: 8px; padding: 0 8px; font-size: 10px; border: 1px solid var(--vscode-panel-border); }
  .chip.live { color: var(--vscode-charts-green); }
  .chip.canceled { color: var(--vscode-charts-orange); }
  .chip.error { color: var(--vscode-charts-red); }
  .prompt { font-size: 12px; opacity: 0.7; margin-bottom: 4px; }
  .thinking { font-size: 12px; font-style: italic; opacity: 0.65; white-space: pre-wrap; }
  .text { font-size: 13px; white-space: pre-wrap; }
  .feed { flex: 1; overflow-y: auto; border-top: 1px solid var(--vscode-panel-border); padding: 6px 12px; font-family: var(--vscode-editor-font-family); font-size: 11px; }
  .feed-line { display: flex; gap: 8px; padding: 1px 0; white-space: nowrap; }
  .seq { opacity: 0.5; min-width: 34px; }
  .source { color: var(--vscode-charts-blue); }
  .type { min-width: 150px; }
  .type.stream { color: var(--vscode-charts-green); }
  .type.health { color: var(--vscode-charts-orange); }
  .type.skeleton { color: var(--vscode-charts-purple); }
  .payload { opacity: 0.75; overflow: hidden; text-overflow: ellipsis; }
`;

const style = document.createElement("style");
style.textContent = css;
document.head.appendChild(style);

const rootEl = document.getElementById("root");
if (rootEl) {
  createRoot(rootEl).render(<App />);
}
