// Pure reducer over ticket 08's envelope (attach/replay-safe: seq-idempotent
// within a run, full reset when run_id changes -- a new run is a fresh
// journal). The five beats of the design are EMERGENT states of this store,
// never modes: idle = no run.started, questions = pending gap round,
// streaming = open specialist streams, gate/verdict = pending question kinds.

import type { Envelope, ItineraryEntry, LifecycleState, QuestionOption } from "./types";

// ---- views -----------------------------------------------------------------

export interface ToolView {
  callId: string;
  name: string;
  args?: Record<string, any>;
  done: boolean;
  ok?: boolean;
  warn?: string;
  note?: string;
}

export interface StreamView {
  id: string;
  source: string;
  who?: string;
  stageLabel?: string;
  label?: string;
  inReplyTo?: string;
  text: string;
  thinking: string;
  tools: ToolView[];
  usageNano: number | null;
  finish?: string;
  openTs: number;
  closeTs?: number;
}

export interface QuestionView {
  id: string;
  kind: string;
  seq: number;
  payload: Record<string, any>;
  options: QuestionOption[];
  resolved?: { choice: string; freeText?: string | null; note?: string };
}

export interface StageView {
  key: string;
  label: string;
  done: boolean;
  iteration: number;
}

export type FeedItem =
  | { kind: "stream"; seq: number; id: string }
  | { kind: "ask"; seq: number; text: string }
  | { kind: "step"; seq: number; text: string }
  | { kind: "res"; seq: number; text: string; roundId?: string }
  | { kind: "warn"; seq: number; text: string; spin?: boolean }
  | { kind: "arm"; seq: number; text: string }
  | { kind: "pc"; seq: number; qid: string }
  | { kind: "sys"; seq: number; text: string; tone?: "jade" };

export interface RunMeta {
  job: string;
  door: string;
  tier?: string;
  itinerary: ItineraryEntry[];
  startedTs: number;
}

export interface State {
  lastSeq: number;
  runId: string | null;
  run: RunMeta | null;
  ended: { status: string; note?: string; ts: number } | null;
  crashRestored: boolean;
  stages: Record<string, StageView>;
  stageOrder: string[];
  currentStage: string | null;
  progress: Record<string, "active" | "configured">;
  activeNode: string | null;
  spec: Record<string, any> | null; // latest spec artifact fields
  flow: { nodes: any[]; edges: string[][]; iteration: number } | null;
  streams: Record<string, StreamView>;
  questions: Record<string, QuestionView>;
  questionOrder: string[];
  roundNotes: Record<string, string[]>;
  feed: FeedItem[];
  creditsNano: number;
  holdArmed: boolean;
  lifecycle: { state: LifecycleState; detail?: string; pid?: number } | null;
  attachNote: string;
}

export const initialState: State = {
  lastSeq: 0,
  runId: null,
  run: null,
  ended: null,
  crashRestored: false,
  stages: {},
  stageOrder: [],
  currentStage: null,
  progress: {},
  activeNode: null,
  spec: null,
  flow: null,
  streams: {},
  questions: {},
  questionOrder: [],
  roundNotes: {},
  feed: [],
  creditsNano: 0,
  holdArmed: false,
  lifecycle: null,
  attachNote: "attaching…",
};

export type Action =
  | { kind: "events"; envelopes: Envelope[] }
  | { kind: "lifecycle"; state: LifecycleState; detail?: string; pid?: number }
  | { kind: "attachNote"; note: string }
  | { kind: "localAsk"; text: string };

const FEED_CAP = 400;

function resetRun(state: State, runId: string): State {
  return {
    ...initialState,
    lifecycle: state.lifecycle,
    attachNote: state.attachNote,
    runId,
    lastSeq: 0,
  };
}

function pushFeed(state: State, item: FeedItem): State {
  return { ...state, feed: [...state.feed, item].slice(-FEED_CAP) };
}

