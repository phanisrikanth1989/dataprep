const vscode = require('vscode');
const out = vscode.window.createOutputChannel('LM Probe');

const KNOWN_PARTS = ['LanguageModelTextPart', 'LanguageModelToolCallPart',
  'LanguageModelToolResultPart', 'LanguageModelDataPart',
  'LanguageModelPromptTsxPart', 'LanguageModelThinkingPart'];

// Product builds minify constructor names (Mac dry run printed `i` for the
// usage data part), so name parts by instanceof against the vscode exports.
// ThinkingPart exists on the vscode module only when proposals are enabled.
function partName(p) {
  for (const n of KNOWN_PARTS) {
    const C = vscode[n];
    if (C && p instanceof C) { return n; }
  }
  return (p && p.constructor) ? p.constructor.name + '(minified?)' : typeof p;
}

// Describe a stream part we can't (or don't) handle: name, mime type,
// value preview, decoded data payload. A Copilot `usage` data part surfaces
// its full JSON here.
function describePart(p) {
  let s = partName(p);
  try {
    if (p && p.mimeType) { s += ' mime=' + p.mimeType; }
    if (p && typeof p.value === 'string') { s += ' value=' + JSON.stringify(p.value.slice(0, 300)); }
    if (p && p.data) { s += ' data=' + new TextDecoder().decode(p.data).slice(0, 2000); }
  } catch (e) { s += ' (describe failed: ' + e.message + ')'; }
  return s;
}

function logErr(where, e) {
  out.appendLine(where + ' ERROR code=' + ((e && e.code) || '-') + ' name=' +
    (e && e.name) + ' msg=' + (e && e.message));
}

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
  if (models.length === 0) {
    out.appendLine('0 models: wait for Copilot to finish signing in, then re-run this command.');
  }
}

async function send(ctx) {
  out.show(true);
  const [model] = await vscode.lm.selectChatModels({ vendor: 'copilot' });
  if (!model) { out.appendLine('NO MODELS'); return; }
  const access = ctx.languageModelAccessInformation;
  out.appendLine('canSendRequest BEFORE: ' +
    (access ? access.canSendRequest(model) : 'languageModelAccessInformation MISSING'));
  try {
    const res = await model.sendRequest(
      [vscode.LanguageModelChatMessage.User('Reply with the single word: pong')],
      { justification: 'ETL Studio demo: verifying language model access.' },
      new vscode.CancellationTokenSource().token);
    let txt = '';
    for await (const part of res.stream) {
      if (part instanceof vscode.LanguageModelTextPart) { txt += part.value; }
      else { out.appendLine('non-text part: ' + describePart(part)); }
    }
    out.appendLine('response: ' + txt);
  } catch (e) { logErr('send', e); }
  out.appendLine('canSendRequest AFTER: ' +
    (access ? access.canSendRequest(model) : 'languageModelAccessInformation MISSING'));
}

async function toolLoop() {
  out.show(true);
  const [model] = await vscode.lm.selectChatModels({ vendor: 'copilot' });
  if (!model) { out.appendLine('NO MODELS'); return; }
  out.appendLine('toolLoop model: ' + model.name +
    ' (family=' + model.family + ' id=' + model.id + ')');
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
      else if (p instanceof vscode.LanguageModelToolCallPart) { calls.push(p); }
      else { out.appendLine('turn ' + turn + ' non-text part: ' + describePart(p)); }
    }
    if (!calls.length) { out.appendLine('final answer: ' + text); return; }
    messages.push(vscode.LanguageModelChatMessage.Assistant(calls));
    messages.push(vscode.LanguageModelChatMessage.User(
      calls.map(c => new vscode.LanguageModelToolResultPart(c.callId,
        [new vscode.LanguageModelTextPart('42')]))));
    out.appendLine('turn ' + turn + ': tool calls=' +
      calls.map(c => c.name + ' ' + JSON.stringify(c.input)).join('; '));
  }
  out.appendLine('toolLoop: hit 5-turn cap without a final text answer');
}

async function limits() {
  out.show(true);
  const [model] = await vscode.lm.selectChatModels({ vendor: 'copilot' });
  if (!model) { out.appendLine('NO MODELS'); return; }
  out.appendLine('limits model: ' + model.name +
    ' maxInputTokens=' + model.maxInputTokens);
  // output cap probe (undocumented modelOptions.max_tokens):
  try {
    const r = await model.sendRequest(
      [vscode.LanguageModelChatMessage.User('Count from 1 to 200, comma separated.')],
      { modelOptions: { max_tokens: 30 } });
    let t = ''; for await (const c of r.text) { t += c; }
    out.appendLine('max_tokens=30 output length: ' + t.length + ' :: ' + t.slice(0, 120));
  } catch (e) { logErr('max_tokens probe', e); }
  // input overflow probe: must exceed the raw context window, not just the
  // advertised LM-API budget -- on the Mac dry run, ~2x the advertised
  // maxInputTokens went through without any error ('lorem ipsum ' is ~2
  // tokens per repeat, so this is ~max(4x advertised, ~500k) tokens).
  try {
    const repeats = Math.max(2 * model.maxInputTokens, 250000);
    const big = 'lorem ipsum '.repeat(repeats);
    out.appendLine('countTokens(big) = ' + await model.countTokens(big));
    await model.sendRequest([vscode.LanguageModelChatMessage.User(big)]);
    out.appendLine('overflow: NO ERROR at ~' + (2 * repeats) +
      ' tokens (no overflow error surfaced - budget proactively)');
  } catch (e) { logErr('overflow probe', e); }
}

exports.activate = (ctx) => {
  const wrap = (name, fn) =>
    vscode.commands.registerCommand(name, () => fn().catch(e => logErr(name, e)));
  ctx.subscriptions.push(
    wrap('lmProbe.enumerate', enumerate),
    wrap('lmProbe.send', () => send(ctx)),
    wrap('lmProbe.toolLoop', toolLoop),
    wrap('lmProbe.limits', limits));
};
