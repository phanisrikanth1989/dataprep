// Stdio bridge smoke harness (tickets 10 + 15 + 16). Drives the Python agent
// core over REAL LSP-framed stdio using the same vscode-jsonrpc client the
// shim uses, so a green run here proves the wire interop without the editor.
// The one thing it cannot prove is the live vscode.lm leg -- that stays with
// the F5 checklist. Note: no lm/* handlers are registered here on purpose, so
// the core's auto provider must visibly fall back to the double.
//
// Phases 1-4: walking-skeleton proofs (attach, echo, cancel, crash, SIGTERM).
// Phases 5-6: the typed-door conductor run -- the injected missing-data gap
// answered with REAL attachments, a real elicitation round, spec-gate reject
// + re-sign, a genuine tool-use loop and rate-limit backoff over the double,
// code-gate reject re-raising only the changed cell, a composer hold with
// resume, crash-restart mid-human-gate with seq continuity, full replay
// fidelity, fetch_artifact from the bus, and the bus itself (canonical
// names, history/<artifact>.<k>, audit.jsonl). Ticket 19 made the verify
// stretch REAL: the materializer writes the goldens from the attached data,
// the harness runs the assembled job through the engine as a subprocess,
// run 1 fails on a genuine textual-parity defect (market_value float writes
// 30200.0 against a golden of 30200), the diagnostician's feedback names
// the Configurator, and the repaired job goes green on run 2.
// Phase 7: the BRD-door walk -- needs_human extraction question, a hold
// that steers (directed iteration to the interpreter, draft 2, forward
// re-run), then the full repair-loop arc on real verdicts: an owner:human
// diagnosis (the golden itself questioned; answered "run again as-is"), a
// misdiagnosis whose applied fix genuinely widens the diff, exhaustion with
// one human grant, and the correct fix going green on run 4.
// Phase 8: composer stop -- confirmed, armed, lands plainly at a boundary.
// Phase 9 (ticket 18): a permanently malformed specialist exhausts its
// bounded retries; the orchestrator explains, the propose-confirm card
// carries its words, and a confirmed stop ends the run plainly. Ticket 18
// also grew phases 5-6: non-blocking narration alongside the stage, a
// composer answer grounded through a real bus-read tool round, the
// hold/stop proposals raised by the model's propose_control call, and a
// post-restore ask that must not be journal-skipped.
//
// Run: npm run smoke   (from demo/etl_studio/extension)

import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import rpc from "vscode-jsonrpc/node.js";

const { createMessageConnection, StreamMessageReader, StreamMessageWriter } = rpc;

const here = path.dirname(fileURLToPath(import.meta.url));
const studioRoot = path.resolve(here, "..", "..");
const repoRoot = path.resolve(studioRoot, "..", "..");
const workDir = path.join(studioRoot, "work", "_smoke");
const venvPython = path.join(repoRoot, ".venv", "bin", "python");
const python = fs.existsSync(venvPython) ? venvPython : "python3";

let passed = 0;
let failed = 0;
function check(name, cond, detail = "") {
  if (cond) {
    passed += 1;
    console.log(`  PASS ${name}`);
  } else {
    failed += 1;
    console.log(`  FAIL ${name}${detail ? ` -- ${detail}` : ""}`);
  }
}

function startCore() {
  const child = spawn(
    python,
    [path.join(studioRoot, "main.py"), "--provider", "auto", "--work-dir", workDir, "--pace", "fast"],
    { cwd: studioRoot, stdio: ["pipe", "pipe", "pipe"] }
  );
  child.stderr.setEncoding("utf8");
  child.stderr.on("data", (d) =>
    d.split("\n").filter((l) => l.trim()).forEach((l) => console.log(`    ${l}`))
  );
  const connection = createMessageConnection(
    new StreamMessageReader(child.stdout),
    new StreamMessageWriter(child.stdin)
  );
  const events = [];
  connection.onNotification("ui/event", (env) => events.push(env));
  connection.listen();
  const exited = new Promise((resolve) => child.on("exit", (code, signal) => resolve({ code, signal })));
  return { child, connection, events, exited };
}

async function waitFor(pred, timeoutMs = 8000, what = "condition") {
  const start = Date.now();
  for (;;) {
    const hit = pred();
    if (hit) {
      return hit;
    }
    if (Date.now() - start > timeoutMs) {
      throw new Error(`timeout waiting for ${what}`);
    }
    await new Promise((r) => setTimeout(r, 25));
  }
}

const isQ = (kind) => (e) => e.type === "question.raised" && e.payload?.kind === kind;
const answer = (core, question_id, choice, free_text) =>
  core.connection.sendNotification("answer", { question_id, choice, free_text });

