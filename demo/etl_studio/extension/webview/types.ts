// Hand-mirrored wire types (ticket 08: Python dataclasses are canonical;
// the webview imports this mirror). The reducer's skip-unknown rule is the
// tolerance that keeps hand-mirroring safe.

export interface Envelope {
  seq: number;
  ts: string;
  run_id: string;
  source: string; // "conductor" | "orchestrator" | "specialist:<stage>" | "shim"
  type: string; // dotted family, e.g. "stream.delta"
  payload: Record<string, any>;
}

export type LifecycleState = "spawned" | "crashed" | "restarting" | "dead" | "stopped";

// shim -> webview
export type HostMessage =
  | { kind: "event"; envelope: Envelope }
  | { kind: "lifecycle"; shimSeq: number; state: LifecycleState; detail?: string; pid?: number }
  | {
      kind: "response";
      id: number;
      result?: unknown;
      error?: { code: number | string; message: string; data?: unknown };
    };

// webview -> shim (relayed to the core unless shim.*/editor.*/lm/*)
export type WebviewMessage =
  | { kind: "request"; id: number; method: string; params?: unknown }
  | { kind: "notify"; method: string; params?: unknown };

export interface AttachResult {
  v: number;
  run?: { run_id: string; last_seq: number };
}
