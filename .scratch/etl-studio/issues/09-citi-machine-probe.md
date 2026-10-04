# 09 - Run the vscode.lm probe on the Citi machine

Status: resolved
Type: task

## Question

Turn the "verify on-machine" gaps from ticket 01's research into recorded
facts by running the probe on the Citi VS Code F5 dev host. Only the user can
do this (Citi machine access). ~30 minutes.

Checklist and copy-paste probe extension:
`../research/2026-08-09-vscode-lm-facts.md`, section
"On-machine checklist (Citi F5 dev host)" (steps 0-7).

Record into this ticket's Answer:

- VS Code and Copilot extension versions on the Citi machine (provider API
  needs >= 1.104).
- Whether the F5 dev host shares the main install's Copilot auth and model
  roster.
- The real vendor/family/id/version/maxInputTokens for GPT-5.Sol,
  Claude Opus 4.8, Claude Sonnet 5 -- these become the provider port's
  selector strings.
- Consent dialog behavior: first-call modal with justification text,
  persisted grant, NoPermissions on decline, and multi-turn loop viability
  with no further prompts.
- Tool round-trip works end to end; any unknown stream parts observed
  (thinking / usage data parts).
- Whether modelOptions.max_tokens truncates output; exact input-overflow
  error text.
- Whether --enable-proposed-api works on the Citi stable build (gates the
  thinking-part display option in ticket 06).
- Copilot Business/Enterprise BYO-model policy state (gates the future
  R2D2-as-provider path discussed in ticket 07).

Results inform tickets 03, 06 and 07 (informs, does not block them).

## Answer

All facts from the 2026-08-09 on-machine run. Raw transcript (user-
transcribed from images; all nano_aiu arithmetic cross-checks exactly):
[`../research/2026-08-09-citi-probe-run.md`](../research/2026-08-09-citi-probe-run.md).
Follow-ups confirmed in-session. Mirrors the record-list above:

1. **Versions.** VS Code 1.122.1 -- clears every gate (provider API 1.104,
   DataPart 1.106, tools 1.95). Copilot Chat ships built-in with VS Code on
   this machine; separate Copilot extension versions not recorded.
2. **F5 auth/roster sharing: yes.** Dev host reused the existing sign-in
   with no re-auth; full Citi roster visible inside the dev host.
3. **Roster and selector strings.** 13 models across vendors `copilot` (10)
   and `claude-code` (3). Frontier copilot entries have family == id ==
   version: `claude-opus-4.8`, `claude-opus-4.6`, `claude-sonnet-4.6` (all
   maxInputTokens 935793), `gpt-5.5` (921793), `gpt-5.3-codex` (271790),
   plus `gpt-5-mini` (127790), `gpt-4o-mini` (12078, version
   gpt-4o-mini-2024-07-18) and aliases (`id=auto` -> claude-sonnet-4.6;
   `copilot-utility` -> gpt-5.3-codex; `copilot-utility-small` ->
   gpt-4o-mini). The claude-code vendor republishes Sonnet 4.6 / Opus 4.8 /
   Opus 4.6 at 936000. The map's expected names "GPT-5.Sol" and
   "Claude Sonnet 5" do NOT exist; Sol has since left the picker entirely.
   Consequences: the roster is org-mutable -- enumerate at runtime, select
   by vendor+id, never by display name (names are non-unique: three entries
   are named "Claude Sonnet 4.6", and two pairs share names across real
   models and utility aliases).
4. **Consent.** First-call modal confirmed. Decline -> LanguageModelError
   code=NoPermissions msg "Language model 'copilot/claude-opus-4.6' cannot
   be used by 'citi-demo.lm-probe'." Allow -> works; grant persists (third
   run silent; tool loop ran multiple requests with no prompts) -- the
   background agent loop is viable after one dialog. Quirk: canSendRequest
   returned `true` both before the first grant and immediately after a
   decline -- NOT a reliable pre-check on this build; treat request-time
   NoPermissions as the real gate. Dialog wording not captured (descoped by
   user). Demo-prep note: the grant is per consumer extension id, so ETL
   Studio pays its own dialog once -- warm up during rehearsal.
5. **Tool round trip: works end to end** on Claude Opus 4.6 (get_row_count
   called with correct JSON args, result consumed, correct final answer
   "42"). No stream parts observed beyond text, tool calls, and the usage
   DataPart.
6. **Usage / credits.** Every request ends with a LanguageModelDataPart
   mime=usage. Schema: prompt/completion/total tokens;
   prompt_tokens_details (cached_tokens, cache_creation_input_tokens);
   completion_tokens_details (reasoning_tokens, prediction fields);
   copilot_usage.token_details = [{batch_size, cost_per_batch, token_count,
   token_type: input|cache_read|cache_write|output}]; total_nano_aiu.
   Verified: total_nano_aiu = sum(token_count * cost_per_batch /
   batch_size), exactly. Opus 4.6 rates per 1M tokens: input 0.5 AIU,
   cache_read 0.5 (no discount), cache_write 0.625, output 2.5. Sample: one
   pong = 0.1375 AIU. Ticket 06's live credit readout =
   accumulate total_nano_aiu / 1e9. OPEN: whether "AIU" is the same unit as
   the "~20k credits" in the map notes. Copilot wrapper overhead ~240
   tokens/request (250 prompt tokens for a one-line prompt).