function reduceEnvelope(prev: State, env: Envelope): State {
  let state = prev;
  if (env.run_id !== state.runId) {
    state = resetRun(state, env.run_id);
  }
  if (env.seq <= state.lastSeq) {
    return prev === state ? prev : state; // replay overlap: seq-idempotent
  }
  state = { ...state, lastSeq: env.seq };
  const p = env.payload ?? {};

  switch (env.type) {
    case "run.started": {
      const itinerary: ItineraryEntry[] = Array.isArray(p.itinerary) ? p.itinerary : [];
      const stages: Record<string, StageView> = {};
      const order: string[] = [];
      for (const e of itinerary) {
        if (e.kind === "stage") {
          stages[e.key] = { key: e.key, label: e.label, done: false, iteration: 1 };
          order.push(e.key);
        }
      }
      return {
        ...state,
        run: {
          job: String(p.job ?? ""),
          door: String(p.door ?? ""),
          tier: p.tier,
          itinerary,
          startedTs: Date.parse(env.ts) || Date.now(),
        },
        stages,
        stageOrder: order,
      };
    }
    case "run.crash_restored":
      return pushFeed(
        { ...state, crashRestored: true },
        { kind: "sys", seq: env.seq, text: String(p.note ?? "The core restarted; the build continues from the journal.") }
      );
    case "run.ended": {
      const status = String(p.status ?? "ended");
      const s2 = {
        ...state,
        ended: { status, note: p.note, ts: Date.parse(env.ts) || Date.now() },
        activeNode: null,
        currentStage: null,
      };
      return pushFeed(s2, {
        kind: "sys",
        seq: env.seq,
        text: String(p.note ?? `Build ${status}.`),
        tone: status === "approved" ? "jade" : undefined,
      });
    }
    case "stage.started": {
      const key = String(p.stage ?? "");
      if (!state.stages[key]) {
        return state;
      }
      const idx = state.stageOrder.indexOf(key);
      const stages = { ...state.stages };
      stages[key] = { ...stages[key], done: false, iteration: Number(p.iteration ?? 1) };
      // Directed iteration: forward stages un-fill while they wait to re-run
      // (ticket 13 -- regression legible, never hidden).
      for (const k of state.stageOrder.slice(idx + 1)) {
        if (stages[k].done) {
          stages[k] = { ...stages[k], done: false };
        }
      }
      let next: State = { ...state, stages, currentStage: key };
      if (key === "configure" && Number(p.iteration ?? 1) === 1) {
        next = { ...next, progress: {}, activeNode: null };
      }
      return next;
    }
    case "stage.completed": {
      const key = String(p.stage ?? "");
      const stages = state.stages[key]
        ? { ...state.stages, [key]: { ...state.stages[key], done: true } }
        : state.stages;
      let next: State = {
        ...state,
        stages,
        currentStage: state.currentStage === key ? null : state.currentStage,
        activeNode: key === "configure" ? null : state.activeNode,
      };
      if (typeof p.note === "string" && p.note) {
        next = pushFeed(next, { kind: "step", seq: env.seq, text: p.note });
      }
      return next;
    }
    case "stage.artifact_written": {
      let next = state;
      const fields = p.fields ?? null;
      if (p.kind === "spec" && fields) {
        next = { ...next, spec: fields };
      } else if (p.kind === "flow" && fields) {
        next = {
          ...next,
          flow: {
            nodes: fields.nodes ?? [],
            edges: fields.edges ?? [],
            iteration: Number(p.iteration ?? 1),
          },
        };
      }
      if (typeof p.note === "string" && p.note) {
        next = pushFeed(next, { kind: "step", seq: env.seq, text: p.note });
      }
      return next;
    }
    case "stage.progress": {
      const nodeId = String(p.node_id ?? "");
      const st = String(p.state ?? "");
      if (!nodeId) {
        return state;
      }
      if (st === "active") {
        return { ...state, activeNode: nodeId, progress: { ...state.progress, [nodeId]: "active" } };
      }
      return {
        ...state,
        activeNode: state.activeNode === nodeId ? null : state.activeNode,
        progress: { ...state.progress, [nodeId]: "configured" },
      };
    }
    case "stage.loop_attempt":
      return pushFeed(state, {
        kind: "warn",
        seq: env.seq,
        text: String(p.note ?? `attempt ${p.k} of ${p.n}`),
      });
    case "question.raised": {
      const qid = String(p.question_id ?? "");
      if (!qid || state.questions[qid]) {
        return state;
      }
      const q: QuestionView = {
        id: qid,
        kind: String(p.kind ?? ""),
        seq: env.seq,
        payload: p,
        options: Array.isArray(p.options) ? p.options : [],
      };
      let next: State = {
        ...state,
        questions: { ...state.questions, [qid]: q },
        questionOrder: [...state.questionOrder, qid],
      };
      if (q.kind === "hold") {
        next = { ...next, holdArmed: false };
      }
      if (q.kind === "propose_confirm") {
        next = pushFeed(next, { kind: "pc", seq: env.seq, qid });
      }
      return next;
    }
    case "question.resolved": {
      const qid = String(p.question_id ?? "");
      const q = state.questions[qid];
      if (!q || q.resolved) {
        return state;
      }
      const questions = {
        ...state.questions,
        [qid]: {
          ...q,
          resolved: { choice: String(p.choice ?? ""), freeText: p.free_text, note: p.note },
        },
      };
      let next: State = { ...state, questions };
      const note = String(p.note ?? "");
      if (q.kind === "gap") {
        const roundId = String(p.round_id ?? "r?");
        const notes = [...(state.roundNotes[roundId] ?? []), note];
        next = { ...next, roundNotes: { ...state.roundNotes, [roundId]: notes } };
        const total = Object.values(state.questions).filter(
          (qq) => qq.kind === "gap" && qq.payload.round_id === roundId
        ).length;
        const k = q.payload.round?.k ?? 1;
        const text = `Round ${k}${notes.length >= total ? " answered" : ""} — ${notes.join(" · ")}`;
        const existing = next.feed.find((f) => f.kind === "res" && f.roundId === roundId);
        if (existing) {
          next = {
            ...next,
            feed: next.feed.map((f) =>
              f.kind === "res" && f.roundId === roundId ? { ...f, text } : f
            ),
          };
        } else {
          next = pushFeed(next, { kind: "res", seq: env.seq, text, roundId });
        }
        return next;
      }
      if (q.kind === "propose_confirm") {
        if (p.choice === "confirm") {
          next = { ...next, holdArmed: true };
          return pushFeed(next, { kind: "arm", seq: env.seq, text: note });
        }
        return pushFeed(next, { kind: "res", seq: env.seq, text: note });
      }
      if (q.kind === "hold") {
        next = { ...next, holdArmed: false };
      }
      return note ? pushFeed(next, { kind: "res", seq: env.seq, text: note }) : next;
    }
    case "stream.open": {
      const sid = String(p.stream_id ?? "");
      if (!sid) {
        return state;
      }
      const view: StreamView = {
        id: sid,
        source: env.source,
        who: p.who,
        stageLabel: p.stage_label,
        label: p.label,
        inReplyTo: p.in_reply_to,
        text: "",
        thinking: "",
        tools: [],
        usageNano: null,
        openTs: Date.parse(env.ts) || Date.now(),
      };
      return pushFeed(
        { ...state, streams: { ...state.streams, [sid]: view } },
        { kind: "stream", seq: env.seq, id: sid }
      );
    }
    case "stream.delta": {
      const sid = String(p.stream_id ?? "");
      const s = state.streams[sid];
      const part = p.part ?? {};
      if (!s) {
        return state;
      }
      if (part.kind === "text_delta") {
        return {
          ...state,
          streams: { ...state.streams, [sid]: { ...s, text: s.text + String(part.text ?? "") } },
        };
      }
      if (part.kind === "thinking_delta") {
        return {
          ...state,
          streams: {
            ...state.streams,
            [sid]: { ...s, thinking: s.thinking + String(part.text ?? "") },
          },
        };
      }
      if (part.kind === "tool_call") {
        const tool: ToolView = {
          callId: String(part.call_id ?? ""),
          name: String(part.name ?? "tool"),
          args: part.args,
          done: false,
        };
        return {
          ...state,
          streams: { ...state.streams, [sid]: { ...s, tools: [...s.tools, tool] } },
        };
      }
      if (part.kind === "tool_result") {
        const tools = s.tools.map((t) =>
          t.callId === String(part.call_id ?? "")
            ? { ...t, done: true, ok: part.ok !== false, warn: part.warn, note: part.note }
            : t
        );
        return { ...state, streams: { ...state.streams, [sid]: { ...s, tools } } };
      }
      if (part.kind === "usage") {
        const nano = Number(part.total_nano_aiu ?? 0) || 0;
        return {
          ...state,
          creditsNano: state.creditsNano + nano,
          streams: { ...state.streams, [sid]: { ...s, usageNano: nano } },
        };
      }
      return state; // unknown part kinds skipped (forward-compat law)
    }
    case "stream.close": {
      const sid = String(p.stream_id ?? "");
      const s = state.streams[sid];
      if (!s) {
        return state;
      }
      return {
        ...state,
        streams: {
          ...state.streams,
          [sid]: {
            ...s,
            finish: String(p.finish_reason ?? "unknown"),
            closeTs: Date.parse(env.ts) || Date.now(),
          },
        },
      };
    }
    case "health.retry":
      return pushFeed(state, {
        kind: "warn",
        seq: env.seq,
        text: `rate-limited — retrying (attempt ${p.attempt ?? "?"} of ${p.of ?? "?"}) · backoff ${p.backoff_s ?? "?"}s`,
      });
    case "health.error":
      return pushFeed(state, {
        kind: "warn",
        seq: env.seq,
        text: `${p.taxonomy ?? "error"} — ${p.message ?? ""}`,
      });
    default:
      return state; // skip-unknown: vocabulary can grow without lockstep releases
  }
}

