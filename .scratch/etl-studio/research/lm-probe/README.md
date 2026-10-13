# lm-probe -- ticket 09 handoff package

One-shot probe extension for the Citi VS Code machine. Turns ticket 01's
"verify on-machine" gaps into recorded facts. ~30 minutes.

- Ticket: `../../issues/09-citi-machine-probe.md`
- Full background + original checklist: `../2026-08-09-vscode-lm-facts.md`,
  section "On-machine checklist (Citi F5 dev host)"
- Record results into `WORKSHEET.md` as you go (any format works; the
  worksheet just makes sure nothing on the ticket's record-list is missed).

## Getting it onto the Citi machine

Copy this folder. Only three files are needed to run: `package.json`,
`extension.js`, `.vscode/launch.json`. If files can't be transferred, they
are short enough to retype from any screen that can show this repo.
`WORKSHEET.md` is the recording sheet -- fill it wherever is convenient and
bring the contents back however works (file, email, photo of screen).

## Run order

1. **Versions** (main VS Code window, before F5): Help > About for the VS
   Code version; Extensions view for the versions of GitHub Copilot and
   GitHub Copilot Chat. -> worksheet section 0.
2. Open this folder in VS Code and press **F5** (config "Run LM Probe").
   A second window (Extension Development Host) opens. In it, open
   View > Output and pick the **LM Probe** channel. Also useful: the
   "Extension Host" and "GitHub Copilot Chat" output channels, and DevTools
   (Help > Toggle Developer Tools).
3. Dev host Accounts icon: is the GitHub account already signed in with no
   re-auth? Does Copilot chat work? -> section 1.
4. Ctrl+Shift+P -> **LM Probe: Enumerate Models** -> section 2.
   If it reports 0 models, wait for Copilot to finish signing in, re-run.
5. **LM Probe: Send Request (consent test)**, three runs -> section 3:
   decline first (Cancel -- expect a NoPermissions error), then Allow, then
   run once more (expect no dialog). To re-test the dialog later: Accounts
   icon > the language-models entry > Manage Trusted Extensions.
6. **LM Probe: Tool Round Trip** -> section 4.
7. **LM Probe: Limits (overflow, max_tokens)** -> section 5.
8. Proposed-API check -> section 6:
   a. Add `"enabledApiProposals": ["languageModelThinkingPart"]` to
      `package.json` (top level). Relaunch with plain "Run LM Probe" and
      look for the "CANNOT USE these API proposals" error in the Extension
      Host channel.
   b. Stop; relaunch with **"Run LM Probe (proposed API)"**. Error gone?
      Re-run Send Request and Tool Round Trip and look for
      `LanguageModelThinkingPart` lines in the non-text part logs.
9. Policy check (no VS Code needed) -> section 7: the Copilot
   Business/Enterprise "Bring Your Own Language Model Key" policy state,
   from a Copilot admin or https://github.com/settings/copilot/features
   viewed from a Citi account.

Bring `WORKSHEET.md` -- or a raw dump of the LM Probe output channel, which
is select-all-copyable -- back to the repo. The next wayfinder session
records it as ticket 09's Answer.

## Optional dry run first

The probe is roster-agnostic: F5 it on any machine with Copilot signed in
(e.g. the Mac this repo lives on) to shake out environment issues before
spending the Citi slot. Model JSON lines will differ; consent, tool and
limit behavior should look the same. The probe has been syntax-checked but
never executed -- a dry run is genuinely worth it.

## Deltas vs the listing in the research doc

The code deviates from the listing in `../2026-08-09-vscode-lm-facts.md`
("1. Minimal probe extension") only in ways that add logging or robustness;
no probe semantics changed:

- `engines.vscode` lowered `^1.104.0` -> `^1.95.0`. The probe itself uses
  only 1.90/1.95-era consumer APIs, so it still runs -- and records facts --
  if the Citi build predates the 1.104 provider API. The `>= 1.104`
  requirement applies to ETL Studio's own provider registration and is
  answered by worksheet section 0.
- `describePart()` added: unknown stream parts log constructor name,
  mimeType, a value preview, and decoded `data` -- so a Copilot `usage` data
  part yields its JSON payload (feeds the ticket 06/08 credit readout).
- The tool loop now logs unknown parts too (the research listing dropped
  them silently, but its own checklist step 4 asks for them) and logs which
  model ran.
- `NO MODELS` guards on every command, a shared error logger
  (`code`/`name`/`message`), and `out.show(true)` per command.
- `languageModelAccessInformation` access is guarded; if the API is absent
  on an older build it logs `MISSING`, which is itself a recorded fact.
- `launch.json` ships a second config ("proposed API") so step 8b is a
  launch-dropdown switch instead of a hand-edit.
- (post dry run) Part names resolved via `instanceof` against the vscode
  exports: product builds minify constructor names (the Mac dry run printed
  `i` for the usage data part). `LanguageModelThinkingPart` is matched only
  when proposals are enabled.
- (post dry run) Overflow probe strengthened: ~2x the advertised
  maxInputTokens produced no error on the Mac free tier (there, advertised
  budget was not the enforcement boundary -- whether that holds on Citi is
  exactly what this probes), so the probe now sends ~max(4x advertised,
  ~500k) tokens. Usage-data preview cap raised 500 -> 2000 chars so the
  full usage JSON schema is captured.
