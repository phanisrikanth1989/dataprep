// Stdio bridge smoke harness (ticket 10). Drives the Python agent core over
// REAL LSP-framed stdio using the same vscode-jsonrpc client the shim uses,
// so a green run here proves the wire interop without the editor. The one
// thing it cannot prove is the live vscode.lm leg -- that stays with the F5
// checklist. Note: no lm/* handlers are registered here on purpose, so the
// core's auto provider must visibly fall back to the double.
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
  const child = spawn(python, [path.join(studioRoot, "main.py"), "--provider", "auto", "--work-dir", workDir], {
    cwd: studioRoot,
    stdio: ["pipe", "pipe", "pipe"],
  });
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

async function main() {
  fs.rmSync(workDir, { recursive: true, force: true });
  console.log(`smoke: python=${python}`);

  // ---- phase 1: fresh core -------------------------------------------------
  console.log("phase 1: attach, ping, streamed echo with visible fallback");
  const one = startCore();
  const attach1 = await one.connection.sendRequest("attach", { v: 1, since_seq: 0 });
  check("attach returns skeleton run", attach1?.run?.run_id === "skeleton");
  check("fresh journal at seq 0", attach1?.run?.last_seq === 0, JSON.stringify(attach1));

  one.connection.sendNotification("skeleton.ping", { nonce: "smoke-1" });
  const pong = await waitFor(
    () => one.events.find((e) => e.type === "skeleton.pong" && e.payload?.nonce === "smoke-1"),
    8000,
    "skeleton.pong"
  );
  check("ping round-trips through core", Boolean(pong));
  check("pong reports python version", /^3\./.test(pong?.payload?.python ?? ""));

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
    attach2?.run?.last_seq === maxSeq1,
    `expected ${maxSeq1}, got ${attach2?.run?.last_seq}`
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

  console.log(`\nsmoke result: ${passed} passed, ${failed} failed`);
  process.exit(failed === 0 ? 0 : 1);
}

main().catch((e) => {
  console.error(`smoke: FATAL ${e?.stack ?? e}`);
  process.exit(1);
});
