// Webview<->shim bridge: one acquireVsCodeApi call, request/response
// correlation, and the notify helpers the components use. The shim relays
// blind to the core except shim.* / editor.* (ticket 08).

import type { HostMessage } from "./types";

declare function acquireVsCodeApi(): { postMessage(msg: unknown): void };
const vscodeApi = acquireVsCodeApi();

let nextRequestId = 1;
const pending = new Map<
  number,
  { resolve: (v: unknown) => void; reject: (e: Error & { code?: unknown }) => void }
>();

type HostHandler = (msg: HostMessage) => void;
let hostHandler: HostHandler | null = null;

export function setHostHandler(h: HostHandler): void {
  hostHandler = h;
}

window.addEventListener("message", (e: MessageEvent) => {
  const msg = e.data as HostMessage;
  if (!msg || typeof msg !== "object") {
    return;
  }
  if (msg.kind === "response") {
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
    return;
  }
  hostHandler?.(msg);
});

export function sendRequest<T>(method: string, params?: unknown): Promise<T> {
  const id = nextRequestId++;
  const promise = new Promise<T>((resolve, reject) => {
    pending.set(id, { resolve: resolve as (v: unknown) => void, reject });
  });
  vscodeApi.postMessage({ kind: "request", id, method, params });
  return promise;
}

export function sendNotify(method: string, params?: unknown): void {
  vscodeApi.postMessage({ kind: "notify", method, params });
}

export const answer = (question_id: string, choice: string, free_text?: string): void =>
  sendNotify("answer", { question_id, choice, free_text });

export function ask(text: string): void {
  const ask_id = `a-${Math.random().toString(36).slice(2, 9)}`;
  sendNotify("command.ask", { ask_id, text });
}
