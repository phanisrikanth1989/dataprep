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
  reading: [
    "scanning the document", "finding the data tables", "reading the attached sample files",
    "cataloguing every source", "detecting the field delimiters", "reading the column headers",
    "parsing the source-to-target map", "noting the special-handling prose", "counting the columns per source",
    "separating data from narrative", "extracting the business rules", "resolving the sample rows",
    "accounting for every section", "assembling the requirement extract",
  ],
  interpreting: [
    "normalizing the rules", "typing each transformation", "checking each lookup key",
    "noting what to keep and drop", "resolving the join cardinality", "reading the no-match handling",
    "inferring the column types", "checking for duplicate keys", "carrying the special-handling notes",
    "flagging anything ambiguous", "ordering the operations", "mapping each rule to a step",
    "confirming the sort direction", "validating the schema shape",
  ],
  designing: [
    "comparing a join vs a lookup", "choosing vectorized for speed", "picking the fastest fit per rule",
    "ordering the pipeline steps", "placing the filter before the joins", "keeping the lookup key unique",
    "weighing left-outer vs inner join", "putting the sort last", "pushing filters upstream",
    "avoiding a row-by-row node", "sizing the cartesian risk", "planning the reject route",
    "naming each node", "minimizing the node count",
  ],
  configuring: [
    "setting the filter condition", "wiring the join keys", "pinning batch mode",
    "reading the component behaviour", "checking every config value", "choosing the match mode",
    "setting the sort type", "authoring the derive code", "picking the delimiter",
    "validating against the schema", "setting the no-match handling", "double-checking the enums",
    "matching the curated reference", "clearing the reported errors",
  ],
  wiring: [
    "connecting the flows", "adding the job envelope", "binding each input and output",
    "wiring the subjob triggers", "setting the terminal output id", "linking the lookup inputs",
    "adding the routines block", "ordering the components", "checking every flow endpoint",
    "finalizing the ids", "assembling the runnable job", "validating the wiring",
  ],
  signoff: [
    "surfacing the generated code", "highlighting the unsandboxed cell", "showing exactly what will run",
    "explaining what the code does", "flagging the security note", "presenting the code for review",
    "holding until you approve", "waiting for your sign-off",
  ],
  testing: [
    "loading the job", "running the engine", "reading the produced output",
    "comparing to your answer key", "diffing every row", "checking the row counts",
    "grading against the golden", "verifying each column", "confirming the sort order",
    "checking for dropped rows", "tallying the matches", "computing the verdict",
  ],
};

// Short stepper label: strip the leading verb word from the full stage line, exactly
// as the prototype did (e.g. "Reading your document" -> "your document").
export function stepLabel(l) {
  return l.replace(/^[A-Z][a-z]+ /, "");
}