export function reducer(state: State, action: Action): State {
  switch (action.kind) {
    case "events": {
      let next = state;
      for (const env of action.envelopes) {
        next = reduceEnvelope(next, env);
      }
      return next;
    }
    case "lifecycle":
      return {
        ...state,
        lifecycle: { state: action.state, detail: action.detail, pid: action.pid },
      };
    case "attachNote":
      return { ...state, attachNote: action.note };
    case "localAsk":
      return pushFeed(state, { kind: "ask", seq: state.lastSeq, text: action.text });
    default:
      return state;
  }
}

// ---- selectors (view state derives; beats emerge here) ---------------------

export const pendingOf = (state: State, kind: string): QuestionView[] =>
  state.questionOrder
    .map((id) => state.questions[id])
    .filter((q): q is QuestionView => Boolean(q && q.kind === kind && !q.resolved));

export const latestPending = (state: State, kind: string): QuestionView | null => {
  const all = pendingOf(state, kind);
  return all.length ? all[all.length - 1] : null;
};

export const latestOf = (state: State, kind: string): QuestionView | null => {
  const ids = state.questionOrder.filter((id) => state.questions[id]?.kind === kind);
  return ids.length ? state.questions[ids[ids.length - 1]] : null;
};

export type Scene =
  | { mode: "idle" }
  | { mode: "blank" }
  | { mode: "scatter"; spot: boolean; hotRules: string[]; card: "gaps" | "spec" | null }
  | {
      mode: "dag";
      camera: { type: "fit"; pad: number } | { type: "focus"; node: string; s: number };
      gatehold: boolean;
      settled: boolean;
      glow: string | null;
      hot: string | null;
      wash: boolean;
      jsweep: boolean;
      card: "code" | "verdict" | "hold" | null;
    };

