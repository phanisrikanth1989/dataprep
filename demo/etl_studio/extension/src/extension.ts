// ETL Studio extension shim entrypoint. Deliberately dumb (ticket 03):
// host the webview, spawn/supervise the agent core, carry the LM bridge.
// Zero agent logic lives on this side of the wire.

import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import { StudioPanel } from "./panel";

let output: vscode.OutputChannel | undefined;

export function activate(context: vscode.ExtensionContext): void {
  output = vscode.window.createOutputChannel("ETL Studio Core");
  context.subscriptions.push(output);
  context.subscriptions.push(
    vscode.commands.registerCommand("etlStudio.open", () => {
      StudioPanel.createOrShow(context, output!);
    })
  );
  // Ticket 17's live-probe affordance (lifecycle only, zero agent logic):
  // a pending autorun marker in the core's default work dir auto-opens the
  // panel so the core spawns and consumes it. Written by the probe driver;
  // never present in normal use.
  const autorun = path.resolve(
    context.extensionPath, "..", "work", "_skeleton", "autorun.json"
  );
  if (fs.existsSync(autorun)) {
    output.appendLine(`[shim] autorun marker found (${autorun}) -- opening the panel`);
    StudioPanel.createOrShow(context, output);
  }
}

export function deactivate(): void {
  // SIGTERMs the core via the panel's dispose chain.
  StudioPanel.current?.dispose();
}
