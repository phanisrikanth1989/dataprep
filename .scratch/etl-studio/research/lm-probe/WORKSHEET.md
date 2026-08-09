# Ticket 09 worksheet -- vscode.lm probe on the Citi machine

Run date: ____________    Run by: ____________

Fill this in while following `README.md`. Bring the completed contents back
(file, paste, or photo); they become ticket 09's Answer.

## 0. Versions (main VS Code window, before F5)

- VS Code version (Help > About):
- GitHub Copilot extension version:
- GitHub Copilot Chat extension version:

## 1. Auth sharing (dev host)

- GitHub account already signed in inside the dev host, no re-auth (yes/no):
- Copilot chat works inside the dev host (yes/no):

## 2. Model roster ("LM Probe: Enumerate Models")

- `total models:` line:
- `vendor=copilot count:` line:
- Paste all model JSON lines:

```
(paste)
```

- Selector strings for the three target models (copy from the JSON lines,
  matched by `name`):
  - GPT-5.Sol:      vendor=          family=          id=          version=          maxInputTokens=
  - Claude Opus 4.8: vendor=          family=          id=          version=          maxInputTokens=
  - Claude Sonnet 5: vendor=          family=          id=          version=          maxInputTokens=
- Any of the three missing from the roster? Which:

## 3. Consent ("LM Probe: Send Request", three runs)

Run 1 -- decline (Cancel):

- Modal dialog appeared (yes/no):
- Exact dialog wording (transcribe or photo):

```
(paste)
```

- "Justification: ETL Studio demo: ..." visible in the dialog (yes/no):
- `canSendRequest BEFORE:` value (expect undefined):
- Error line after declining (expect code=NoPermissions):

Run 2 -- Allow:

- Dialog appeared again (yes/no):
- `response:` line (expect pong):
- `canSendRequest AFTER:` value (expect true):
- Any `non-text part:` lines (paste -- especially anything `mime=usage`):

```
(paste)
```

Run 3 -- immediately re-run:

- Any dialog (expect none):

## 4. Tool round trip ("LM Probe: Tool Round Trip")

- `toolLoop model:` line:
- Turn lines (expect `get_row_count {"table":"CUSTOMERS"}`):

```
(paste)
```

- `final answer:` line (expect it to contain 42):
- Any consent prompts during the loop (expect none):
- Any `non-text part` lines (paste):

```
(paste)
```

## 5. Limits ("LM Probe: Limits")

- `max_tokens=30 output length:` line (truncated -- i.e. short -- or not):
- `countTokens(big) =` line:
- Overflow error line, exact (expect msg='Message exceeds token limit.'):

## 6. Proposed API on the Citi stable build

6a. Plain F5 after adding `enabledApiProposals` (README step 8a):

- "CANNOT USE these API proposals" error in Extension Host log (yes/no);
  paste the line:

```
(paste)
```

6b. Relaunched with "Run LM Probe (proposed API)" (README step 8b):

- Flag honored -- error gone (yes/no):
- `LanguageModelThinkingPart` lines observed in send/toolLoop (paste any):

```
(paste)
```

## 7. BYO-model policy (future R2D2-as-provider path)

- "Bring Your Own Language Model Key" policy state
  (enabled / disabled / unknown; source -- admin or
  github.com/settings/copilot/features):
- MCP policy state, if visible:

## Anything unexpected

- (extra dialogs, warnings, roster differences between the chat picker and
  enumerate, crashes, anything odd)