export function deriveScene(state: State): Scene {
  if (!state.run) {
    return { mode: "idle" };
  }
  const gaps = pendingOf(state, "gap");
  const spec = latestPending(state, "spec_gate");
  const code = latestPending(state, "code_gate");
  const human = latestPending(state, "human_gate");
  const hold = latestPending(state, "hold");
  const humanEver = latestOf(state, "human_gate");
  const approved = state.ended?.status === "approved";

  if (!state.flow || spec) {
    if (!state.spec) {
      return { mode: "blank" };
    }
    if (gaps.length) {
      return {
        mode: "scatter",
        spot: true,
        hotRules: gaps.map((q) => String(q.payload.rule_id ?? "")),
        card: "gaps",
      };
    }
    if (spec) {
      const resolved = (state.spec.rules ?? [])
        .filter((r: any) => r.gap)
        .map((r: any) => String(r.id));
      return { mode: "scatter", spot: true, hotRules: resolved, card: "spec" };
    }
    return { mode: "scatter", spot: false, hotRules: [], card: null };
  }

  const outputNode: string | null =
    (state.flow.nodes.find((n: any) => n.kind === "output") ?? {}).id ?? null;
  const codeNode: string | null = code
    ? String(code.payload.cells?.[0]?.node_id ?? "") || null
    : null;

  if (code) {
    return {
      mode: "dag",
      camera: codeNode ? { type: "focus", node: codeNode, s: 0.74 } : { type: "fit", pad: 0.96 },
      gatehold: true,
      settled: false,
      glow: null,
      hot: codeNode,
      wash: true,
      jsweep: false,
      card: "code",
    };
  }
  if (human || approved) {
    return {
      mode: "dag",
      camera: { type: "fit", pad: 0.98 },
      gatehold: false,
      settled: true,
      glow: outputNode,
      hot: null,
      wash: false,
      jsweep: Boolean(humanEver && !humanEver.resolved),
      card: human ? "verdict" : null,
    };
  }
  if (hold) {
    return {
      mode: "dag",
      camera: { type: "fit", pad: 0.96 },
      gatehold: false,
      settled: false,
      glow: null,
      hot: null,
      wash: false,
      jsweep: false,
      card: "hold",
    };
  }
  if (state.currentStage === "configure" && state.activeNode) {
    return {
      mode: "dag",
      camera: { type: "focus", node: state.activeNode, s: 0.9 },
      gatehold: false,
      settled: false,
      glow: null,
      hot: null,
      wash: false,
      jsweep: false,
      card: null,
    };
  }
  return {
    mode: "dag",
    camera: { type: "fit", pad: 0.96 },
    gatehold: false,
    settled: false,
    glow: null,
    hot: null,
    wash: false,
    jsweep: false,
    card: null,
  };
}

