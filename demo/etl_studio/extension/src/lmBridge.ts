// LM bridge, shim half: MECHANICAL by decision (ticket 07 Q6). Converts
// instanceof-discriminated stream parts to tagged JSON and forwards vscode
// errors verbatim ({code, name, message}); all semantics (taxonomy mapping,
// usage decoding, system-role emulation) live in the Python vscode_lm
// adapter. Part naming by instanceof is vendored from the ticket 09
// lm-probe: product builds minify constructor names.

import * as vscode from "vscode";
import { CancellationToken, MessageConnection, ResponseError } from "vscode-jsonrpc/node";

const REQUEST_CANCELLED = -32800; // LSP ErrorCodes.RequestCancelled
const LM_ERROR = 1000; // app-range code; taxonomy travels in error.data
const JUSTIFICATION =
  "ETL Studio: agent-authored RecTran jobs (walking skeleton echo).";

// Serialized-vscode message parts (ticket 07 Q6: the Python adapter owns
// the semantics -- roles, conventions, degradation; this file only
// instantiates what arrives, mechanically).
type WirePart =
  | { kind: "text"; value: string }
  | { kind: "toolCall"; callId: string; name: string; input: unknown }
  | { kind: "toolResult"; callId: string; name?: string; content: unknown };

interface WireChatMessage {
  role: string;
  text?: string;
  parts?: WirePart[];
}

interface WireToolDecl {
  name: string;
  description?: string;
  inputSchema?: object;
}

interface ChatParams {
  streamId: string;
  modelId?: string | null;
  messages: WireChatMessage[];
  tools?: WireToolDecl[];
  options?: { max_output_tokens?: number };
}

type TaggedPart =
  | { kind: "text"; value: string }
  | { kind: "thinking"; value: string }
  | { kind: "toolCall"; callId: string; name: string; input: unknown }
  | { kind: "data"; mime: string; json?: unknown; text?: string }
  | { kind: "unknown"; ctor: string };

function tagPart(part: unknown): TaggedPart {
  if (part instanceof vscode.LanguageModelTextPart) {
    return { kind: "text", value: part.value };
  }
  if (part instanceof vscode.LanguageModelToolCallPart) {
    return { kind: "toolCall", callId: part.callId, name: part.name, input: part.input };
  }
  const anyVscode = vscode as unknown as Record<string, any>;
  const ThinkingPart = anyVscode.LanguageModelThinkingPart; // proposed API; module export absent on stable
  if (ThinkingPart && part instanceof ThinkingPart) {
    return { kind: "thinking", value: String((part as any).value ?? "") };
  }
  // Stable at runtime since ~1.122 but missing from @types/vscode@1.104
  // (our engine floor), so look it up dynamically like ThinkingPart.
  const DataPart = anyVscode.LanguageModelDataPart;
  if (DataPart && part instanceof DataPart) {
    const dataPart = part as { mimeType: string; data: Uint8Array };
    const mime = dataPart.mimeType;
    try {
      const text = new TextDecoder().decode(dataPart.data);
      try {
        return { kind: "data", mime, json: JSON.parse(text) };
      } catch {
        return { kind: "data", mime, text: text.slice(0, 2000) };
      }
    } catch {
      return { kind: "data", mime };
    }
  }
  const ctor =
    part && (part as any).constructor ? (part as any).constructor.name : typeof part;
  return { kind: "unknown", ctor };
}

function toWireError(e: unknown): ResponseError<object> {
  const err = e as any;
  const message = String(err?.message ?? err);
  return new ResponseError(LM_ERROR, message, {
    code: err?.code ?? null,
    name: err?.name ?? null,
    message,
  });
}

// Mechanical part instantiation: tagged JSON in, vscode parts out. No
// convention decisions here -- the Python adapter already serialized them.
function buildMessage(m: WireChatMessage): vscode.LanguageModelChatMessage {
  const mk =
    m.role === "assistant"
      ? vscode.LanguageModelChatMessage.Assistant
      : vscode.LanguageModelChatMessage.User;
  if (!m.parts || m.parts.length === 0) {
    return mk(m.text ?? "");
  }
  const parts = m.parts.map((p) => {
    if (p.kind === "toolCall") {
      return new vscode.LanguageModelToolCallPart(p.callId, p.name, (p.input as object) ?? {});
    }
    if (p.kind === "toolResult") {
      const content =
        typeof p.content === "string" ? p.content : JSON.stringify(p.content ?? null);
      return new vscode.LanguageModelToolResultPart(p.callId, [
        new vscode.LanguageModelTextPart(content),
      ]);
    }
    return new vscode.LanguageModelTextPart(String((p as { value?: unknown }).value ?? ""));
  });
  return mk(parts as never);
}

