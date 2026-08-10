// ETL Studio webview panel host. The shim relays blind, routing by method
// family (ticket 08): lm/* never crosses the webview boundary, shim.* and
// editor.* terminate here, everything else goes to the core untouched.

import * as path from "path";
import * as vscode from "vscode";
import { MessageConnection } from "vscode-jsonrpc/node";
import { CoreProcess, LifecycleEvent } from "./coreProcess";
import { registerLmBridge } from "./lmBridge";
import type { WebviewMessage } from "../webview/types";

export class StudioPanel {
  public static current: StudioPanel | undefined;

  private readonly panel: vscode.WebviewPanel;
  private readonly core: CoreProcess;
  private readonly studioRoot: string;
  private shimSeq = 0;
  private disposables: vscode.Disposable[] = [];

  public static createOrShow(
    context: vscode.ExtensionContext,
    output: vscode.OutputChannel
  ): void {
    if (StudioPanel.current) {
      StudioPanel.current.panel.reveal();
      return;
    }
    StudioPanel.current = new StudioPanel(context, output);
  }

  private constructor(
    context: vscode.ExtensionContext,
    private readonly output: vscode.OutputChannel
  ) {
    const distRoot = vscode.Uri.file(path.join(context.extensionPath, "dist"));
    this.panel = vscode.window.createWebviewPanel(
      "etlStudio",
      "ETL Studio",
      vscode.ViewColumn.One,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [distRoot],
      }
    );
    this.panel.webview.html = this.renderHtml(distRoot);

    this.studioRoot = path.resolve(context.extensionPath, "..");
    this.core = new CoreProcess({
      studioRoot: this.studioRoot,
      output,
      onLifecycle: (e) => this.postLifecycle(e),
      onConnection: (conn) => this.wireConnection(conn),
    });

    this.panel.webview.onDidReceiveMessage(
      (msg: WebviewMessage) => void this.handleWebviewMessage(msg),
      null,
      this.disposables
    );
    this.panel.onDidDispose(() => this.dispose(), null, this.disposables);

    // Ticket 03: one core per window, spawned when the panel opens.
    this.core.start();
  }

  // ---- core -> webview -----------------------------------------------------

  private wireConnection(conn: MessageConnection): void {
    registerLmBridge(conn, this.output);
    conn.onNotification("ui/event", (envelope) => {
      void this.panel.webview.postMessage({ kind: "event", envelope });
    });
  }

  private postLifecycle(e: LifecycleEvent): void {
    // Shim events seq in their own namespace: they can fire while the core
    // (and its journal-owned sequence) is dead. Ticket 08.
    this.shimSeq += 1;
    void this.panel.webview.postMessage({
      kind: "lifecycle",
      shimSeq: this.shimSeq,
      state: e.state,
      detail: e.detail,
      pid: e.pid,
    });
  }

  // ---- webview -> core (blind relay, routed by family) ---------------------

  private async handleWebviewMessage(msg: WebviewMessage): Promise<void> {
    if (msg.kind === "notify") {
      if (msg.method.startsWith("lm/")) {
        return; // shim<->core only, never webview-originated
      }
      if (msg.method === "shim.restart") {
        this.output.appendLine("[shim] manual core restart requested");
        this.core.restartFromDead();
        return;
      }
      if (msg.method === "shim.close_panel") {
        // Exit from the webview: close the panel (SIGTERMs the core via
        // dispose); the run journal stays, so reopening restores it.
        this.output.appendLine("[shim] exit requested from the webview");
        this.panel.dispose();
        return;
      }
      if (msg.method === "editor.open_file") {
        // Whole data files open in the real editor, never the feed (tickets
        // 06/20). The core sends real bus paths; a relative path resolves
        // against the studio root.
        const p = (msg.params ?? {}) as { path?: string };
        if (!p.path) {
          return;
        }
        const abs = path.isAbsolute(p.path) ? p.path : path.join(this.studioRoot, p.path);
        try {
          await vscode.commands.executeCommand("vscode.open", vscode.Uri.file(abs), {
            viewColumn: vscode.ViewColumn.Beside,
            preview: true,
          });
        } catch (e) {
          this.output.appendLine(`[shim] editor.open_file failed for ${abs}: ${String(e)}`);
        }
        return;
      }
      if (msg.method.startsWith("shim.") || msg.method.startsWith("editor.")) {
        this.output.appendLine(`[shim] no handler for ${msg.method}`);
        return;
      }
      const conn = this.core.activeConnection;
      if (!conn) {
        this.output.appendLine(`[shim] dropping ${msg.method}: core is down`);
        return;
      }
      try {
        conn.sendNotification(msg.method, msg.params);
      } catch (e) {
        this.output.appendLine(`[shim] relay failed for ${msg.method}: ${String(e)}`);
      }
      return;
    }

    const respond = (body: { result?: unknown; error?: object }) =>
      void this.panel.webview.postMessage({ kind: "response", id: msg.id, ...body });

    if (msg.method === "editor.pick_file") {
      // Webviews cannot open native dialogs (ticket 08): the BRD door and
      // data attachments pick through the shim.
      const p = (msg.params ?? {}) as { label?: string; filters?: Record<string, string[]> };
      try {
        const picked = await vscode.window.showOpenDialog({
          canSelectMany: false,
          openLabel: p.label ?? "Choose file",
          filters: p.filters,
        });
        const uri = picked?.[0];
        respond({ result: uri ? { path: uri.fsPath, name: path.basename(uri.fsPath) } : null });
      } catch (e) {
        respond({ error: { code: "pick_failed", message: String(e) } });
      }
      return;
    }
    if (
      msg.method.startsWith("lm/") ||
      msg.method.startsWith("shim.") ||
      msg.method.startsWith("editor.")
    ) {
      respond({
        error: { code: "method_not_found", message: `no request handler: ${msg.method}` },
      });
      return;
    }
    const conn = this.core.activeConnection;
    if (!conn) {
      respond({ error: { code: "core_down", message: "agent core is not running" } });
      return;
    }
    try {
      const result = await conn.sendRequest(msg.method, msg.params);
      respond({ result });
    } catch (e) {
      const err = e as any;
      respond({
        error: {
          code: err?.code ?? "error",
          message: String(err?.message ?? e),
          data: err?.data,
        },
      });
    }
  }

  // ---- html ----------------------------------------------------------------

  private renderHtml(distRoot: vscode.Uri): string {
    const webview = this.panel.webview;
    const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(distRoot, "webview.js"));
    const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(distRoot, "webview.css"));
    const nonce = Array.from({ length: 32 }, () =>
      "abcdefghijklmnopqrstuvwxyz0123456789".charAt(Math.floor(Math.random() * 36))
    ).join("");
    // font-src covers the locally bundled @fontsource files; no CDN exists
    // inside the webview (ticket 15).
    return [
      "<!DOCTYPE html>",
      '<html lang="en">',
      "<head>",
      '<meta charset="utf-8">',
      `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; font-src ${webview.cspSource}; script-src 'nonce-${nonce}';">`,
      '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
      `<link rel="stylesheet" href="${styleUri}">`,
      "<title>ETL Studio</title>",
      "</head>",
      "<body>",
      '<div id="root"></div>',
      `<script nonce="${nonce}" src="${scriptUri}"></script>`,
      "</body>",
      "</html>",
    ].join("\n");
  }

  dispose(): void {
    StudioPanel.current = undefined;
    // Ticket 03/10: SIGTERM on panel close / deactivate.
    this.core.dispose();
    for (const d of this.disposables.splice(0)) {
      try {
        d.dispose();
      } catch {
        // already disposed
      }
    }
  }
}
