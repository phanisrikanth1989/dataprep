// Agent-core process supervisor. Ticket 03: core spawned on panel open (not
// activation), auto-restart on crash with a VISIBLE banner (never silent),
// SIGTERM on panel close / deactivate. Restart storms end in the 'dead'
// state (3 crashes / 60s) with a manual Restart affordance.

import * as cp from "child_process";
import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import {
  createMessageConnection,
  MessageConnection,
  StreamMessageReader,
  StreamMessageWriter,
} from "vscode-jsonrpc/node";

export type LifecycleState = "spawned" | "crashed" | "restarting" | "dead" | "stopped";

export interface LifecycleEvent {
  state: LifecycleState;
  detail?: string;
  pid?: number;
}

export interface CoreProcessDeps {
  studioRoot: string; // demo/etl_studio
  output: vscode.OutputChannel;
  onLifecycle: (e: LifecycleEvent) => void;
  onConnection: (conn: MessageConnection) => void; // re-fires per (re)spawn
}

const CRASH_WINDOW_MS = 60_000;
const CRASH_LIMIT = 3;
const RESTART_DELAY_MS = 500;
const SIGKILL_GRACE_MS = 3_000;

export function resolvePython(studioRoot: string): string {
  const configured = vscode.workspace
    .getConfiguration("etlStudio")
    .get<string>("pythonPath", "")
    .trim();
  if (configured) {
    return configured;
  }
  const repoRoot = path.resolve(studioRoot, "..", "..");
  // Windows venvs put the interpreter under Scripts\, and "python3" is
  // usually absent from PATH there (ticket 20: Citi laptop portability).
  const isWin = process.platform === "win32";
  const venvPython = isWin
    ? path.join(repoRoot, ".venv", "Scripts", "python.exe")
    : path.join(repoRoot, ".venv", "bin", "python");
  if (fs.existsSync(venvPython)) {
    return venvPython;
  }
  return isWin ? "python" : "python3";
}

export class CoreProcess implements vscode.Disposable {
  private child: cp.ChildProcess | null = null;
  private connection: MessageConnection | null = null;
  private crashTimes: number[] = [];
  private stopping = false;
  private dead = false;

  constructor(private readonly deps: CoreProcessDeps) {}

  get activeConnection(): MessageConnection | null {
    return this.connection;
  }

  start(): void {
    if (this.child) {
      return;
    }
    const python = resolvePython(this.deps.studioRoot);
    const provider = vscode.workspace
      .getConfiguration("etlStudio")
      .get<string>("provider", "auto");
    const mainPy = path.join(this.deps.studioRoot, "main.py");
    this.deps.output.appendLine(
      `[shim] spawning core: ${python} ${mainPy} --provider ${provider}`
    );
    let child: cp.ChildProcess;
    try {
      child = cp.spawn(python, [mainPy, "--provider", provider], {
        cwd: this.deps.studioRoot,
        stdio: ["pipe", "pipe", "pipe"],
      });
    } catch (e) {
      this.deps.output.appendLine(`[shim] spawn failed: ${String(e)}`);
      this.deps.onLifecycle({ state: "dead", detail: `spawn failed: ${String(e)}` });
      this.dead = true;
      return;
    }
    this.child = child;

    child.stderr?.setEncoding("utf8");
    child.stderr?.on("data", (chunk: string) => {
      for (const line of chunk.split("\n")) {
        if (line.trim()) {
          this.deps.output.appendLine(line);
        }
      }
    });

    child.on("error", (err) => {
      // e.g. ENOENT: python not found. 'exit' may never fire with a code.
      this.deps.output.appendLine(`[shim] core process error: ${err.message}`);
      this.child = null;
      this.disposeConnection();
      this.handleUnexpectedExit(`process error: ${err.message}`);
    });

    child.on("exit", (code, signal) => {
      this.deps.output.appendLine(
        `[shim] core exited code=${code ?? "-"} signal=${signal ?? "-"}`
      );
      this.child = null;
      this.disposeConnection();
      if (this.stopping) {
        this.deps.onLifecycle({ state: "stopped" });
        return;
      }
      this.handleUnexpectedExit(`exit code=${code ?? "-"} signal=${signal ?? "-"}`);
    });

    const connection = createMessageConnection(
      new StreamMessageReader(child.stdout!),
      new StreamMessageWriter(child.stdin!)
    );
    connection.onError((e) => this.deps.output.appendLine(`[shim] rpc error: ${String(e)}`));
    this.connection = connection;
    this.deps.onConnection(connection); // handlers first, then listen
    connection.listen();

    this.deps.onLifecycle({ state: "spawned", pid: child.pid });
  }

  private handleUnexpectedExit(detail: string): void {
    const now = Date.now();
    this.crashTimes = this.crashTimes.filter((t) => now - t < CRASH_WINDOW_MS);
    this.crashTimes.push(now);
    if (this.crashTimes.length >= CRASH_LIMIT) {
      this.dead = true;
      this.deps.onLifecycle({
        state: "dead",
        detail: `${detail} -- ${this.crashTimes.length} crashes in ${CRASH_WINDOW_MS / 1000}s`,
      });
      return;
    }
    this.deps.onLifecycle({ state: "crashed", detail });
    this.deps.onLifecycle({ state: "restarting" });
    setTimeout(() => {
      if (!this.stopping && !this.dead) {
        this.start();
      }
    }, RESTART_DELAY_MS);
  }

  /** Manual restart out of the 'dead' state (webview banner button). */
  restartFromDead(): void {
    this.crashTimes = [];
    this.dead = false;
    this.stopping = false;
    if (!this.child) {
      this.start();
    }
  }

  /** Deliberate shutdown: SIGTERM, SIGKILL after a grace period. */
  stop(): void {
    this.stopping = true;
    const child = this.child;
    if (!child) {
      return;
    }
    this.deps.output.appendLine(`[shim] stopping core pid=${child.pid} (SIGTERM)`);
    child.kill("SIGTERM");
    const killer = setTimeout(() => {
      if (this.child === child) {
        this.deps.output.appendLine("[shim] core ignored SIGTERM, sending SIGKILL");
        child.kill("SIGKILL");
      }
    }, SIGKILL_GRACE_MS);
    child.once("exit", () => clearTimeout(killer));
  }

  private disposeConnection(): void {
    try {
      this.connection?.dispose();
    } catch {
      // already down
    }
    this.connection = null;
  }

  dispose(): void {
    this.stop();
  }
}
