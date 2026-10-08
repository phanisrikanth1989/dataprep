# vscode.lm facts (ticket 01)

Researched: 2026-08-09. All API facts verified against VS Code stable
**1.132.0** (tag `1.132.0`, released 2026-08-05 per
https://github.com/microsoft/vscode/releases/latest and
https://code.visualstudio.com/updates). Where a fact depends on the version,
the version that introduced it is stamped. Sources are the stable
`src/vscode-dts/vscode.d.ts` at tag 1.132.0, the proposed `vscode.proposed.*.d.ts`
files at the same tag, VS Code core source at the same tag, the official API
guides (code.visualstudio.com/api, raw markdown from microsoft/vscode-docs),
and official release notes. No blogs, no Stack Overflow.

Shorthand used below:
- `d.ts#L123` = https://github.com/microsoft/vscode/blob/1.132.0/src/vscode-dts/vscode.d.ts#L123
- `copilot lmAccess` = https://github.com/microsoft/vscode/blob/1.132.0/extensions/copilot/src/extension/conversation/vscode-node/languageModelAccess.ts
  (the GitHub Copilot extension is vendored into the microsoft/vscode repo at
  this tag; this file is the actual implementation that serves `vscode.lm`
  requests for the `copilot` vendor -- implementation detail, not API contract,
  and Citi's installed Copilot build may differ; flagged per item)
- `extHostLanguageModels` = src/vs/workbench/api/common/extHostLanguageModels.ts at 1.132.0
- `languageModels.ts` = src/vs/workbench/contrib/chat/common/languageModels.ts at 1.132.0

---

## 1. Stable vs proposed API

### Stable (in `vscode.d.ts` at 1.132.0 -- no flags needed, works in any install)

Namespace `vscode.lm` (`d.ts#L20734`):

| API | Since | Evidence |
|---|---|---|
| `lm.selectChatModels(selector?)` | 1.90 | `d.ts#L20766`; finalized per v1.90 notes: "We have finalized APIs that enable extensions to participate in chat and to access language models" (https://code.visualstudio.com/updates/v1_90) |
| `lm.onDidChangeChatModels: Event<void>` | 1.90 | `d.ts#L20739` |
| `lm.registerTool(name, tool)` / `lm.tools` / `lm.invokeTool(name, options, token)` | 1.95 | `d.ts#L20774,20780,20808`; v1.95 notes: "We have finalized our LanguageModelTool API!" (https://code.visualstudio.com/updates/v1_95) |
| `lm.registerLanguageModelChatProvider(vendor, provider)` | 1.104 | `d.ts#L20847`; v1.104 notes (released 2025-09-11): "This iteration, we finalized the LanguageModelChatProviders API. This enables extensions to contribute one or more language models, cloud-hosted or local." (https://code.visualstudio.com/updates/v1_104). Verified present in stable d.ts at tag 1.104.0. |
| `lm.registerMcpServerDefinitionProvider` | 1.101 | `d.ts#L20838` |

Types (all stable at 1.132.0):

- `LanguageModelChat` (`d.ts#L20239`): readonly `name`, `id`, `vendor`,
  `family`, `version`, `maxInputTokens`; methods `sendRequest(messages,
  options?, token?)`, `countTokens(text, token?)`. No `maxOutputTokens` on the
  consumer side (see Q6).
- `LanguageModelChatSelector` (`d.ts#L20316`): optional `vendor`, `family`,
  `version`, `id`. Matching is exact string equality on each provided field
  over all cached models (`languageModels.ts#L1304-L1327`); empty selector
  resolves and returns models from all vendors.
- `LanguageModelChatMessage` (`d.ts#L20142`) with `LanguageModelChatMessageRole`
  = `User = 1`, `Assistant = 2` (`d.ts#L20127`). **There is no System role in
  stable.** The LM guide states: "Currently, the Language Model API doesn't
  support the use of system messages."
  (https://code.visualstudio.com/api/extension-guides/ai/language-model)
- `LanguageModelChatResponse` (`d.ts#L20191`): `.stream` and `.text` (Q2).
- `LanguageModelChatRequestOptions` (`d.ts#L20384`): `justification?`,
  `modelOptions?`, `tools?`, `toolMode?`.
- `LanguageModelChatTool` (`d.ts#L20876`): `name`, `description`,
  `inputSchema?: object`.
- `LanguageModelChatToolMode` (`d.ts#L20896`): `Auto = 1`, `Required = 2`.
- Parts: `LanguageModelTextPart` (L20966), `LanguageModelToolCallPart`
  (L20913: `callId`, `name`, `input: object`), `LanguageModelToolResultPart`
  (L20943: `callId`, `content[]`), `LanguageModelDataPart` (L21018, with
  static `image()`, `json()`, `text()`; stable since 1.106 -- absent from
  stable d.ts at tag 1.105.0, present at 1.106.0, verified by tag bisect),
  `LanguageModelPromptTsxPart` (L20983), `LanguageModelToolResult` (L20999).
- `LanguageModelError` (`d.ts#L20351`): static factories `NoPermissions`,
  `Blocked`, `NotFound`; instance `code: string` whose values are those three
  names "or `Unknown` for unspecified errors from the language model itself.
  In the latter case the `cause`-property will contain the actual error."
  That is the complete documented case list (Q2 has runtime extras).
- Tool implementation surface: `LanguageModelTool<T>` (`invoke`,
  `prepareInvocation?`) L21157, `LanguageModelToolInvocationOptions` L21072
  (`toolInvocationToken`, `input`, `tokenizationOptions?`),
  `LanguageModelToolTokenizationOptions` L21103 (`tokenBudget`,
  `countTokens`), `LanguageModelToolInformation` L21121,
  `PreparedToolInvocation`/`LanguageModelToolConfirmationMessages` L21180-L21206.
  `ChatParticipantToolToken` is `never` in stable (L21067) -- outside a chat
  participant you pass `undefined` to `lm.invokeTool`.
- Provider surface (all stable, since 1.104): `LanguageModelChatProvider`
  (`d.ts#L20683`: `provideLanguageModelChatInformation`,
  `provideLanguageModelChatResponse`, `provideTokenCount`, optional
  `onDidChangeLanguageModelChatInformation`), `LanguageModelChatInformation`
  (L20580: `id`, `name`, `family`, `version`, `maxInputTokens`,
  `maxOutputTokens`, `capabilities`, `tooltip?`, `detail?`),
  `LanguageModelChatCapabilities` (L20634: `imageInput?: boolean`,
  `toolCalling?: boolean | number` -- "If a number is provided, that is the
  maximum number of tools that can be provided in a request to the model"),
  `LanguageModelChatRequestMessage` (L20651),
  `ProvideLanguageModelChatResponseOptions` (L20552),
  `PrepareLanguageModelChatModelOptions` (L20723: `silent: boolean`).
- `ExtensionContext.languageModelAccessInformation:
  LanguageModelAccessInformation` (`d.ts#L8575`) with
  `canSendRequest(chat): boolean | undefined` and `onDidChange` (L20853).
- Chat participant API (`ChatParticipant`, `ChatRequest`, `ChatResponseStream`)
  is stable since 1.90; `ChatRequest.model: LanguageModelChat` ("the model that
  is currently selected in the UI") and `ChatRequest.toolInvocationToken` are
  stable, `model` finalized in 1.95 (v1_95 notes).

Contribution points (stable):

- `contributes.languageModelTools` -- required for `lm.registerTool`: "The
  tool must also be registered in the package.json `languageModelTools`
  contribution point" (`d.ts#L20768-L20771`). Fields documented in
  https://code.visualstudio.com/api/extension-guides/ai/tools : `name`
  (`{verb}_{noun}` format), `displayName`, `modelDescription`,
  `userDescription`, `inputSchema`, `canBeReferencedInPrompt`,
  `toolReferenceName`, `icon`, `tags`, `when`.
- `contributes.languageModelChatProviders` -- required for
  `lm.registerLanguageModelChatProvider`: "You must also define the language
  model chat provider via the `languageModelChatProviders` contribution point
  in package.json" (`d.ts#L20840-L20846`). Schema at
  `languageModels.ts#L811-L828`: required `vendor` ("A globally unique vendor
  of language model chat provider") and `displayName`; optional
  `managementCommand` and `configuration` (JSON schema, properties can be
  marked `secret`). Registering a provider for a vendor not declared in the
  contribution throws "Chat model provider uses UNKNOWN vendor"
  (`languageModels.ts#L1333`). Contributing generates activation event
  `onLanguageModelChatProvider:<vendor>`. Docs:
  https://code.visualstudio.com/api/extension-guides/ai/language-model-chat-provider

### Proposed at 1.132.0 (require `enabledApiProposals` + a non-stable context; see Q5 for what that means under F5)

From `src/vscode-dts/vscode.proposed.*.d.ts` at tag 1.132.0:

- `languageModelSystem`: adds `LanguageModelChatMessageRole.System = 3`. Using
  a System-role message without this proposal throws at runtime
  (`extHostLanguageModels.ts#L543-L545` calls `checkProposedApiEnabled`).
- `languageModelThinkingPart`: `LanguageModelThinkingPart` in the response
  stream + `LanguageModelChatMessage2`.
- `languageModelCapabilities`: consumer-side `LanguageModelChat.capabilities`
  (`supportsToolCalling`, `supportsImageToText`). Stable consumers cannot
  query tool-calling capability; only providers declare it.
- `chatProvider`: provider-side extras -- `requiresAuthorization`,
  `multiplierNumeric`, `isBYOK`, `isDefault`, `isUserSelectable`,
  `configurationSchema`, `requestInitiator`, `includeEncryptedThinking`,
  `editTools` capability. The core provider API is stable; only these extras
  are proposed.
- `languageModelToolSupportsModel`: `lm.registerToolDefinition` (register a
  tool without package.json contribution), invoke-by-information, per-model
  tool filtering.
- Also LM-adjacent: `contribLanguageModelToolSets`, `languageModelPricing`,
  `languageModelProxy`, `languageModelToolResultAudience`, `embeddings`.

Bottom line for the design: everything ETL Studio needs for an agent loop
(model selection, streaming, tool calling, provider registration) is stable
API. System role and thinking parts are the only relevant proposed pieces.

---

## 2. Streaming, cancellation, errors

Response shape (`d.ts#L20191-L20232`):

- `stream: AsyncIterable<LanguageModelTextPart | LanguageModelToolCallPart |
  LanguageModelDataPart | unknown>` -- "The `unknown`-type is used as a
  placeholder for future parts, like image data parts."
- `text: AsyncIterable<string>` -- "equivalent to filtering everything except
  for text parts from a stream."
- Part discrimination is `instanceof`-based (the d.ts example itself does
  `chunk instanceof LanguageModelTextPart`). At 1.132.0 the Copilot provider
  really does emit parts a stable consumer cannot name: thinking deltas as
  `LanguageModelThinkingPart` (proposed class) and trailing
  `LanguageModelDataPart`s with custom mime types `usage` (JSON APIUsage) and
  `stateful_marker` (`copilot lmAccess` `provideLanguageModelResponse`,
  mime constants in extensions/copilot/src/platform/endpoint/common/endpointTypes.ts).
  **A robust loop must silently skip parts it does not recognize.**

Errors on the stream (`d.ts#L20200-L20201`): "Note that this stream will error
when during data receiving an error occurs. Consumers of the stream should
handle the errors accordingly." Mechanically, a failed response rejects the
async iterable (`extHostLanguageModels.ts#L562-L576`); a failure to even start
the request rejects the `sendRequest` promise itself (L526-L535). So errors
must be handled in two places: around `await sendRequest(...)` and around the
`for await` loop.

Cancellation (`d.ts#L20203-L20204`): "To cancel the stream, the consumer can
cancel the token that was used to make the request or break from the
for-loop." Cancellation propagates to the provider via
`$cancelLanguageModelChatRequest` (`extHostLanguageModels.ts#L520-L524`).

`LanguageModelError` documented cases (`d.ts#L20276-L20288`, sendRequest doc):

- "user consent not given, see NoPermissions"
- "model does not exist anymore, see NotFound"
- "quota limits exceeded, see Blocked"
- "other issues in which case extension must check LanguageModelError.cause"

`code` values: `"NoPermissions" | "Blocked" | "NotFound" | "Unknown"`
(`d.ts#L20351-L20377`).

Copilot implementation reality at 1.132.0 (`copilot lmAccess`,
implementation detail -- verify on the Citi build):

- Client-side extension blocklist: `LanguageModelError.Blocked("The extension
  has been temporarily blocked due to making too many requests. Please try
  again later.")` (L657-L660), also raised when the server reports
  ExtensionBlocked (with retryAfter bookkeeping, L799-L804).
- Quota exhausted: a `LanguageModelError` whose `err.name` is
  `'ChatQuotaExceeded'` (message includes plan/quota-reset info) (L805-L810).
- Rate limited by the server: a **plain `Error`** with `err.name =
  'ChatRateLimited'` (L811-L815) -- not a `LanguageModelError`.
- Input over budget: plain `Error('Message exceeds token limit.')` (L700-L703).
- Output hitting the model's length limit is NOT an error: the partial
  response is returned as a successful (truncated) stream, with a warning in
  the Copilot log (L789-L796).

So error handling needs three tiers: `instanceof LanguageModelError` +
`.code`, then `err.name` string checks (`ChatQuotaExceeded`,
`ChatRateLimited`), then message-string fallbacks. The provider port should
normalize all of these into a core error taxonomy (feeds ticket 03).

---

## 3. Multi-turn agentic loops: consent, user-initiation, background use

Documented consent model
(https://code.visualstudio.com/api/extension-guides/ai/language-model):

> "Copilot's language models require consent from the user before an
> extension can use them. Consent is implemented as an authentication dialog.
> Because of that, `selectChatModels` should be called as part of a
> user-initiated action, such as a command."

And `d.ts#L20277-L20280` (sendRequest): "Calling this function for the first
time (for an extension) will show a consent dialog to the user and because of
that this function must _only be called in response to a user action!_
Extensions can use `LanguageModelAccessInformation.canSendRequest` to check if
they have the necessary permissions."

Mechanics at 1.132.0 (core source, not Copilot-specific):

- The gate exists only for models whose provider metadata declares `auth`,
  and only when the consumer is a **different extension** than the provider
  (`extHostLanguageModels.ts#L607-L612`). Copilot declares auth; a
  stable-API third-party provider has no way to declare it
  (`requiresAuthorization` is in the proposed `chatProvider`), so its models
  are consumable by other extensions without any dialog.
- Consent is implemented as a fake per-provider-extension
  AuthenticationProvider ("BIG HACK: Using AuthenticationProviders to check
  access to Language Models", `extHostLanguageModels.ts#L578`; provider
  registration in mainThreadLanguageModels.ts#L271-L283 with comment "The
  fake AuthenticationProvider that will be used to gate access to the
  Language Model").
- On `sendRequest`: silent session check first; if absent, a **modal auth
  dialog** (`forceNewSession`) is shown; `options.justification` is rendered
  into the dialog detail as "Justification: ..."
  (`extHostLanguageModels.ts#L579-L605`). Declining yields
  `LanguageModelError.NoPermissions("Language model 'X' cannot be used by
  'Y'.")` (L508-L513).
- `selectChatModels` itself never shows the modal -- it does a silent
  access-populate only (L440-L443, L614-L628). The dialog appears on the
  first `sendRequest`.
- The grant is persisted like authentication access (standard "Accounts"
  trusted-extensions machinery) and survives restarts; after the first grant
  every subsequent request is silent. `canSendRequest` "will not trigger a
  consent UI but just checks for a persisted state" (`d.ts#L20860-L20869`);
  it returns `undefined` if "consent hasn't been asked for".

Consequences for a long agentic loop:

- There is no per-request consent and no user-gesture enforcement in code.
  One dialog per (consumer extension, providing extension) pair, ever --
  then unlimited background `sendRequest` calls are permitted. A loop that
  starts from a command (as the docs require) pays the dialog at most once,
  ideally via a warm-up request before the loop.
- No documented limit on number of round trips or messages per conversation;
  each `sendRequest` is independent. The only hard budgets are tokens (Q6)
  and tool count (Q4).
- Rate limiting: "Extensions should responsibly use the language model and be
  aware of rate limiting. VS Code is transparent to the user regarding how
  extensions are using language models and how many requests each extension
  is sending and how that influences their respective quotas." Also:
  "Extensions should not use the Language Model API for integration tests
  due to rate-limitations." (LM guide.) Numeric limits are nowhere
  documented; Copilot enforces them server-side and via the client blocklist
  (Q2). Requests are attributed per extension via an
  `x-onbehalf-extension-id: <extId>/<version>` header (`copilot lmAccess`
  L709-L728).
- Note for prompt design: for requests coming from any extension other than
  Copilot itself, Copilot wraps the messages in its own prompt with safety
  rules (`noSafety: extensionId === this._envService.extensionId`,
  `copilot lmAccess` L670-L674) -- your messages are not the entire prompt,
  and part of the token budget is consumed by that wrapper.

---

## 4. Tool calling: declaration, round-trip, limits

Declaration paths:

1. Registered tools: `contributes.languageModelTools` in package.json +
   `lm.registerTool(name, impl)`. "A registered tool is available in the
   `lm.tools` list for any extension to see." (`d.ts#L20768-L20772`).
   Invocation goes through `lm.invokeTool`, input "will be validated against
   the schema declared by the tool" (`d.ts#L20782-L20785`).
2. Private tools: pass plain `LanguageModelChatTool` objects (name,
   description, inputSchema) in `LanguageModelChatRequestOptions.tools` --
   "These could be registered tools available via lm.tools, or private tools
   that are just implemented within the calling extension."
   (`d.ts#L20397-L20399`). Tools guide: "If you want the tool to be private
   to your extension, skip the tool registration step."
   For ETL Studio's self-contained loop, private tools suffice; no
   contribution point needed.

The documented round-trip (`d.ts#L20397-L20407`, normative):

> "If the LLM requests to call one of these tools, it will return a
> LanguageModelToolCallPart in LanguageModelChatResponse.stream. ... Then,
> the tool result can be provided to the LLM by creating an Assistant-type
> LanguageModelChatMessage with a LanguageModelToolCallPart, followed by a
> User-type message with a LanguageModelToolResultPart."

- `LanguageModelToolResultPart` "can only be included in the content of a
  User message" (`d.ts#L20939-L20942`); its `callId` must match the tool
  call's `callId`.
- Copilot validates the sequencing at request time; violation gives
  `Error('Invalid request: Tool call part must be followed by a User message
  with a LanguageModelToolResultPart with a matching callId.')`
  (`copilot lmAccess` L963).
- Tool results carry `LanguageModelTextPart | LanguageModelPromptTsxPart |
  LanguageModelDataPart | unknown` content (`d.ts#L20954`).

Limits (documented + implementation):

- API-level: no documented cap on tool count or payload size. The provider
  capability `toolCalling?: boolean | number` exists precisely so a model can
  advertise "the maximum number of tools that can be provided in a request"
  (`d.ts#L20641-L20645`).
- `toolMode: Required`: "Note - some models only support a single tool when
  using this mode." (`d.ts#L20902-L20906`). Copilot hard-enforces it:
  `Error('LanguageModelChatToolMode.Required is not supported with more than
  one tool')` (`copilot lmAccess` L744-L746).
- Copilot at 1.132.0: max **128 tools per request** -- `Error('Cannot have
  more than 128 tools per request.')` unless the endpoint supports tool
  search (`copilot lmAccess` L705-L707). Implementation detail; verify on
  the Citi build.
- Tool names (Copilot): must match `^[\w-]+$` -- "only alphanumeric
  characters, hyphens, and underscores are allowed" (L937-L943).
- Tool definitions and schemas are token-counted and subtracted from the
  prompt budget (L662-L664): budget = model max prompt tokens - Copilot
  wrapper overhead - completion reserve - tool tokens.
- Tool-result size: no limit anywhere except the next request's token budget.
  `LanguageModelToolInvocationOptions.tokenizationOptions.tokenBudget` is a
  hint "to hint at how many tokens the tool should return in its response"
  (`d.ts#L21093-L21097`), not enforcement.
- Confirmation UI applies to tools invoked through `lm.invokeTool` in the
  chat flow: "A generic confirmation dialog will always be shown for tools
  from extensions" (tools guide) with `prepareInvocation` customization and
  "Always Allow". Private tools invoked directly by your own code (your
  runtime calling your own functions) show no VS Code UI at all -- the
  confirmation machinery only exists inside `lm.invokeTool`/chat.

---

## 5. Model availability, selectors, and the F5 Extension Development Host

Selector semantics (verified in `languageModels.ts#L1304-L1327`): exact
equality per provided field (`vendor`, `family`, `version`, `id`), across the
global model cache; omitted selector = resolve every vendor. Calling
`selectChatModels` triggers activation of matching provider extensions
(activation event `onLanguageModelChatProvider:<vendor>`). "This can yield
multiple or no chat models and extensions must handle these cases, esp. when
no chat model exists, gracefully" and re-query on `onDidChangeChatModels`
(`d.ts#L20740-L20765`).

Copilot values:

- Vendor is the string `'copilot'` (`languageModels.ts#L49`:
  `COPILOT_VENDOR_ID = 'copilot'`; the d.ts gives `copilot` as the canonical
  vendor example, `d.ts#L20250-L20255`).
- `family`/`id`/`version` values "are defined by extensions contributing
  chat models and need to be looked up with them ... subject to change"
  (`d.ts#L20256-L20267`). The LM guide's family list ("Currently, gpt-4o,
  gpt-4o-mini, o1, o1-mini, claude-3.5-sonnet are supported") is visibly
  stale and cannot be trusted for current rosters.
- In the 1.132.0 Copilot implementation, the LM-API `maxInputTokens` is the
  raw model prompt window minus Copilot's wrapper overhead and completion
  reserve (`copilot lmAccess` L359), i.e. smaller than the marketing context
  size.

**GPT-5.Sol / Claude Opus 4.8 / Claude Sonnet 5 (Citi picker names): the
mapping from picker display name to `family`/`id` selector strings is not
documented anywhere public.** The picker shows
`LanguageModelChatInformation.name` ("shown in the model picker", provider
guide); `family`/`id` are separate opaque strings chosen by the provider or
returned by the Copilot service for enterprise custom models. "GPT-5.Sol"
looks like a Citi-side custom deployment name; only on-machine enumeration
(checklist below) can produce the real selector strings. Do not hardcode
guesses.

BYO provider visibility (bears on R2D2-as-provider):

- Stable `LanguageModelChatProvider` doc: "A LanguageModelChatProvider
  implements access to language models, which users can then use through the
  chat view, **or through extension API by acquiring a LanguageModelChat**"
  (`d.ts#L20679-L20682`). The selection loop matches all cached models
  regardless of which extension contributed them -- so yes, models registered
  via `registerLanguageModelChatProvider` are visible to OTHER extensions via
  `selectChatModels` (and in the chat model picker, per the v1.104 note).
- Cross-extension consent for such models: none in stable (the `auth`
  metadata that triggers the consent dialog is not settable via the stable
  provider API; `requiresAuthorization` is proposed). An extension consuming
  its own provider's models is explicitly exempt from the consent gate
  (`extHostLanguageModels.ts#L607-L612`).
- Enterprise policy risk: the provider guide warns "If you are a Copilot
  Business or Enterprise user, your administrator can disable the **Bring
  Your Own Language Model Key** policy ... for models provided through this
  API." A Citi admin policy could therefore kill third-party provider models
  entirely -- must be checked on-machine before promising the R2D2-provider
  path.

F5 Extension Development Host:

- The default generated launch config passes only
  `--extensionDevelopmentPath=${workspaceFolder}` (microsoft/vscode-generator-code,
  generators/app/templates/ext-command-ts/vscode/launch.json) -- **no**
  `--disable-extensions`.
- "VS Code uses the globally installed instance of VS Code and will load all
  installed extensions" unless you add `--disable-extensions`
  (https://code.visualstudio.com/api/working-with-extensions/testing-extension,
  "Disabling other extensions while debugging"; written for test launches,
  same `extensionHost` launch type as F5 Run Extension).
  So by default Copilot + Copilot Chat run inside the dev host, and its model
  roster is the same as the main window's.
- Settings/state: the dev host runs on the same user data dir/profile unless
  `--user-data-dir`/`--profile` is passed; the same doc uses a dedicated
  `--user-data-dir` in CI precisely because otherwise "previously persisted
  trust decisions" leak in -- i.e. persisted user state is shared by default.
  Explicit statements that authentication sessions (Copilot entitlement) are
  shared do not exist in the docs -- strong inference, verify on-machine
  (checklist step 2).
- Proposed APIs under F5 -- the precise rule, from
  src/vs/workbench/services/extensions/common/extensionsProposedApi.ts#L34-L37
  at 1.132.0. Proposals are honored iff one of:
  1. running VS Code from sources;
  2. extension development mode AND `productService.quality !== 'stable'`
     (in-source comment: "do not allow proposed API against stable builds
     when developing an extension");
  3. `--enable-proposed-api` passed without an extension id (enables all);
  4. `--enable-proposed-api <extId>` for that extension;
  5. product.json `extensionEnabledApiProposals` allowlist (how Copilot gets
     its own proposals in stable).
  Otherwise the extension's `enabledApiProposals` is nulled with error
  "CANNOT USE these API proposals ... You MUST start in extension development
  mode or use the --enable-proposed-api command line flag" (L110-L114).
  **Consequence: on Citi's stable VS Code, plain F5 does NOT enable proposed
  APIs.** Adding `"--enable-proposed-api=<publisher>.<name>"` to the launch
  config args should enable them even on stable (path 3/4 has no quality
  check) -- but this exact combination on the Citi build is an on-machine
  check. The official docs page
  (https://code.visualstudio.com/api/advanced-topics/using-proposed-api)
  only describes the Insiders flow ("only available in Insiders
  distribution") and the `argv.json` `enable-proposed-api` list; it does not
  document the stable+flag path, so treat it as unsupported-but-working.
  Marketplace restrictions are irrelevant for an F5-only demo; for the
  record: "you should not publish extensions using the proposed API on the
  Marketplace".

Recommendation embedded in these facts: design the demo against stable API
only (System-role emulation via a leading User message, no thinking parts),
so the F5 story has zero flags; keep `--enable-proposed-api` as a verified
fallback if thinking-part streaming is wanted for the UI.

---

## 6. Token/context limits, output control, quota surface

- `maxInputTokens` (stable, consumer): "The maximum number of tokens that can
  be sent to the model in a single request" (`d.ts#L20269-L20272`). LM guide:
  "The returned model object from the selectChatModels call has a
  maxInputTokens attribute that shows the token limit."
- `countTokens(text | LanguageModelChatMessage)` uses "the model specific
  tokenizer-logic" (`d.ts#L20301-L20308`), delegated to the provider's
  `provideTokenCount`.
- **No output-token field exists on the stable consumer surface.**
  `maxOutputTokens` exists only on the provider-side
  `LanguageModelChatInformation` (`d.ts#L20620-L20623`) and is not exposed to
  consumers in stable (it is part of proposed surfaces).
- Output control in practice: `modelOptions` is a documented pass-through
  ("specific to the language model and need to be looked up in the respective
  documentation", `d.ts#L20391-L20395`). The 1.132.0 Copilot implementation
  accepts exactly: `stop` (string|string[]), `temperature`, `max_tokens`,
  `frequency_penalty`, `presence_penalty` -- all other keys are silently
  dropped (`copilot lmAccess` L988-L1015). So
  `modelOptions: { max_tokens: N }` is the (undocumented,
  implementation-defined) output cap for Copilot models. Verify on the Citi
  build.
- Context overflow (input): Copilot throws plain
  `Error('Message exceeds token limit.')` when the rendered prompt exceeds
  budget, where budget = model max prompt tokens - Copilot wrapper - reserved
  completion tokens - tool tokens (`copilot lmAccess` L662-L707). VS Code
  itself imposes nothing. Overflow is NOT a `LanguageModelError`.
- Output overflow: truncation, success, warning log (Q2; L789-L796).
- Quota/billing surface: documented only as `Blocked` ("quota limits
  exceeded, see Blocked", `d.ts#L20287`) plus the rate-limiting guide text
  (Q3). Copilot specifics at 1.132.0: `ChatQuotaExceeded` named
  `LanguageModelError` (message mentions plan and quota reset date),
  `ChatRateLimited` named plain Error, temporary per-extension blocklist
  (Q2). Per-request token usage arrives as a trailing
  `LanguageModelDataPart` with mime `usage` containing JSON usage data
  (`copilot lmAccess` L888-L891) -- undocumented but handy for the demo's
  credit accounting (~20k credits context). Premium-request multipliers
  (`multiplierNumeric`) are proposed-only; credits/billing are otherwise
  invisible to the API.

---

## 7. What leaks `vscode` types into agent-core logic (provider-port audit)

Everything below crosses the `vscode.lm` boundary and must be wrapped by the
adapter; the core must define its own equivalents (feeds ticket 03):

- `CancellationToken` / `CancellationTokenSource` -- `sendRequest`,
  `countTokens`, tool `invoke`, every provider method. Core should carry its
  own abort signal; adapter bridges (`new vscode.CancellationTokenSource()`,
  cancel on core abort).
- `Event<T>` -- `lm.onDidChangeChatModels`,
  `LanguageModelAccessInformation.onDidChange`,
  `onDidChangeLanguageModelChatInformation`. VS Code event objects are
  disposable-returning functions; core should expose its own subscription
  shape.
- `Disposable` -- returned by `registerTool`,
  `registerLanguageModelChatProvider`.
- `Thenable` -- harmless (PromiseLike), but signatures use it.
- **Class-identity coupling (the sharpest edge):** stream parts and message
  content are discriminated by `instanceof` against classes exported by the
  `vscode` module -- `LanguageModelTextPart`, `LanguageModelToolCallPart`,
  `LanguageModelToolResultPart`, `LanguageModelDataPart`,
  `LanguageModelPromptTsxPart`. Messages must be built with
  `vscode.LanguageModelChatMessage.User/.Assistant` or the constructor, and
  Copilot's own validation does `instanceof` checks on the parts you send
  (`copilot lmAccess` L955-L979). Core-side part/message types must be plain
  data; the adapter converts both directions at the boundary. The stream's
  `unknown` members mean the adapter must map-and-skip, never
  exhaustive-match.
- Enums with fixed numeric values: `LanguageModelChatMessageRole` (User=1,
  Assistant=2), `LanguageModelChatToolMode` (Auto=1, Required=2). Fine to
  mirror numerically in core, but do not import.
- `LanguageModelChat` itself: a **frozen** object
  (`extHostLanguageModels.ts#L483`) -- cannot be patched or subclassed;
  wrap, never extend.
- `LanguageModelError`: class + `code` string + (Copilot) `err.name`
  conventions and plain-Error cases -- normalize into a core error taxonomy
  inside the adapter (string matching for `'Message exceeds token limit.'`
  and `err.name` values is unavoidable and should live only in the adapter).
- Tool surface: `LanguageModelToolResult`, `LanguageModelToolInvocationOptions`
  (`toolInvocationToken` is chat-participant plumbing -- keep it out of core;
  pass `undefined` from a non-chat runtime), `MarkdownString` (confirmation
  messages), `ProviderResult`.
- `ExtensionContext.languageModelAccessInformation` -- consent pre-check is
  reachable only through the extension context; expose as a capability query
  on the port (`canSend(): boolean | 'unknown'`).
- Extension-host residency: `vscode.lm` exists only inside the extension
  host process. The port implementation must live in the extension; a core
  that runs elsewhere (worker, webview, server) needs the port to be
  message-passing-friendly (all-data DTOs, no live vscode objects) -- the
  shapes above are all JSON-serializable once converted, so nothing blocks
  the port.

No API shape forces `vscode` types into the core: every input is
constructible from plain data and every output is reducible to plain data.
The port is feasible with a thin adapter; the only irreducible behaviors the
core must model are (a) streamed part union with unknown members, (b) the
tool-call/tool-result two-message convention, (c) consent as an async
first-call side effect, (d) token budgeting via `maxInputTokens` +
`countTokens`.

---

## On-machine checklist (Citi F5 dev host)

Goal: turn every "verify on-machine" above into a recorded fact. Total time
~30 min. Keep DevTools console (Help > Toggle Developer Tools) open in the
dev host; also watch the "Extension Host" and "GitHub Copilot Chat" output
channels.

### 0. Record versions

- Main window: Help > About -- record VS Code version (facts above are
  stamped 1.132.0; if Citi is older, re-check: provider API needs >= 1.104,
  `LanguageModelDataPart` >= 1.106, tools >= 1.95, base LM API >= 1.90).
- Extensions view: record `GitHub Copilot` and `GitHub Copilot Chat` versions
  (Copilot-side behaviors -- 128-tool cap, modelOptions keys, usage part --
  are per-Copilot-version).

### 1. Minimal probe extension

Create a folder `lm-probe/` with exactly two files (no build step -- plain
JS):

`package.json`:

```json
{
  "name": "lm-probe",
  "displayName": "LM Probe",
  "publisher": "citi-demo",
  "version": "0.0.1",
  "engines": { "vscode": "^1.104.0" },
  "main": "./extension.js",
  "activationEvents": [],
  "contributes": {
    "commands": [
      { "command": "lmProbe.enumerate", "title": "LM Probe: Enumerate Models" },
      { "command": "lmProbe.send", "title": "LM Probe: Send Request (consent test)" },
      { "command": "lmProbe.toolLoop", "title": "LM Probe: Tool Round Trip" },
      { "command": "lmProbe.limits", "title": "LM Probe: Limits (overflow, max_tokens)" }
    ]
  }
}
```

`extension.js`:

```js
const vscode = require('vscode');
const out = vscode.window.createOutputChannel('LM Probe');

async function enumerate() {
  out.show(true);
  const models = await vscode.lm.selectChatModels(); // no selector: everything
  out.appendLine('total models: ' + models.length);
  for (const m of models) {
    out.appendLine(JSON.stringify({
      vendor: m.vendor, family: m.family, id: m.id,
      version: m.version, name: m.name, maxInputTokens: m.maxInputTokens
    }));
  }
  const copilot = await vscode.lm.selectChatModels({ vendor: 'copilot' });
  out.appendLine('vendor=copilot count: ' + copilot.length);
}

async function send(ctx) {
  const [model] = await vscode.lm.selectChatModels({ vendor: 'copilot' });
  if (!model) { out.appendLine('NO MODELS'); return; }
  out.appendLine('canSendRequest BEFORE: ' +
    ctx.languageModelAccessInformation.canSendRequest(model));
  try {
    const res = await model.sendRequest(
      [vscode.LanguageModelChatMessage.User('Reply with the single word: pong')],
      { justification: 'ETL Studio demo: verifying language model access.' },
      new vscode.CancellationTokenSource().token);
    let txt = '';
    for await (const part of res.stream) {
      if (part instanceof vscode.LanguageModelTextPart) { txt += part.value; }
      else { out.appendLine('non-text part: ' + part.constructor.name +
        (part.mimeType ? ' mime=' + part.mimeType : '')); }
    }
    out.appendLine('response: ' + txt);
  } catch (e) {
    out.appendLine('ERROR code=' + (e.code || '-') + ' name=' + e.name +
      ' msg=' + e.message);
  }
  out.appendLine('canSendRequest AFTER: ' +
    ctx.languageModelAccessInformation.canSendRequest(model));
}

async function toolLoop() {
  const [model] = await vscode.lm.selectChatModels({ vendor: 'copilot' });
  const tools = [{
    name: 'get_row_count',
    description: 'Returns the row count of a named table.',
    inputSchema: { type: 'object',
      properties: { table: { type: 'string' } }, required: ['table'] }
  }];
  const messages = [vscode.LanguageModelChatMessage.User(
    'How many rows does table CUSTOMERS have? Use the tool.')];
  for (let turn = 0; turn < 5; turn++) {
    const res = await model.sendRequest(messages, { tools });
    const calls = []; let text = '';
    for await (const p of res.stream) {
      if (p instanceof vscode.LanguageModelTextPart) { text += p.value; }
      if (p instanceof vscode.LanguageModelToolCallPart) { calls.push(p); }
    }
    if (!calls.length) { out.appendLine('final answer: ' + text); return; }
    messages.push(vscode.LanguageModelChatMessage.Assistant(calls));
    messages.push(vscode.LanguageModelChatMessage.User(
      calls.map(c => new vscode.LanguageModelToolResultPart(c.callId,
        [new vscode.LanguageModelTextPart('42')]))));
    out.appendLine('turn ' + turn + ': tool calls=' +
      calls.map(c => c.name + ' ' + JSON.stringify(c.input)).join('; '));
  }
}

async function limits() {
  const [model] = await vscode.lm.selectChatModels({ vendor: 'copilot' });
  // output cap probe (undocumented modelOptions.max_tokens):
  try {
    const r = await model.sendRequest(
      [vscode.LanguageModelChatMessage.User('Count from 1 to 200, comma separated.')],
      { modelOptions: { max_tokens: 30 } });
    let t = ''; for await (const c of r.text) { t += c; }
    out.appendLine('max_tokens=30 output length: ' + t.length + ' :: ' + t.slice(0, 120));
  } catch (e) { out.appendLine('max_tokens probe error: ' + e.message); }
  // input overflow probe:
  try {
    const big = 'lorem ipsum '.repeat(Math.ceil(model.maxInputTokens));
    out.appendLine('countTokens(big) = ' + await model.countTokens(big));
    await model.sendRequest([vscode.LanguageModelChatMessage.User(big)]);
    out.appendLine('overflow: NO ERROR (unexpected)');
  } catch (e) {
    out.appendLine('overflow error: code=' + (e.code || '-') + ' name=' +
      e.name + ' msg=' + e.message);
  }
}

exports.activate = (ctx) => {
  ctx.subscriptions.push(
    vscode.commands.registerCommand('lmProbe.enumerate', enumerate),
    vscode.commands.registerCommand('lmProbe.send', () => send(ctx)),
    vscode.commands.registerCommand('lmProbe.toolLoop', toolLoop),
    vscode.commands.registerCommand('lmProbe.limits', limits));
};
```

`.vscode/launch.json` inside `lm-probe/`:

```json
{
  "version": "0.2.0",
  "configurations": [{
    "name": "Run LM Probe",
    "type": "extensionHost",
    "request": "launch",
    "args": ["--extensionDevelopmentPath=${workspaceFolder}"]
  }]
}
```

Note: no `--disable-extensions` -- Copilot must load in the dev host.

### 2. Entitlement + auth sharing

- F5. In the dev host: Accounts icon -- confirm the GitHub account is already
  signed in (no re-auth) and Copilot chat works. Record: dev host shares main
  install auth: yes/no.
- Run "LM Probe: Enumerate Models". Record the full JSON lines. This answers:
  does the F5 host see the Citi roster; and the exact `vendor/family/id/
  version/name/maxInputTokens` for **GPT-5.Sol**, **Claude Opus 4.8**,
  **Claude Sonnet 5** (match by `name`, record their `family` and `id` --
  these are the selector strings the provider port will use).

### 3. Consent dialog observation

- Run "LM Probe: Send Request". Expect (first run only): a modal
  authentication-style dialog naming the probe extension and Copilot, with
  the line "Justification: ETL Studio demo: ...". Record exact wording,
  and the `canSendRequest` values before (expect `undefined`) / after
  (expect `true`).
- Click Cancel first: expect error `code=NoPermissions`. Re-run and Allow.
- Re-run again: no dialog (persisted grant).
- Revoke to re-test: Accounts icon > the language-models entry > Manage
  Trusted Extensions.
- Loop behavior: run "LM Probe: Tool Round Trip" -- confirm 2+ consecutive
  sendRequests complete with no further prompts (multi-turn loop viability).

### 4. Tool round trip

- "LM Probe: Tool Loop" output should show a `get_row_count` call with
  `{"table":"CUSTOMERS"}` then a final answer containing 42. Record which
  model produced it and whether any non-text parts appeared (thinking/data
  parts on stable -- expected to surface as unknown constructor names).

### 5. Limits

- "LM Probe: Limits": record whether `max_tokens: 30` truncates (proves the
  undocumented output-cap path on the Citi Copilot build) and the exact
  overflow error text (expect 'Message exceeds token limit.' on 1.132-era
  Copilot).

### 6. Proposed API under F5 on the Citi stable build

- Add `"enabledApiProposals": ["languageModelThinkingPart"]` to the probe's
  package.json. F5 without flags: check the Extension Host log for the
  "CANNOT USE these API proposals" error -- confirms proposals are OFF under
  plain F5 on stable.
- Then add `"--enable-proposed-api=citi-demo.lm-probe"` to launch args and
  retest (a thinking-capable model should now stream
  `LanguageModelThinkingPart` instances in step 4's non-text log). Record
  whether the Citi build honors the flag.

### 7. Policy check for the future R2D2-provider path

- Ask the Copilot admin (or check
  https://github.com/settings/copilot/features from a Citi account) whether
  the "Bring Your Own Language Model Key" / MCP policies are disabled --
  this gates third-party `languageModelChatProviders` models on
  Business/Enterprise (provider guide note).

---

## Confidence and gaps

High confidence (read directly from stamped primary sources):
- Stable-vs-proposed split at 1.132.0, all type shapes and line-cited
  docstrings; stabilization versions 1.90 / 1.95 / 1.104 / 1.106 (release
  notes + tag bisects).
- Consent mechanics (core source, provider-agnostic), selector matching,
  cross-extension visibility of provider models, proposed-API gating rules
  including the stable+F5 refusal.

Medium confidence (primary source, but implementation detail of the Copilot
build vendored in vscode 1.132.0 -- Citi's installed Copilot version may
behave differently):
- 128-tool cap, Required-mode single-tool restriction, tool-name regex,
  'Message exceeds token limit.', truncated-output-as-success,
  ChatQuotaExceeded / ChatRateLimited names, modelOptions accepted keys
  (max_tokens etc.), usage data part, safety-prompt wrapping, onbehalf
  header.

Unverifiable off-machine (checklist covers all):
- Citi's actual VS Code + Copilot versions; whether the roster (GPT-5.Sol,
  Claude Opus 4.8, Claude Sonnet 5) surfaces through `vscode.lm` inside the
  F5 host at all, and their real `family`/`id` selector strings.
- Auth-session sharing in the dev host (documented only indirectly).
- Whether `--enable-proposed-api` works on the Citi stable build (code says
  yes at 1.132.0; enterprise builds/policies could interfere).
- Copilot Business/Enterprise policy state for third-party model providers.
- Rate-limit numerics (undocumented everywhere, server-side).
- Exact consent-dialog wording (mechanism verified; copy is l10n/UI-owned).

Doc-vs-code conflicts found (code wins, both cited): the LM guide's model
family list is stale; the using-proposed-api page describes only the Insiders
flow while the enforcement code also honors `--enable-proposed-api` on
stable; the guide says "system messages" are unsupported -- true for stable,
while the `languageModelSystem` proposal adds the role behind a flag.