export interface SpineEntry {
  kind: "stage" | "gate";
  key: string;
  label: string;
  state: "todo" | "active" | "done" | "hold";
}

export function deriveSpine(state: State): { entries: SpineEntry[]; word: string; wordTone: "em" | "ok" | "dim" } {
  if (!state.run) {
    return { entries: [], word: "Ready", wordTone: "dim" };
  }
  const gateState = (key: string): "todo" | "done" | "hold" => {
    const kind = key === "spec" ? "spec_gate" : key === "code" ? "code_gate" : "human_gate";
    const latest = latestOf(state, kind);
    if (!latest) {
      return "todo";
    }
    if (!latest.resolved) {
      return "hold";
    }
    return latest.resolved.choice === "approve" ? "done" : "todo";
  };
  const entries: SpineEntry[] = state.run.itinerary.map((e) => {
    if (e.kind === "gate") {
      return { kind: "gate", key: e.key, label: e.label, state: gateState(e.key) };
    }
    const sv = state.stages[e.key];
    const st: SpineEntry["state"] = sv?.done
      ? "done"
      : state.currentStage === e.key
        ? "active"
        : "todo";
    return { kind: "stage", key: e.key, label: e.label, state: st };
  });

  const hold = latestPending(state, "hold");
  const human = latestPending(state, "human_gate");
  if (hold) {
    // The armed window is a feed chip (ticket 13); the spine word waits for
    // the actual hold at the boundary.
    return { entries, word: "Holding", wordTone: "em" };
  }
  if (state.ended) {
    return {
      entries,
      word: state.ended.status === "approved" ? "Approved" : state.ended.status === "stopped" ? "Stopped" : "Ended",
      wordTone: state.ended.status === "approved" ? "ok" : "dim",
    };
  }
  if (human) {
    return { entries, word: "Human gate", wordTone: "ok" };
  }
  const pendingGate = entries.find((e) => e.kind === "gate" && e.state === "hold");
  if (pendingGate) {
    return { entries, word: pendingGate.label, wordTone: "em" };
  }
  const active = entries.find((e) => e.kind === "stage" && e.state === "active");
  if (active) {
    return { entries, word: active.label, wordTone: "em" };
  }
  const nextTodo = entries.find((e) => e.kind === "stage" && e.state === "todo");
  return { entries, word: nextTodo ? nextTodo.label : "Verify", wordTone: "em" };
}

export function deriveFeedSub(state: State): string {
  const gaps = pendingOf(state, "gap");
  if (gaps.length) {
    return `${gaps.length} gap${gaps.length > 1 ? "s" : ""} · waiting on you`;
  }
  if (latestPending(state, "spec_gate")) {
    return "waiting at the spec sign-off";
  }
  if (latestPending(state, "code_gate")) {
    return "holding at the code gate";
  }
  const human = latestPending(state, "human_gate");
  if (human) {
    return `${human.payload.verdict ?? "verdict"} — ${human.payload.matched ?? ""} matched`;
  }
  const hold = latestPending(state, "hold");
  if (hold) {
    return `holding after ${hold.payload.after_label ?? hold.payload.after_stage ?? ""}`;
  }
  if (state.ended) {
    return state.ended.status === "approved" ? "approved — build complete" : `build ${state.ended.status}`;
  }
  if (state.holdArmed) {
    return "hold armed — next boundary";
  }
  const openSpecialist = Object.values(state.streams).find(
    (s) => !s.finish && s.source.startsWith("specialist:")
  );
  if (openSpecialist?.who) {
    return `${openSpecialist.who} working…`;
  }
  if (state.currentStage && state.stages[state.currentStage]) {
    return `${state.stages[state.currentStage].label} running…`;
  }
  return "build in progress";
}

export const credits = (state: State): number => state.creditsNano / 1e9;

export function fmtElapsed(fromTs: number, now: number): string {
  const secs = Math.max(0, Math.floor((now - fromTs) / 1000));
  return `${Math.floor(secs / 60)}m ${String(secs % 60).padStart(2, "0")}s`;
}