export function registerLmBridge(
  conn: MessageConnection,
  output: vscode.OutputChannel
): void {
  conn.onRequest("lm/listModels", async () => {
    const models = await vscode.lm.selectChatModels(); // no selector: everything
    output.appendLine(`[shim] lm/listModels -> ${models.length} models`);
    return {
      models: models.map((m) => ({
        id: m.id,
        vendor: m.vendor,
        family: m.family,
        name: m.name,
        version: m.version,
        maxInputTokens: m.maxInputTokens,
      })),
    };
  });

  conn.onRequest(
    "lm/countTokens",
    async (params: { modelId?: string | null; text: string }) => {
      const all = await vscode.lm.selectChatModels();
      const model = params.modelId
        ? all.find((m) => m.id === params.modelId)
        : all.find((m) => m.vendor === "copilot") ?? all[0];
      if (!model) {
        throw new ResponseError(LM_ERROR, "no language models available", {
          code: "NotFound",
          name: "NoModels",
          message: "no language models available",
        });
      }
      try {
        const count = await model.countTokens(params.text ?? "");
        return { count };
      } catch (e) {
        throw toWireError(e);
      }
    }
  );

  conn.onRequest(
    "lm/chat",
    async (params: ChatParams, token: CancellationToken) => {
      const { streamId, modelId, messages, tools, options } = params;
      const all = await vscode.lm.selectChatModels();
      const model = modelId
        ? all.find((m) => m.id === modelId)
        : all.find((m) => m.vendor === "copilot") ?? all[0];
      if (!model) {
        throw new ResponseError(LM_ERROR, "no language models available", {
          code: "NotFound",
          name: "NoModels",
          message: "no language models available",
        });
      }
      output.appendLine(
        `[shim] lm/chat stream=${streamId} model=${model.vendor}/${model.id}`
      );
      const cts = new vscode.CancellationTokenSource();
      const cancelSub = token.onCancellationRequested(() => cts.cancel());
      if (token.isCancellationRequested) {
        cts.cancel();
      }
      // Mechanical construction only; role/convention semantics arrived
      // pre-serialized from the Python adapter (ticket 07 Q6).
      const vsMessages = messages.map(buildMessage);
      const vsTools = (tools ?? []).map((t) => ({
        name: t.name,
        description: t.description ?? "",
        inputSchema: t.inputSchema,
      }));
      try {
        const res = await model.sendRequest(
          vsMessages,
          {
            justification: JUSTIFICATION,
            ...(vsTools.length ? { tools: vsTools } : {}),
            ...(options?.max_output_tokens
              ? { modelOptions: { max_tokens: options.max_output_tokens } }
              : {}),
          },
          cts.token
        );
        for await (const part of res.stream) {
          if (token.isCancellationRequested) {
            break;
          }
          conn.sendNotification("lm/chatEvent", { streamId, part: tagPart(part) });
        }
        if (token.isCancellationRequested) {
          throw new ResponseError(REQUEST_CANCELLED, "request cancelled");
        }
        // vscode stable exposes no finish reason; 'unknown' is the honest
        // value (ticket 07 Q4).
        return { finishReason: "unknown" };
      } catch (e) {
        if (e instanceof ResponseError) {
          throw e;
        }
        if (token.isCancellationRequested || (e as any)?.name === "Canceled") {
          throw new ResponseError(REQUEST_CANCELLED, "request cancelled");
        }
        output.appendLine(
          `[shim] lm/chat error code=${(e as any)?.code ?? "-"} name=${(e as any)?.name ?? "-"} msg=${(e as any)?.message ?? String(e)}`
        );
        throw toWireError(e);
      } finally {
        cancelSub.dispose();
        cts.dispose();
      }
    }
  );
}
