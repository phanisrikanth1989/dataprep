// src/hooks/useEventStream.js
// Drives the pure reducer from either a live SSE stream or a recorded event array.
//
// LIVE  (job):    open EventSource("/stream/<job>"), reduce each JSON message, and
//                 close() on the terminal `end` event so the browser does NOT
//                 auto-reconnect and replay the whole log on top of the finished run.
// REPLAY (replay): dispatch a recorded events array through the SAME reducer on a
//                 timer (~250 ms apart) so the generic renderer animates exactly as
//                 it would from a live stream. Replay is a dev/verification harness,
//                 not a golden path -- it feeds RECORDED REAL events to one renderer.

import { useEffect, useReducer } from "react";
import { reduce, initialState } from "../state/reducer.js";

const REPLAY_INTERVAL_MS = 250;

export function useEventStream({ job, replay }) {
  // useReducer's signature is (reduce, initialState) and dispatch(event) calls
  // reduce(state, event) -- an exact fit for the pure reducer from Unit A.
  const [state, dispatch] = useReducer(reduce, initialState);

  useEffect(() => {
    if (replay && replay.length) {
      let i = 0;
      let timer = null;
      const pump = () => {
        dispatch(replay[i]);
        i += 1;
        if (i < replay.length) timer = setTimeout(pump, REPLAY_INTERVAL_MS);
      };
      timer = setTimeout(pump, REPLAY_INTERVAL_MS);
      return () => { if (timer) clearTimeout(timer); };
    }

    if (job) {
      const es = new EventSource("/stream/" + job);
      es.onmessage = (e) => {
        let event;
        try {
          event = JSON.parse(e.data);
        } catch {
          return; // ignore a non-JSON keep-alive / comment frame
        }
        dispatch(event);
        if (event && event.type === "end") {
          es.close(); // terminal: stop here, no reconnect+replay
        }
      };
      return () => es.close();
    }

    return undefined;
  }, [job, replay]);

  return state;
}
