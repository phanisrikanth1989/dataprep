// Root composition (ticket 15): full-bleed canvas, floating glass feed,
// brand + run/credit chips, the run spine, idle doors, lifecycle banners.
// All state arrives as 08 envelopes through the reducer; attach/replay
// reconstructs everything after reloads and crash-restarts.

import React, { useEffect, useReducer, useRef, useState } from "react";
import { ask, sendNotify, sendRequest, setHostHandler } from "./bridge";
import { Canvas } from "./Canvas";
import { Feed } from "./Feed";
import {
  Action,
  State,
  credits,
  deriveScene,
  deriveSpine,
  fmtElapsed,
  initialState,
  reducer,
} from "./state";
import type { AttachResult, Envelope, PickedFile } from "./types";

function useThemeSync(): void {
  useEffect(() => {
    const body = document.body;
    const apply = () => {
      const light =
        body.classList.contains("vscode-light") ||
        body.classList.contains("vscode-high-contrast-light");
      body.classList.toggle("light", light);
    };
    apply();
    const mo = new MutationObserver(apply);
    mo.observe(body, { attributes: true, attributeFilter: ["class"] });
    return () => mo.disconnect();
  }, []);
}

function useViewport(): { vw: number; vh: number } {
  const [size, setSize] = useState({ vw: window.innerWidth, vh: window.innerHeight });
  useEffect(() => {
    const onResize = () => setSize({ vw: window.innerWidth, vh: window.innerHeight });
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return size;
}

export function App(): React.ReactElement {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [composer, setComposer] = useState("");
  // A finished run stays on screen until a new one starts (ticket 08);
  // this flips back to the two doors so the next run can start.
  const [doorsOverride, setDoorsOverride] = useState(false);
  const stateRef = useRef<State>(state);
  stateRef.current = state;
  const { vw, vh } = useViewport();
  useThemeSync();

  useEffect(() => {
    setDoorsOverride(false); // a new run's events arrived: show the run
  }, [state.runId]);

  // ---- envelope pump: per-part forwarding coalesced to animation frames ----
  useEffect(() => {
    const buffer: Envelope[] = [];
    let scheduled = false;
    const flush = () => {
      scheduled = false;
      if (buffer.length) {
        const batch = buffer.splice(0, buffer.length);
        dispatch({ kind: "events", envelopes: batch });
      }
    };
    const attach = async (): Promise<void> => {
      try {
        const since = stateRef.current.runId ? stateRef.current.lastSeq : 0;
        const res = await sendRequest<AttachResult>("attach", { v: 1, since_seq: since });
        if (res.run && stateRef.current.runId && res.run.run_id !== stateRef.current.runId) {
          // A different run owns the journal now: replay it from the start.
          await sendRequest<AttachResult>("attach", { v: 1, since_seq: 0 });
        }
        dispatch({ kind: "attachNote", note: `attached v${res.v}` });
      } catch (e) {
        const err = e as Error & { code?: unknown };
        dispatch({
          kind: "attachNote",
          note: err.code === "core_down" ? "core starting…" : `attach failed: ${err.message}`,
        });
      }
    };
    setHostHandler((msg) => {
      if (msg.kind === "event") {
        buffer.push(msg.envelope);
        if (!scheduled) {
          scheduled = true;
          requestAnimationFrame(flush);
        }
      } else if (msg.kind === "lifecycle") {
        dispatch({ kind: "lifecycle", state: msg.state, detail: msg.detail, pid: msg.pid });
        if (msg.state === "spawned") {
          void attach();
        }
      }
    });
    void attach(); // core may already be up (webview reload)
  }, []);

  // ---- dev affordance: crash the core to demo restore (Ctrl+Alt+Shift+K) ---
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.altKey && e.shiftKey && (e.key === "K" || e.key === "k")) {
        sendNotify("skeleton.crash");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const scene = deriveScene(state);
  const showDoors = scene.mode === "idle" || (doorsOverride && Boolean(state.ended));
  const onSend = () => {
    const text = composer.trim();
    if (!text) {
      return;
    }
    dispatch({ kind: "localAsk", text });
    ask(text);
    setComposer("");
  };

  return (
    <div className="app">
      {!showDoors ? (
        <Canvas state={state} scene={scene} vw={vw} vh={vh} setComposer={setComposer} />
      ) : (
        <div className="canvas">
          <div className="dots" />
        </div>
      )}
      {showDoors ? (
        <Idle onBack={scene.mode !== "idle" ? () => setDoorsOverride(false) : undefined} />
      ) : null}
      <Chrome
        state={state}
        idleLook={showDoors}
        onNewBuild={() => setDoorsOverride(true)}
      />
      {!showDoors ? (
        <Feed state={state} composer={composer} setComposer={setComposer} onSend={onSend} />
      ) : null}
      <LifecycleBanner state={state} />
    </div>
  );
}

// ---- chrome ----------------------------------------------------------------

function Chrome({
  state,
  idleLook,
  onNewBuild,
}: {
  state: State;
  idleLook: boolean;
  onNewBuild: () => void;
}): React.ReactElement {
  const [now, setNow] = useState(Date.now());
  const [menuOpen, setMenuOpen] = useState(false);
  const running = Boolean(state.run) && !state.ended;
  useEffect(() => {
    if (!running) {
      return;
    }
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [running]);
  useEffect(() => {
    if (!menuOpen) {
      return;
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setMenuOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  // The doors screen is a clean slate: no chrome from the finished build.
  const showRunChrome = !idleLook && Boolean(state.run);
  const spine = idleLook
    ? { entries: [], word: "Two ways in", wordTone: "dim" as const }
    : deriveSpine(state);
  const cr = credits(state);
  const pipClass = state.ended
    ? state.ended.status === "approved"
      ? " ok"
      : " idle"
    : "";
  return (
    <>
      <div className="brand">
        <span className="arc" />
        <span className="t">ETL Studio</span>
        <span className="s">on DataPrep</span>
      </div>
      <div className="hud">
        {showRunChrome && state.run ? (
          <>
            <div className="chip">
              <span className={`pip${pipClass}`} />
              <b className="mono">{state.run.job}</b>
            </div>
            <div className="chip">
              <b className="mono">{cr.toFixed(1)}</b>
              <span>credits</span>
              <span className="mono" style={{ color: "var(--mute)" }}>
                {fmtElapsed(state.run.startedTs, state.ended ? state.ended.ts : now)}
              </span>
            </div>
            <div className="menuwrap">
              <button
                className={`dotsbtn${menuOpen ? " open" : ""}`}
                aria-label="Build actions"
                onClick={() => setMenuOpen((o) => !o)}
              >
                ⋯
              </button>
              {menuOpen ? (
                <>
                  <button className="menuveil" aria-hidden onClick={() => setMenuOpen(false)} />
                  <div className="hudmenu">
                    {state.ended ? (
                      <button
                        className="mitem"
                        onClick={() => {
                          setMenuOpen(false);
                          onNewBuild();
                        }}
                      >
                        <span className="plus">+</span>
                        New build
                      </button>
                    ) : null}
                    <button
                      className="mitem quiet"
                      title="Close ETL Studio — reopening restores this build"
                      onClick={() => sendNotify("shim.close_panel")}
                    >
                      Exit
                    </button>
                  </div>
                </>
              ) : null}
            </div>
          </>
        ) : (
          <div className="chip">
            <span className="pip idle" />
            <span style={{ color: "var(--mute)" }}>no build</span>
          </div>
        )}
      </div>
      <div className="spine">
        {spine.entries.map((e) =>
          e.kind === "gate" ? (
            <div
              key={`g-${e.key}`}
              className={`gd${e.state === "done" ? " done" : ""}${e.state === "hold" ? " hold" : ""}`}
              title={e.label}
            />
          ) : (
            <div
              key={`s-${e.key}`}
              className={`seg${e.state === "done" ? " done" : ""}${e.state === "active" ? " active" : ""}`}
              title={e.label}
            />
          )
        )}
        <span className={`word${spine.wordTone === "ok" ? " ok" : spine.wordTone === "dim" ? " dim" : ""}`}>
          {spine.word}
        </span>
      </div>
    </>
  );
}

function LifecycleBanner({ state }: { state: State }): React.ReactElement | null {
  const life = state.lifecycle;
  if (!life) {
    return null;
  }
  if (life.state === "crashed" || life.state === "restarting") {
    return (
      <div className="lifebanner">
        <span className="sp" />
        Agent core {life.state === "crashed" ? "crashed" : "is restarting"} — back in a moment.
        The build continues from its journal.
      </div>
    );
  }
  if (life.state === "dead") {
    return (
      <div className="lifebanner dead">
        Agent core is down{life.detail ? ` — ${life.detail}` : ""}.
        <button onClick={() => sendNotify("shim.restart")}>Restart core</button>
      </div>
    );
  }
  return null;
}

// ---- idle: the two front doors ---------------------------------------------

function Idle({ onBack }: { onBack?: () => void }): React.ReactElement {
  const [text, setText] = useState("");
  const [attachments, setAttachments] = useState<PickedFile[]>([]);
  const [picking, setPicking] = useState(false);

  const pickBrd = async () => {
    if (picking) {
      return;
    }
    setPicking(true);
    try {
      const file = await sendRequest<PickedFile | null>("editor.pick_file", {
        label: "Choose a BRD (.docx)",
        filters: { "Word documents": ["docx"], "All files": ["*"] },
      });
      if (file) {
        sendNotify("command.start_run", { door: "brd", brd_path: file.path, brd_name: file.name });
      }
    } catch {
      // shim not ready; the doors stay open
    } finally {
      setPicking(false);
    }
  };

  const pickAttachment = async () => {
    try {
      const file = await sendRequest<PickedFile | null>("editor.pick_file", {
        label: "Attach sample or expected data",
        filters: { "Data files": ["csv", "xlsx", "json"], "All files": ["*"] },
      });
      if (file) {
        setAttachments((a) => [...a, file]);
      }
    } catch {
      // ignore
    }
  };

  const start = () => {
    if (!text.trim()) {
      return;
    }
    sendNotify("command.start_run", {
      door: "typed",
      text: text.trim(),
      attachments: attachments.map((a) => a.path),
    });
  };

  return (
    <div className="idlewrap">
      <div className="wm">
        <span className="arc" />
        ETL <em>Studio</em>
      </div>
      <div className="lede">
        A requirement goes in. Agents design, configure and assemble the job on the DataPrep
        engine — and verify it against your data before you approve anything.
      </div>
      <div className="portals">
        <div className="portal">
          <h3>Start from a BRD</h3>
          <p>Drop a .docx. Rules are extracted; anything unclear becomes a question, never an assumption.</p>
          <button className="drop" onClick={pickBrd}>
            <span className="ic">⇪</span>
            {picking ? "Choosing…" : "Drop .docx — or browse"}
            <i>tables · rules · sample data</i>
          </button>
        </div>
        <div className="portal">
          <h3>Describe the job</h3>
          <p>Type it. Attach sample and expected data to earn a verified build.</p>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Keep settled trades, add account and price details, compute each trade’s value…"
          />
          <div className="row">
            <button className="ghostbtn" onClick={pickAttachment}>
              {attachments.length ? `${attachments.length} attached` : "Attach data"}
            </button>
            <button className="go" onClick={start}>
              Start build
            </button>
          </div>
        </div>
      </div>
      <div className="fine">Every gate is yours — the spec, the generated code, and the final approval.</div>
      {onBack ? (
        <button className="fine backlink" onClick={onBack}>
          Back to the finished build
        </button>
      ) : null}
    </div>
  );
}
