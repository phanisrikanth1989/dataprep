// ETL Studio extension shim entrypoint. Deliberately dumb (ticket 03):
// host the webview, spawn/supervise the agent core, carry the LM bridge.
// Zero agent logic lives on this side of the wire.

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
}

export function deactivate(): void {
  // SIGTERMs the core via the panel's dispose chain.
  StudioPanel.current?.dispose();
}