async function main() {
  fs.rmSync(workDir, { recursive: true, force: true });
  console.log(`smoke: python=${python}`);

  // ---- phase 1: fresh core -------------------------------------------------
  console.log("phase 1: attach, ping, streamed echo with visible fallback");
  const one = startCore();
  const attach1 = await one.connection.sendRequest("attach", { v: 1, since_seq: 0 });
  check("fresh attach is idle (no run)", attach1?.v === 1 && attach1?.run === undefined, JSON.stringify(attach1));

  one.connection.sendNotification("skeleton.ping", { nonce: "smoke-1" });
  const pong = await waitFor(
    () => one.events.find((e) => e.type === "skeleton.pong" && e.payload?.nonce === "smoke-1"),
    8000,
    "skeleton.pong"
  );
  check("ping round-trips through core", Boolean(pong));
  check("pong reports python version", /^3\./.test(pong?.payload?.python ?? ""));
  check("skeleton events journal under run 'skeleton'", pong?.run_id === "skeleton" && pong?.seq === 1);

  one.connection.sendNotification("skeleton.echo", { prompt: "hello skeleton" });
  const close1 = await waitFor(
    () => one.events.find((e) => e.type === "stream.close"),
    8000,
    "stream.close"
  );
  const fallback = one.events.find((e) => e.type === "health.provider_fallback");
  const open1 = one.events.find((e) => e.type === "stream.open");
  const sid1 = open1?.payload?.stream_id;
  const deltas1 = one.events.filter(
    (e) => e.type === "stream.delta" && e.payload?.stream_id === sid1
  );
  const text1 = deltas1
    .filter((e) => e.payload?.part?.kind === "text_delta")
    .map((e) => e.payload.part.text)
    .join("");
  check("auto provider fell back VISIBLY to double", fallback?.payload?.to === "double");
  check("fallback announced before stream.open", fallback && open1 && fallback.seq < open1.seq);
  check("stream.open carries provider+model", open1?.payload?.provider === "double" && open1?.payload?.model?.id === "double-1");
  check("streamed >= 3 text deltas", deltas1.filter((e) => e.payload?.part?.kind === "text_delta").length >= 3);
  check("echo text contains the prompt", text1.includes("hello skeleton"), text1);
  check("usage part arrived", deltas1.some((e) => e.payload?.part?.kind === "usage"));
  check("close finish_reason=stop", close1?.payload?.finish_reason === "stop", JSON.stringify(close1?.payload));

  // ---- phase 2: mid-stream cancel -----------------------------------------
  console.log("phase 2: mid-stream cancellation");
  const evBase = one.events.length;
  one.connection.sendNotification("skeleton.echo", {
    prompt: "cancel me midway through a long scripted reply with many words to stream",
  });
  const open2 = await waitFor(
    () => one.events.slice(evBase).find((e) => e.type === "stream.open"),
    8000,
    "second stream.open"
  );
  const sid2 = open2.payload.stream_id;
  await waitFor(
    () =>
      one.events
        .slice(evBase)
        .find((e) => e.type === "stream.delta" && e.payload?.part?.kind === "text_delta"),
    8000,
    "first delta of stream 2"
  );
  one.connection.sendNotification("skeleton.cancel", { stream_id: sid2 });
  const close2 = await waitFor(
    () =>
      one.events
        .slice(evBase)
        .find((e) => e.type === "stream.close" && e.payload?.stream_id === sid2),
    8000,
    "canceled stream.close"
  );
  check("cancel closes stream with finish_reason=canceled", close2?.payload?.finish_reason === "canceled", JSON.stringify(close2?.payload));
  const deltasAfterClose = one.events.filter(
    (e) => e.type === "stream.delta" && e.payload?.stream_id === sid2 && e.seq > close2.seq
  );
  check("no deltas after canceled close", deltasAfterClose.length === 0);

  // ---- phase 3: crash + seq continuity ------------------------------------
  console.log("phase 3: crash, restart, journal seq continuity, full replay");
  const maxSeq1 = Math.max(...one.events.map((e) => e.seq));
  one.connection.sendNotification("skeleton.crash", {});
  const exit1 = await one.exited;
  check("crash exits nonzero", exit1.code === 13, `code=${exit1.code} signal=${exit1.signal}`);
  one.connection.dispose();

  const two = startCore();
  const attach2 = await two.connection.sendRequest("attach", { v: 1, since_seq: maxSeq1 });
  check(
    "restarted core continues the journal (last_seq preserved)",
    attach2?.run?.last_seq === maxSeq1 && attach2?.run?.run_id === "skeleton",
    `expected ${maxSeq1}, got ${JSON.stringify(attach2)}`
  );
  two.connection.sendNotification("skeleton.ping", { nonce: "smoke-2" });
  const pong2 = await waitFor(
    () => two.events.find((e) => e.type === "skeleton.pong" && e.payload?.nonce === "smoke-2"),
    8000,
    "post-restart pong"
  );
  check("first post-restart event continues seq", pong2.seq === maxSeq1 + 1, `expected ${maxSeq1 + 1}, got ${pong2.seq}`);
  check("no stale replay before since_seq", two.events.every((e) => e.seq > maxSeq1));

  const replayBase = two.events.length;
  await two.connection.sendRequest("attach", { v: 1, since_seq: 0 });
  await waitFor(
    () => two.events.slice(replayBase).some((e) => e.seq === pong2.seq),
    8000,
    "full replay to reach the tail"
  );
  const replayed = two.events.slice(replayBase);
  const replayedSeqs = new Set(replayed.map((e) => e.seq));
  let missing = 0;
  for (let s = 1; s <= pong2.seq; s++) {
    if (!replayedSeqs.has(s)) {
      missing += 1;
    }
  }
  check("full-fidelity replay across restart (no missing seq)", missing === 0, `${missing} missing`);
  check(
    "replay preserves pre-crash content (smoke-1 pong)",
    replayed.some((e) => e.type === "skeleton.pong" && e.payload?.nonce === "smoke-1")
  );

  // ---- phase 4: clean shutdown --------------------------------------------
  console.log("phase 4: SIGTERM is a clean exit");
  two.child.kill("SIGTERM");
  const exit2 = await two.exited;
  check("SIGTERM exits 0", exit2.code === 0, `code=${exit2.code} signal=${exit2.signal}`);
  two.connection.dispose();

  // ---- phase 5: the typed-door conductor run (ticket 16) -------------------
  console.log("phase 5: conductor run -- injected gap, spec reject, code reject, hold, repair");
  const three = startCore();
  const ev = three.events;
  await three.connection.sendRequest("attach", { v: 1, since_seq: 0 });

  three.connection.sendNotification("command.start_run", {
    door: "typed",
    text: "Keep settled trades, add account and price details, compute each trade's value",
  });
  const started = await waitFor(() => ev.find((e) => e.type === "run.started"), 10000, "run.started");
  check("run.started carries job + itinerary", started.payload?.job === "trade_positions" && started.payload?.itinerary?.length === 9);
  // The run journal may open with the announced provider fallback (ticket 17:
  // the live leg resolves per run); seq 1 is the run's first event either way.
  const firstR1 = ev.find((e) => e.run_id === "trade_positions-r1");
  check("run gets a fresh journal (seq restarts)", firstR1?.seq === 1 && started.run_id === "trade_positions-r1", `first=${firstR1?.type}#${firstR1?.seq}`);

  // Ticket 18: narration is non-blocking -- the next stage starts while the
  // orchestrator's opening line is still streaming alongside it.
  const openingClose = await waitFor(
    () => ev.find((e) => e.type === "stream.close" && e.payload?.label === "orch.opening.typed"),
    10000,
    "opening narration close"
  );
  const intakeStart = ev.find((e) => e.type === "stage.started" && e.payload?.stage === "intake");
  check(
    "narration streams alongside the stage (non-blocking)",
    Boolean(intakeStart) && intakeStart.seq < openingClose.seq,
    `intake#${intakeStart?.seq} vs close#${openingClose?.seq}`
  );

  const gaps = await waitFor(
    () => { const g = ev.filter(isQ("gap")); return g.length >= 3 ? g : null; },
    15000,
    "three gap questions (G0 injected + G1 + G2)"
  );
  const g0 = gaps.find((e) => e.payload.gap_id === "G0");
  const g1 = gaps.find((e) => e.payload.gap_id === "G1");
  const g2 = gaps.find((e) => e.payload.gap_id === "G2");
  check("dataless request injects the advisory data gap (G0)", g0?.payload?.severity === "advisory" && g0?.payload?.options?.some((o) => o.kind === "waive"));
  check("gap round shares round_id r1", g0?.payload?.round_id === "r1" && g1?.payload?.round_id === "r1" && g2?.payload?.round_id === "r1");
  check("G1 blocking with recommended option", g1?.payload?.severity === "blocking" && g1?.payload?.options?.[0]?.recommended === true);
  check("G2 advisory offers waive", g2?.payload?.severity === "advisory" && g2?.payload?.options?.some((o) => o.kind === "waive"));

  // Real attachments (ticket 19): the materializer writes inputs + goldens
  // from exactly these files, so the harness has something true to grade.
  const attachPaths = ["trades.csv", "accounts.csv", "prices.csv", "trade_positions_expected.csv"]
    .map((f) => path.join(studioRoot, "examples", f));
  answer(three, g0.payload.question_id, "attach", attachPaths.join(", "));
  answer(three, g1.payload.question_id, "keep_blanks");
  answer(three, g2.payload.question_id, "waive");
  await waitFor(
    () => ev.filter((e) => e.type === "question.resolved" && e.payload?.kind === "gap").length >= 3,
    8000,
    "gap resolutions"
  );

  // Dependency-first re-find (ticket 17): the real interpreter folds round 1
  // in and finds the downstream disposition gap, so a second round arrives.
  const g3 = await waitFor(
    () => ev.find((e) => e.type === "question.raised" && e.payload?.kind === "gap" && e.payload?.gap_id === "G3"),
    20000,
    "re-found gap G3 (round 2)"
  );
  check("re-found gap rides round r2", g3.payload?.round_id === "r2" && g3.payload?.severity === "advisory");
  answer(three, g3.payload.question_id, "validate_drop");

  const spec1 = await waitFor(isQFind(ev, "spec_gate", (p) => p.draft === 1), 30000, "spec gate draft 1");
  check("spec gate carries gap resolutions", spec1.payload.gap_resolutions?.length === 4, `${spec1.payload.gap_resolutions?.length}`);
  answer(three, spec1.payload.question_id, "request_changes", "Also carry account_id through to the output");
  const interp2 = await waitFor(
    () => ev.find((e) => e.type === "stage.started" && e.payload?.stage === "interpret" && e.payload?.iteration === 2),
    15000,
    "directed interpreter re-run"
  );
  check("spec reject re-runs the interpreter (directed)", interp2.payload?.directed === true);
  const spec2 = await waitFor(isQFind(ev, "spec_gate", (p) => p.draft === 2), 15000, "spec gate draft 2");
  check("draft 2 re-sign-off carries what_changed", Boolean(spec2.payload.what_changed));
  answer(three, spec2.payload.question_id, "approve");

  await waitFor(
    () => ev.find((e) => e.type === "stage.started" && e.payload?.stage === "configure"),
    20000,
    "configure stage"
  );
  // Composer hold while the configure stretch is running (ticket 13).
  three.connection.sendNotification("command.ask", { ask_id: "a1", text: "hold on for a moment please" });
  const pc = await waitFor(() => ev.find(isQ("propose_confirm")), 15000, "propose-confirm card");
  check("hold proposal streamed with in_reply_to", ev.some((e) => e.type === "stream.open" && e.payload?.in_reply_to === "a1"));
  answer(three, pc.payload.question_id, "confirm");
  const hold = await waitFor(() => ev.find(isQ("hold")), 30000, "hold question at a boundary");
  check("hold raised at a stage boundary", Boolean(hold.payload.after_stage));

  const flowArt = ev.find((e) => e.type === "stage.artifact_written" && e.payload?.name === "flow.json");
  check("flow.json artifact carries nodes+edges", flowArt?.payload?.fields?.nodes?.length === 10 && flowArt?.payload?.fields?.edges?.length === 9);
  const thinkDelta = ev.find((e) => e.type === "stream.delta" && e.payload?.part?.kind === "thinking_delta");
  const toolCall = ev.find((e) => e.type === "stream.delta" && e.payload?.part?.kind === "tool_call");
  const toolResult = ev.find((e) => e.type === "stream.delta" && e.payload?.part?.kind === "tool_result");
  check("thinking deltas streamed", Boolean(thinkDelta));
  check("tool_call + tool_result parts streamed", Boolean(toolCall) && Boolean(toolResult));
  const retry = ev.find((e) => e.type === "health.retry");
  const errClose = ev.find((e) => e.type === "stream.close" && e.payload?.finish_reason === "error");
  check("rate-limit retry surfaced (health.retry)", retry?.payload?.attempt === 2);
  check("errored stream still closed (finish_reason=error)", Boolean(errClose));
  const progress = ev.filter((e) => e.type === "stage.progress");
  check("per-node configure progress streamed", progress.some((e) => e.payload?.state === "configured"));

  answer(three, hold.payload.question_id, "resume");

  const code1 = await waitFor(isQFind(ev, "code_gate", (p) => p.round === 1), 30000, "code gate round 1");
  check("code gate carries the exact cell", code1.payload.cells?.[0]?.code?.includes("market_value"));
  answer(three, code1.payload.question_id, "request_changes", "Cast explicitly and round to 2 decimal places");
  const code2 = await waitFor(isQFind(ev, "code_gate", (p) => p.round === 2), 30000, "code gate round 2");
  check("re-raise is the changed cell only", code2.payload.cells?.length === 1 && code2.payload.cells?.[0]?.changed === true);
  check("revised cell reflects the feedback", code2.payload.cells?.[0]?.code?.includes("round(2)"));
  answer(three, code2.payload.question_id, "approve");

  const human = await waitFor(isQFind(ev, "human_gate", () => true), 60000, "human gate");
  check("verdict is verified with the graded table", human.payload.verdict === "verified" && human.payload.table?.rows?.length === 4);
  check("verdict facts come from the real report (4/4 matched, green on run 2)",
    human.payload.matched === "4/4" && human.payload.runs?.k === 2,
    `matched=${human.payload.matched} runs=${JSON.stringify(human.payload.runs)}`);
  check("verdict diagnosis carries the real owner + fix",
    /Configurator/.test(human.payload.diagnosis ?? "") && /int/.test(human.payload.diagnosis ?? ""),
    human.payload.diagnosis);
  const loopAttempts = ev.filter((e) => e.type === "stage.loop_attempt");
  check("repair loop attempts surfaced", loopAttempts.some((e) => e.payload?.stage === "verify" && e.payload?.k === 2));
  const usageParts = ev.filter((e) => e.type === "stream.delta" && e.payload?.part?.kind === "usage" && e.payload?.part?.total_nano_aiu > 0);
  check("usage parts carry nano-AIU for the credit readout", usageParts.length >= 5, `${usageParts.length}`);

  // A plain composer ask while holding at the gate: conversation, not a gate.
  three.connection.sendNotification("command.ask", { ask_id: "a2", text: "what is left to do?" });
  const askReply = await waitFor(
    () => ev.find((e) => e.type === "stream.open" && e.payload?.in_reply_to === "a2"),
    15000,
    "orchestrator ask reply"
  );
  const askClose = await waitFor(
    () => ev.find((e) => e.type === "stream.close" && e.payload?.stream_id === askReply.payload.stream_id),
    15000,
    "ask reply close"
  );
  const askText = ev
    .filter((e) => e.type === "stream.delta" && e.payload?.stream_id === askReply.payload.stream_id && e.payload?.part?.kind === "text_delta")
    .map((e) => e.payload.part.text)
    .join("");
  check("ask answered from real run state", askClose.payload.finish_reason === "stop" && askText.includes("human gate"));
  // Ticket 18: the answer grounds itself with a real bus read -- one stream
  // carries the model's tool_call and the core-authored tool_result.
  const askParts = ev
    .filter((e) => e.type === "stream.delta" && e.payload?.stream_id === askReply.payload.stream_id)
    .map((e) => e.payload.part?.kind);
  check(
    "ask reply grounded through a bus read (tool round on one stream)",
    askParts.includes("tool_call") && askParts.includes("tool_result"),
    askParts.join(",")
  );

  const art = await three.connection.sendRequest("fetch_artifact", { name: "flow.json" });
  check("fetch_artifact returns the full artifact", art?.found === true && art?.artifact?.fields?.nodes?.length === 10);

  // ---- phase 6: crash mid-gate, restore, approve, replay fidelity ----------
  console.log("phase 6: crash mid-human-gate, crash-restore, approve, full replay");
  const preCrashMax = Math.max(...ev.map((e) => e.seq));
  three.connection.sendNotification("skeleton.crash", {});
  const exit3 = await three.exited;
  check("mid-run crash exits nonzero", exit3.code === 13);
  three.connection.dispose();

  const four = startCore();
  const attach4 = await four.connection.sendRequest("attach", { v: 1, since_seq: preCrashMax });
  check(
    "reattach lands on the run journal with last_seq preserved",
    attach4?.run?.run_id === "trade_positions-r1" && attach4?.run?.last_seq >= preCrashMax,
    JSON.stringify(attach4)
  );
  const restored = await waitFor(
    () => four.events.find((e) => e.type === "run.crash_restored"),
    10000,
    "run.crash_restored"
  );
  // The restored core may announce its provider fallback first (ticket 17:
  // the live leg re-resolves at restore); seq continuity holds either way.
  const firstPostCrash = four.events.reduce((m, e) => (e.seq < m.seq ? e : m), restored);
  check("crash_restored continues the seq sequence",
    firstPostCrash.seq === preCrashMax + 1 && restored.seq <= preCrashMax + 2,
    `expected ${preCrashMax + 1}.., got first=${firstPostCrash.type}#${firstPostCrash.seq} restored=#${restored.seq}`);

  // Ticket 18: conversation survives crash-restore -- a NEW composer ask is
  // never journal-skipped, and its answer grounds in the restored state.
  four.connection.sendNotification("command.ask", { ask_id: "a3", text: "where did we leave off?" });
  const askReply3 = await waitFor(
    () => four.events.find((e) => e.type === "stream.open" && e.payload?.in_reply_to === "a3"),
    15000,
    "post-restore ask reply"
  );
  const askClose3 = await waitFor(
    () => four.events.find((e) => e.type === "stream.close" && e.payload?.stream_id === askReply3.payload.stream_id),
    15000,
    "post-restore ask close"
  );
  const askText3 = four.events
    .filter((e) => e.type === "stream.delta" && e.payload?.stream_id === askReply3.payload.stream_id && e.payload?.part?.kind === "text_delta")
    .map((e) => e.payload.part.text)
    .join("");
  check(
    "post-restore ask answered from restored state (not journal-skipped)",
    askClose3.payload.finish_reason === "stop" && askText3.includes("human gate")
  );

  answer(four, human.payload.question_id, "approve");
  const ended = await waitFor(
    () => four.events.find((e) => e.type === "run.ended"),
    15000,
    "run.ended"
  );
  check("pending gate survived the crash; approve ends the run", ended.payload?.status === "approved");

  const replay4Base = four.events.length;
  await four.connection.sendRequest("attach", { v: 1, since_seq: 0 });
  await waitFor(
    () => four.events.slice(replay4Base).some((e) => e.seq === ended.seq),
    15000,
    "run journal replay to the tail"
  );
  const replayedRun = four.events.slice(replay4Base);
  const runSeqs = new Set(replayedRun.map((e) => e.seq));
  let runMissing = 0;
  for (let s = 1; s <= ended.seq; s++) {
    if (!runSeqs.has(s)) {
      runMissing += 1;
    }
  }
  check("run journal replays full-fidelity (no missing seq)", runMissing === 0, `${runMissing} missing`);
  check(
    "replay preserves stream deltas (thinking reopens after reload)",
    replayedRun.some((e) => e.type === "stream.delta" && e.payload?.part?.kind === "thinking_delta")
  );

  four.child.kill("SIGTERM");
  const exit4 = await four.exited;
  check("SIGTERM after the run exits 0", exit4.code === 0);
  four.connection.dispose();

  // ---- the bus on disk (ticket 16): canonical names, history, audit -------
  console.log("phase 6b: the artifact bus on disk");
  const r1 = path.join(workDir, "trade_positions-r1");
  const has = (p) => fs.existsSync(path.join(r1, p));
  check(
    "canonical artifacts on the bus",
    ["intake.json", "requirement_spec.json", "flow.json", "config.json", "job.json", "feedback.json"].every(has),
    ["intake.json", "requirement_spec.json", "flow.json", "config.json", "job.json", "feedback.json"].filter((p) => !has(p)).join(",")
  );
  check(
    "materialized inputs + golden + manifest on the bus (ticket 19)",
    ["trades.csv", "accounts.csv", "prices.csv", "golden/trade_positions_expected.csv", "golden/manifest.json"].every(has),
    ["trades.csv", "accounts.csv", "prices.csv", "golden/trade_positions_expected.csv", "golden/manifest.json"].filter((p) => !has(p)).join(",")
  );
  check("run reports on the bus", has("runs/run-1/test_report.json") && has("runs/run-2/test_report.json") && has("runs/run-1/harness_output.txt"));
  const report1 = JSON.parse(fs.readFileSync(path.join(r1, "runs/run-1/test_report.json"), "utf8"));
  const mvExample = report1?.outputs?.trade_positions?.examples?.value_mismatch?.[0];
  check(
    "run 1 report is a REAL red with enriched expected-vs-actual examples",
    report1.passed === false &&
      report1?.outputs?.trade_positions?.value_mismatch === 4 &&
      mvExample?.columns?.market_value?.expected === "30200" &&
      mvExample?.columns?.market_value?.actual === "30200.0",
    JSON.stringify(mvExample ?? report1).slice(0, 120)
  );
  const report2 = JSON.parse(fs.readFileSync(path.join(r1, "runs/run-2/test_report.json"), "utf8"));
  check("run 2 report is a REAL green", report2.passed === true && report2.graded === 1);
  const fb = JSON.parse(fs.readFileSync(path.join(r1, "feedback.json"), "utf8"));
  check(
    "feedback.json names the owner with value-visible evidence",
    fb.owner === "configurator" && /30200\.0/.test(fb.evidence ?? "") && Boolean(fb.fix),
    JSON.stringify(fb).slice(0, 120)
  );
  const actualOut = fs.readFileSync(path.join(r1, "trade_positions.csv"), "utf8");
  check(
    "the engine's actual output landed in the work dir and matches the golden textually",
    actualOut.includes('"T004","Gamma Funds","APAC","AAPL","30200","151"'),
    actualOut.split("\n")[1]
  );
  check(
    "supersede moved priors to history/<artifact>.<k>",
    has("history/requirement_spec.json.1") && has("history/config.json.1") && has("history/job.json.1"),
    fs.existsSync(path.join(r1, "history")) ? fs.readdirSync(path.join(r1, "history")).join(",") : "no history/"
  );
  const auditLines = fs
    .readFileSync(path.join(r1, "audit.jsonl"), "utf8")
    .split("\n")
    .filter((l) => l.trim())
    .map((l) => JSON.parse(l));
  const auditEvents = new Set(auditLines.map((e) => e.event));
  check(
    "audit.jsonl records the run's decisions",
    ["run_started", "tier_frozen", "artifact_superseded", "cells_approved", "question_resolved", "run_ended"].every((e) => auditEvents.has(e)),
    [...auditEvents].join(",")
  );
  const spec = JSON.parse(fs.readFileSync(path.join(r1, "requirement_spec.json"), "utf8"));
  check("canonical spec is draft 2 (draft 1 in history)", spec.draft === 2 && Boolean(spec.what_changed));

  // ---- phase 7: BRD door -- needs_human, hold+steer, the full repair arc ---
  console.log("phase 7: BRD walk -- needs_human, steer, owner:human, misdiagnosis, grant, green");
  const five = startCore();
  const ev7 = five.events;
  const my7 = (pred) => (e) => e.run_id === "trade_positions-r2" && pred(e);
  five.connection.sendNotification("command.start_run", {
    door: "brd",
    brd_path: path.join(studioRoot, "examples", "trade_position_demo.docx"),
    brd_name: "trade_position_demo.docx",
    // Attachment contract: the run sees exactly the data files the human
    // attached -- the exploder never scans the document's directory.
    attachments: [
      path.join(studioRoot, "examples", "trades.csv"),
      path.join(studioRoot, "examples", "accounts.csv"),
      path.join(studioRoot, "examples", "prices.csv"),
    ],
    // Fixture-label selectors only (the harness verdicts stay real): the
    // first diagnosis names the human (the golden itself questioned), the
    // next one misdiagnoses (its applied fix genuinely widens the diff),
    // then the correct fix lands -- runs 1-3 red, run 4 green.
    rig: { shape_errors: 1, needs_human: true, owner_human: true, diag_misses: 1 },
  });
  const started7 = await waitFor(
    () => ev7.find((e) => e.type === "run.started" && e.payload?.door === "brd"),
    10000,
    "brd run.started"
  );
  check("brd run gets the next run dir (r2)", started7.run_id === "trade_positions-r2");
  const shapeChip = await waitFor(
    () => ev7.find(my7((e) => e.type === "stage.loop_attempt" && e.payload?.stage === "intake")),
    15000,
    "shape-repair loop attempt"
  );
  check("shape-repair loop surfaced in intake", /shape repair 1 of 3/.test(shapeChip.payload?.note ?? ""));
  const nh = await waitFor(() => ev7.find(isQ("needs_human")), 30000, "needs_human question");
  check("extraction needs_human rides the question channel", nh.payload?.source === "normalize_validate" && nh.payload?.options?.length >= 2);
  check("needs_human names the real unaccounted handle", /para:0/.test(nh.payload?.prompt ?? ""), nh.payload?.prompt);
  answer(five, nh.payload.question_id, "irrelevant");

  // The demo BRD is deliberately incomplete (its section 3 never settles
  // unmatched trades), so G1/G2 rise here too -- but its tables ARE data,
  // so the injected G0 must NOT fire on this door.
  const gaps7 = await waitFor(
    () => { const g = ev7.filter(isQ("gap")); return g.length >= 2 ? g : null; },
    20000,
    "brd gap round"
  );
  check("BRD tables count as data: no injected G0", !gaps7.some((e) => e.payload.gap_id === "G0"));
  for (const g of gaps7) {
    answer(five, g.payload.question_id, g.payload.gap_id === "G1" ? "keep_blanks" : "trade_id_asc");
  }
  const spec7 = await waitFor(isQFind(ev7, "spec_gate", (p) => p.draft === 1), 20000, "brd spec gate draft 1");
  answer(five, spec7.payload.question_id, "approve");

  await waitFor(
    () => ev7.find(my7((e) => e.type === "stage.started" && e.payload?.stage === "configure")),
    20000,
    "brd configure stage"
  );
  five.connection.sendNotification("command.ask", { ask_id: "b1", text: "hold on a moment" });
  const pc7 = await waitFor(() => ev7.find(isQ("propose_confirm")), 15000, "brd propose-confirm");
  answer(five, pc7.payload.question_id, "confirm");
  const hold7 = await waitFor(() => ev7.find(isQ("hold")), 30000, "brd hold at a boundary");
  answer(five, hold7.payload.question_id, "steer", "Name the output column market_value_usd");
  const interp7 = await waitFor(
    () =>
      ev7.find(
        my7((e) => e.type === "stage.started" && e.payload?.stage === "interpret" && e.payload?.iteration === 2)
      ),
    20000,
    "steer re-runs the interpreter"
  );
  check("hold steer routes to the interpreter (directed)", interp7.payload?.directed === true);
  const spec7b = await waitFor(isQFind(ev7, "spec_gate", (p) => p.draft === 2), 20000, "brd spec gate draft 2");
  check("steer produces a draft-2 re-sign-off", Boolean(spec7b.payload.what_changed));
  answer(five, spec7b.payload.question_id, "approve");

  const code7 = await waitFor(isQFind(ev7, "code_gate", () => true), 40000, "brd code gate");
  answer(five, code7.payload.question_id, "approve");

  // Ticket 19: the first diagnosis questions the ORACLE itself -- owner:human
  // rides the channel with the diagnostician's real question + evidence.
  const oh = await waitFor(() => ev7.find(isQ("owner_human")), 60000, "owner:human question");
  check(
    "owner:human carries the diagnostician's question and evidence",
    /golden/.test(oh.payload?.prompt ?? "") && /30200/.test(oh.payload?.evidence ?? "") &&
      ["retry", "stop_to_gate", "steer"].every((id) => oh.payload?.options?.some((o) => o.id === id)),
    JSON.stringify(oh.payload?.prompt ?? "").slice(0, 80)
  );
  answer(five, oh.payload.question_id, "retry");

  const exhaustion = await waitFor(() => ev7.find(isQ("exhaustion")), 90000, "repair exhaustion question");
  check(
    "exhaustion raises grant / stop-to-gate / steer",
    exhaustion.payload?.loop === "repair" &&
      exhaustion.payload?.k === 3 &&
      ["grant", "stop_to_gate", "steer"].every((id) => exhaustion.payload?.options?.some((o) => o.id === id))
  );
  answer(five, exhaustion.payload.question_id, "grant");
  const grantChip = await waitFor(
    () =>
      ev7.find(
        my7((e) => e.type === "stage.loop_attempt" && e.payload?.stage === "verify" && e.payload?.n === 6)
      ),
    30000,
    "post-grant repair attempt (n grew to 6)"
  );
  check("grant stretches the budget visibly", grantChip.payload?.k >= 4);

  const human7 = await waitFor(isQFind(ev7, "human_gate", () => true), 90000, "brd human gate");
  check(
    "brd verdict verified after the granted repair (green on run 4)",
    human7.payload.verdict === "verified" && human7.payload.runs?.k === 4 && human7.payload.matched === "4/4",
    `verdict=${human7.payload.verdict} runs=${JSON.stringify(human7.payload.runs)} matched=${human7.payload.matched}`
  );
  // The misdiagnosis round is REAL on disk: run 3 (the applied float
  // normalization) mismatches closing_price too, where runs 1-2 only ever
  // mismatched market_value.
  const r2dir = path.join(workDir, "trade_positions-r2");
  const rep3 = JSON.parse(fs.readFileSync(path.join(r2dir, "runs/run-3/test_report.json"), "utf8"));
  const rep3cols = new Set(
    (rep3?.outputs?.trade_positions?.examples?.value_mismatch ?? []).flatMap((ex) => Object.keys(ex.columns ?? {}))
  );
  check(
    "the applied misdiagnosis genuinely widened the diff (run 3 adds closing_price)",
    rep3.passed === false && rep3cols.has("market_value") && rep3cols.has("closing_price"),
    [...rep3cols].join(",")
  );
  answer(five, human7.payload.question_id, "approve");
  const ended7 = await waitFor(
    () => ev7.find(my7((e) => e.type === "run.ended")),
    20000,
    "brd run.ended"
  );
  check("brd run ends approved", ended7.payload?.status === "approved");

  const r2 = path.join(workDir, "trade_positions-r2");
  check("brd bus holds the explode + intake chain", fs.existsSync(path.join(r2, "exploded.json")) && fs.existsSync(path.join(r2, "intake.json")));
  const audit7 = fs
    .readFileSync(path.join(r2, "audit.jsonl"), "utf8")
    .split("\n")
    .filter((l) => l.trim())
    .map((l) => JSON.parse(l));
  check(
    "grant + directed iteration on the audit trail",
    audit7.some((e) => e.event === "grant") && audit7.some((e) => e.event === "directed_iteration")
  );
  five.child.kill("SIGTERM");
  await five.exited;
  five.connection.dispose();

  // ---- phase 8: composer stop lands plainly at a boundary ------------------
  console.log("phase 8: composer stop -- confirmed, armed, plain end");
  const six = startCore();
  const ev8 = six.events;
  const my8 = (pred) => (e) => e.run_id === "trade_positions-r3" && pred(e);
  six.connection.sendNotification("command.start_run", {
    door: "typed",
    text: "Same job again",
    attachments: attachPaths.slice(0, 3),
  });
  const gaps8 = await waitFor(
    () => { const g = ev8.filter(isQ("gap")); return g.length >= 2 ? g : null; },
    15000,
    "phase 8 gap round"
  );
  check("attachments at start suppress the injected gap", !gaps8.some((e) => e.payload.gap_id === "G0"));
  six.connection.sendNotification("command.ask", { ask_id: "s1", text: "please stop the build" });
  const pc8 = await waitFor(() => ev8.find(isQ("propose_confirm")), 15000, "stop propose-confirm");
  check("stop intent proposes a stop", pc8.payload?.proposal === "stop");
  answer(six, pc8.payload.question_id, "confirm");
  for (const g of gaps8) {
    answer(six, g.payload.question_id, g.payload.gap_id === "G1" ? "keep_blanks" : "trade_id_asc");
  }
  const g3b = await waitFor(
    () => ev8.find((e) => e.type === "question.raised" && e.payload?.kind === "gap" && e.payload?.gap_id === "G3"),
    20000,
    "phase 8 re-found gap"
  );
  answer(six, g3b.payload.question_id, "validate_drop");
  const spec8 = await waitFor(isQFind(ev8, "spec_gate", (p) => p.draft === 1), 30000, "phase 8 spec gate");
  answer(six, spec8.payload.question_id, "approve");
  const ended8 = await waitFor(
    () => ev8.find(my8((e) => e.type === "run.ended")),
    20000,
    "stopped run.ended"
  );
  check("armed stop lands plainly at the next boundary", ended8.payload?.status === "stopped" && ended8.payload?.by === "you");
  check("nothing ran past the boundary", !ev8.some(my8((e) => e.type === "stage.started" && e.payload?.stage === "design")));
  six.child.kill("SIGTERM");
  const exit6 = await six.exited;
  check("SIGTERM after the stopped run exits 0", exit6.code === 0);
  six.connection.dispose();

  // ---- phase 9: forced malformed-specialist escalation (ticket 18) ---------
  console.log("phase 9: malformed specialist -> orchestrator explains -> propose-confirm stop");
  const nine = startCore();
  const ev9 = nine.events;
  nine.connection.sendNotification("command.start_run", {
    door: "typed",
    text: "Same job again",
    attachments: attachPaths.slice(0, 3),
    rig: { malformed_design: true },
  });
  const gaps9 = await waitFor(
    () => { const g = ev9.filter(isQ("gap")); return g.length >= 2 ? g : null; },
    15000,
    "phase 9 gap round"
  );
  for (const g of gaps9) {
    answer(nine, g.payload.question_id, g.payload.gap_id === "G1" ? "keep_blanks" : "trade_id_asc");
  }
  const g3d = await waitFor(
    () => ev9.find((e) => e.type === "question.raised" && e.payload?.kind === "gap" && e.payload?.gap_id === "G3"),
    20000,
    "phase 9 re-found gap"
  );
  answer(nine, g3d.payload.question_id, "validate_drop");
  const spec9 = await waitFor(isQFind(ev9, "spec_gate", (p) => p.draft === 1), 30000, "phase 9 spec gate");
  answer(nine, spec9.payload.question_id, "approve");

  const pc9 = await waitFor(() => ev9.find(isQ("propose_confirm")), 60000, "escalation propose-confirm");
  const badCloses = ev9.filter((e) => e.type === "stream.close" && e.payload?.label === "flow.design.bad");
  check("malformed specialist spent its bounded retries (3 attempts streamed)", badCloses.length === 3, `${badCloses.length}`);
  check(
    "escalation proposes a stop with conductor-authored options",
    pc9.payload?.proposal === "stop" && ["confirm", "dismiss"].every((id) => pc9.payload?.options?.some((o) => o.id === id))
  );
  const escOpen = ev9.find((e) => e.type === "stream.open" && e.payload?.label === "orch.escalate");
  const escText = ev9
    .filter((e) => e.type === "stream.delta" && e.payload?.stream_id === escOpen?.payload?.stream_id && e.payload?.part?.kind === "text_delta")
    .map((e) => e.payload.part.text)
    .join("");
  check(
    "the orchestrator explained first and the card carries its words",
    Boolean(escOpen) && escOpen.seq < pc9.seq && pc9.payload?.voice === escText.trim(),
    `voice=${JSON.stringify(pc9.payload?.voice ?? "").slice(0, 60)}`
  );
  answer(nine, pc9.payload.question_id, "confirm");
  const ended9 = await waitFor(
    () => ev9.find((e) => e.type === "run.ended" && e.run_id === spec9.run_id),
    20000,
    "phase 9 run.ended"
  );
  check(
    "confirmed stop ends the run plainly",
    ended9.payload?.status === "stopped" && /design/.test(ended9.payload?.note ?? ""),
    JSON.stringify(ended9.payload)
  );
  nine.child.kill("SIGTERM");
  const exit9 = await nine.exited;
  check("SIGTERM after the escalated run exits 0", exit9.code === 0);
  nine.connection.dispose();

  console.log(`\nsmoke result: ${passed} passed, ${failed} failed`);
  process.exit(failed === 0 ? 0 : 1);
}

// find helper bound late so `ev` array identity is shared
function isQFind(ev, kind, pred) {
  return () => ev.find((e) => e.type === "question.raised" && e.payload?.kind === kind && pred(e.payload));
}

main().catch((e) => {
  console.error(`smoke: FATAL ${e?.stack ?? e}`);
  process.exit(1);
});
