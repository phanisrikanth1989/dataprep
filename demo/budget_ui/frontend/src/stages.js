// src/stages.js
// The ONE canonical, ordered stage list -- keyed by the DAEMON'S stage names.
//
// CRITICAL re-keying: the prototype keyed its stepper/rail/thinking-state by ROLE
// keys (interpreter/flow/configurator/assembler/approval/test). The daemon emits
// stage NAMES (reading/interpreting/designing/configuring/wiring/signoff/testing,
// then a terminal `done`). Only "reading" overlaps; a naive port would light 1 of 7
// steps and blank the thinking-pill for every later stage. So the prototype's
// STAGES/THOUGHTS/rail narration are re-keyed to the daemon names here.
//
// GENERIC: these describe the ETL-builder's reasoning phases, not any one pipeline.

export const STAGES = [
  { name: "reading",      k: "Read",       l: "Reading your document" },
  { name: "interpreting", k: "Understand", l: "Understanding the rules" },
  { name: "designing",    k: "Design",     l: "Designing the pipeline" },
  { name: "configuring",  k: "Configure",  l: "Configuring each step" },
  { name: "wiring",       k: "Wire",       l: "Wiring it together" },
  { name: "signoff",      k: "Sign-off",   l: "Human sign-off on the code" },
  { name: "testing",      k: "Test",       l: "Testing against your sample" },
];

// The 7 stepper stages, in order. `done` is terminal and is NOT a stepper step
// (the prototype likewise filtered its trailing "done" role out of the stepper).
export const STAGE_ORDER = STAGES.map((s) => s.name);
export const STAGE_BY_NAME = Object.fromEntries(STAGES.map((s) => [s.name, s]));

// The specialist that owns each stage. The assistant panel tags every message with its agent
// (avatar initial + name) so the run reads as a team of specialists handing off down the line.
// `human: true` marks the sign-off beat -- that's YOU, not an agent (the human-in-the-loop).
export const AGENTS = {
  reading:      { initial: "R", name: "Reader" },
  interpreting: { initial: "I", name: "Interpreter" },
  designing:    { initial: "D", name: "Designer" },
  configuring:  { initial: "C", name: "Configurator" },
  wiring:       { initial: "A", name: "Assembler" },
  signoff:      { initial: "H", name: "Sign-off", human: true },
  testing:      { initial: "T", name: "Tester" },
};

// Rotating "thoughts" for the thinking-state pill (the star of the demo), re-keyed
// from the prototype's THOUGHTS to the daemon stage names.
export const THOUGHTS = {
  reading:      ["scanning the document", "finding the data tables", "reading the sample files"],
  interpreting: ["normalizing the rules", "checking each lookup key", "noting what to keep"],
  designing:    ["comparing a join vs a lookup", "choosing vectorized for speed", "ordering the steps"],
  configuring:  ["setting the filter condition", "wiring the join keys", "pinning batch mode", "reading the component behaviour", "checking every config"],
  wiring:       ["connecting the flows", "adding the job envelope"],
  signoff:      ["surfacing the generated code", "waiting for sign-off"],
  testing:      ["loading the job", "running the engine", "comparing to your answer key"],
};

// Short stepper label: strip the leading verb word from the full stage line, exactly
// as the prototype did (e.g. "Reading your document" -> "your document").
export function stepLabel(l) {
  return l.replace(/^[A-Z][a-z]+ /, "");
}
