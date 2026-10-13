// src/App.jsx
// URL-driven entry:
//   ?job=<id>  -> LIVE   (EventSource "/stream/<id>")
//   ?replay=1  -> REPLAY (import the recorded sample-events.json, dispatch on a timer)
//   neither    -> the Upload view (POST /upload -> { job } -> set ?job=)
// The live/replay presenter renders the same generic <Rail/> + <Canvas/> (which nests
// the <Stepper/>). Nothing about a specific pipeline lives here.

import { useEffect, useMemo, useState } from "react";
import { useEventStream } from "./hooks/useEventStream.js";
import { Rail } from "./components/Rail.jsx";
import { Canvas } from "./components/Canvas.jsx";
import { Upload } from "./components/Upload.jsx";
import { Waiting } from "./components/Waiting.jsx";
import { STAGE_ORDER } from "./stages.js";

// Progress derived generically from the current stage (the prototype drove it from a
// local timeline; here the stage is the source of truth).
function progressPct(state) {
  if (state.ended || (state.stage && state.stage.name === "done")) return 100;
  const i = state.stage ? STAGE_ORDER.indexOf(state.stage.name) : -1;
  if (i < 0) return 0;
  return Math.round(((i + 1) / STAGE_ORDER.length) * 100);
}

function Presenter({ job, isReplay }) {
  // The recorded replay fixture carries demo cell values; keep it OUT of the live
  // (?job=) bundle by loading it as a separate chunk only when ?replay is present.
  const [replayEvents, setReplayEvents] = useState(null);
  useEffect(() => {
    if (!isReplay) return undefined;
    let live = true;
    import("./replay/sample-events.json").then((m) => {
      if (live) setReplayEvents(m.default);
    });
    return () => { live = false; };
  }, [isReplay]);

  const state = useEventStream({ job, replay: isReplay ? replayEvents : null });
  const pct = progressPct(state);
  // Live job, no events relayed yet -> show the "queued" handoff (job id + operator
  // commands) instead of an empty canvas. The first event flips this to the live view.
  const started = !!state.stage || state.order.length > 0 || state.sources.length > 0;
  const waiting = !!job && !isReplay && !started;
  // A generic peek at the state driving the render (no pipeline is hardcoded).
  const peek = {
    nodes: state.order.map((id) => ({
      id,
      kind: state.nodesById[id] && state.nodesById[id].kind,
    })),
    edges: state.edges.map((e) => ({ from: e.from, to: e.to })),
    result: state.result ? state.result.tier : null,
  };

  return (
    <div className="wrap">
      <div className="pbar">
        <i style={{ width: pct + "%" }} />
      </div>

      <header className="hd">
        <div className="brand">Building your ETL pipeline</div>
      </header>

      {waiting ? (
        <Waiting job={job} />
      ) : (
        <div className="main">
          <Rail state={state} />
          <Canvas state={state} />
        </div>
      )}

      {!waiting && (
        <div className="foot">
          <b>Generic presenter.</b> Everything above is rendered from this run's real
          artifacts &mdash; the graph, the labels, and the reasoning all come from the
          pipeline's own files. No pipeline is hardcoded; swap the artifacts and it redraws.
          <details className="peek">
            <summary>peek at the state driving this</summary>
            <pre>{JSON.stringify(peek, null, 2)}</pre>
          </details>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const params = useMemo(() => new URLSearchParams(window.location.search), []);
  const job = params.get("job");
  const replay = params.get("replay");

  if (!job && !replay) return <Upload />;
  return <Presenter job={job} isReplay={!!replay} />;
}