7. **Limits -- both differ from the 1.132 research reading.**
   modelOptions.max_tokens=30 raised a plain Error msg "Response too long."
   (no code) instead of truncating -- do not use max_tokens as an output
   cap; add the string to the adapter error taxonomy. Input overflow: NO
   error at ~3.74M tokens (4x the advertised 935793) -- countTokens on the
   22.5MB probe string returned 3743174 and sendRequest still succeeded.
   Input budgeting must be proactive via countTokens/maxInputTokens; no
   error will fire.
8. **Proposed API on stable 1.122.1: the flag works.** Plain F5 with
   enabledApiProposals declared produced the refusal; the
   --enable-proposed-api=citi-demo.lm-probe launch config removed it
   (user-confirmed present -> gone; exact wording not transcribed). No
   LanguageModelThinkingPart was observed with the flag on -- indeterminate
   between endpoint-not-forwarding and nothing-to-think, but
   reasoning_tokens was 0 on every call (trivial prompts), so
   nothing-to-think is the primary reading. Dev-time discriminator: watch
   reasoning_tokens and stream parts on the real (reasoning-heavy) stage
   prompts. Ticket 06's fallback chain (opening line -> tool verbs) covers
   the no-thinking-parts case regardless.
9. **BYO policy (step 7): descoped by user** (R2D2 will not be used
   locally; not attempted). Incidental evidence stands: the claude-code
   vendor's models being visible cross-extension proves third-party
   provider registration and cross-extension visibility work on this build.

## Comments

2026-08-09 -- Handoff package prepared at
[`../research/lm-probe/`](../research/lm-probe/): the probe extension as
ready-to-copy files (`package.json`, `extension.js`, `.vscode/launch.json`),
a run guide (`README.md`), and a results form (`WORKSHEET.md`) mirroring the
record-list above. Code follows the research-doc listing with
logging/robustness deltas documented in the README (notably: unknown stream
parts now dump their payload so a `usage` part yields its JSON, and the
engine pin is lowered so the probe still runs on a pre-1.104 build). Probe is
syntax-checked but not yet executed anywhere; the README describes an
optional dry run on any Copilot-enabled machine before spending the Citi
slot. Awaiting the on-machine run -- paste the filled worksheet (or a raw LM
Probe output dump) into a wayfinder session to resolve this ticket.

2026-08-09 -- Mac dry run: probe code validated end to end on a FREE-tier
personal Copilot (enumerate, consent flow, tool round trip -> 42,
max_tokens truncation, usage data part captured). Caveat per user: free
tier only -- none of the behavioral observations (usage JSON schema,
no-overflow-error at ~2x advertised, maxInputTokens semantics) count as
facts for the Citi Business/Enterprise environment. The Citi worksheet is
the sole authority for the record-list above. Probe upgrades from the dry
run (probe-code changes, valid regardless of tier): instanceof-based part
naming (product builds minify constructor names to e.g. `i`), usage-data
preview cap 500 -> 2000 chars, stronger overflow probe (~max(4x advertised,
~500k) tokens, since 2x advertised did not error on the free tier). Citi
run imminent.

2026-08-09 -- Citi run happened; raw transcript (user-transcribed from
images, typos possible, but all nano_aiu arithmetic cross-checks exactly)
saved at
[`../research/2026-08-09-citi-probe-run.md`](../research/2026-08-09-citi-probe-run.md).
Core facts landed: full 13-model roster with selector strings (note:
"Claude Sonnet 5" and "GPT-5.Sol" do NOT appear -- actual frontier entries
are Claude Opus 4.8 / Claude Sonnet 4.6 / GPT-5.5 / GPT-5.3-Codex; a
`claude-code` vendor also registers 3 models, proving third-party providers
work on this build), consent decline/allow/persist behavior (with a
canSendRequest-always-true quirk), full usage/AIU cost schema, tool round
trip on Claude Opus 4.6, max_tokens=30 -> plain Error "Response too long."
(no truncation), and NO overflow error at ~3.74M tokens. Still open before
resolution: step 0 versions, consent-dialog wording, step 6 proposed-API
dance, step 7 BYO policy page, and which picker entry "GPT-5.Sol"
actually was.

2026-08-09 -- User follow-ups: VS Code on the Citi laptop is 1.122.1
(>= 1.104, so the provider API and LanguageModelDataPart are both stable
there); Copilot Chat ships built-in with VS Code on that machine, so no
separate extension version recorded. Auth sharing confirmed: the dev host
used the existing sign-in, no re-auth. Consent-dialog wording not captured
(no photo) and descoped by user -- exact copy does not matter for the demo.
Demo-prep note kept: the grant is per consumer extension id, so ETL
Studio's own first sendRequest will show the dialog once; pay it during
rehearsal warm-up. "GPT-5.Sol" no longer appears in the picker -- the org
evidently changed the roster; treat the roster as mutable and select via
enumeration (already the port design). Step 7 BYO policy page descoped by
user decision (R2D2 will not be used locally; the claude-code vendor
sighting stands as incidental evidence that third-party providers work on
this build). Remaining before resolution: step 6 proposed-API dance only.
