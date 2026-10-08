# v1 engine semantics around its components (digest for the v2 core)

Read 2026-10-05 at commit `0d2348bf` on `feature/engine-v2`; `src/v1`, `src/converters` and the cited tests are unchanged through `65e36b7d`. Sources: code and tests only. `docs/` was not used.

Conventions
- A bare file name (`executor.py:344`) is under `src/v1/engine/`. `components/...` is under `src/v1/engine/components/`. Other paths start at the repo root.
- "observed" = I ran it: the real `ETLEngine` on in-memory job dicts, with a stub `BaseComponent` subclass registered in-process as type `Probe`, or with real components where named. The scripts were throwaway (temp dir) and are not kept.
- Observation environment: one Mac, Python 3.14.6, pandas 3.0.5, numpy 2.5.2. Engine-logic observations do not depend on pandas. The coercion results in section 8 do, and are provisional until repeated on the target servers.
- No JVM on this machine: every statement about `{{java}}` or the bridge comes from reading code and was never observed.

## 1. The job config as v1 reads it

A config is a dict or a path to a JSON file (engine.py:40-46). `{}` is valid and returns `success` with 0 components (observed).

Top-level keys

| Key | Read at | Default | Effect |
|---|---|---|---|
| `job_name` | engine.py:123 | `unnamed_job` | label in the returned stats (engine.py:269) |
| `components` | engine.py:187 (also 99, 115, 155, 238, 254) | `[]` | component list. List order matters (section 4) |
| `flows` | engine.py:156 | `[]` | section 3 |
| `triggers` | engine.py:157, 229 | `[]` | section 5 |
| `context` | engine.py:126 | `{}` | context groups (section 2) |
| `default_context` | engine.py:127 | `Default` | the one group that is loaded |
| `java_config` | engine.py:53-57 | `{}` | `enabled` (default false): when true the bridge starts in the constructor and gets `routines`, `libraries`, `routine_jars`. A start failure raises out of the constructor (engine.py:61-65; observed with no JVM: `JavaBridgeError`) |
| `python_config` | engine.py:74-80 | `{}` | `enabled`, `routines_dir` (`src/python_routines`), `routines` |
| `oracle_config` | engine.py:84, 101-102 | `{}` | `enabled`, `thick_mode`. The manager also starts when any component type is in the Oracle set (engine.py:86-100) |
| `mssql_config` | engine.py:108, 117 | `{}` | `enabled`; also auto-starts on MSSql types (engine.py:109-116) |
| `engine_config` | engine.py:137, 170 | `{}` | `jobs_dir`, `max_run_job_depth` (2) for tRunJob (engine.py:143-146); `iterate.log_per_iter_threshold` (engine.py:171-175) |
| `subjobs` | never read | - | written by the converter (src/converters/talend_to_v1/converter.py:145). Observed: a contradictory value changed nothing |
| `job_type`, `_validation`, `_warnings`, `_needs_review` | never read | - | converter metadata (src/converters/talend_to_v1/converter.py:139, 155, 170, 172) |

Component-level keys

| Key | Read at | Default | Effect |
|---|---|---|---|
| `id` | engine.py:188 | required (KeyError) | duplicate ids: the last one silently replaces the first (observed) |
| `type` | engine.py:189-194 | required (KeyError) | REGISTRY lookup: 182 names for 86 classes, both `X` and `tX` forms (observed). Unknown type: WARNING, no instance, job goes on (section 9) |
| `config` | engine.py:197 | `{}` | deep-copied to `_original_config` (base_component.py:180). The base itself reads `die_on_error`, `execution_mode`, `chunk_size`, `component_type` (base_component.py:234, 454, 507, 186) |
| `inputs` | engine.py:203; output_router.py:68 | `[]` | flow names consumed; decides what `execute()` receives and in what order (section 3) |
| `outputs` | engine.py:204; output_router.py:69 | `[]` | only use: naming of extra result keys (output_router.py:143-156) |
| `schema.output` | engine.py:206 | `[]` | column order, fill and coercion of `main` (section 8) |
| `schema.reject` | engine.py:207 | `[]` | same for `reject` |
| `schema.input` | engine.py:205 | `[]` | unused by the base; read by sinks and tJavaRow (e.g. components/file/file_output_delimited.py:426) |
| `schema.inputs` | engine.py:212 | `{}` | per-flow input schemas; read by Map, tJavaRow, tJavaFlex (components/transform/map/map_component.py:393-397) |
| `subjob_id` | engine.py:201, 255 | none | if ANY component has one, subjobs come only from these (section 4) |
| `is_subjob_start` | engine.py:202 | False | stored on the instance, never read again |
| `triggers` | engine.py:240-247 | `[]` | keys `type`, `target_component` or `to`, `condition`, `output_id`. Registered with the TriggerManager but not with the ExecutionPlan (engine.py:157), so the target subjob stays "initial" and runs regardless. Observed: a false RunIf declared here still ran its target |
| `original_type`, `position`, `_unsupported`, `schema.outputs` | not read by engine.py | - | - |

- Schema column keys the base reads: `name`, `type`, `nullable`, `precision`, `date_pattern`, `treat_empty_as_null` (base_component.py:1018-1054). `length` and `key` are never read by the base (base_component.py:928-930).
- Flow keys: `name`, `from`, `to` required (output_router.py:73-75, KeyError in the constructor). `type` is defaulted for lookups (output_router.py:93) but indexed directly when routing (output_router.py:124). Observed: a flow with no `type` makes its producer fail with error `'type'` after it has run. `enable_parallel`, `number_parallel` (src/converters/talend_to_v1/converter.py:257-258) are never read.
- Trigger keys: `type`, `from` or `from_component`, `to` or `to_component`, `condition`, `output_id` (engine.py:229-236; execution_plan.py:349-353).

## 2. Context

Groups
- `context = {group: {name: {"value": v, "type": t}}}`. An entry that is not a dict is taken as a plain value with no type (context_manager.py:141-145).
- Only one group is loaded: `initial_context.get(default_context, initial_context)` (context_manager.py:127). If that group is absent, the WHOLE `context` dict is loaded as if flat. Observed: `default_context: "PROD"` with only `Default` defined gives the context `{'Default': None}`; nothing is reported.
- Other groups are read only when the job runs as a tRunJob child (child_job_runner.py:174-197).

Value conversion, at load and on every `set(key, value, type)` (context_manager.py:178-191, 314-345)

| `type` | Converter (context_manager.py:75-101) | Observed |
|---|---|---|
| `str`, `id_String`, `object`, `id_Object` | `str` | 9 -> '9' |
| `int`, `id_Integer`, `id_Long`, `id_Short`, `id_Byte` | `int` | '100' -> 100; '1.5' and '12x' stay str, WARNING |
| `float`, `id_Float`, `id_Double` | `float` | '1.50' -> 1.5 |
| `bool`, `id_Boolean` | `str(v).lower() in ("true", "1", "yes")` | 'TRUE', 'yes', '1' -> True; 'Y' -> False |
| `Decimal`, `id_BigDecimal` | `Decimal` | '1.10' -> Decimal('1.10') |
| `datetime` | `str` (no parsing) | '2024-01-31' stays a str |
| `id_Date` | first match of `%Y-%m-%d %H:%M:%S`, `%Y-%m-%d`, `%m/%d/%Y`, `%d/%m/%Y %H:%M` (context_manager.py:22-44) | datetime.datetime; no match: stays str |
| `id_Character` | first character | 'xyz' -> 'x' |
| anything else | value kept, WARNING (context_manager.py:332-337) | - |

- `None` and `""` are never converted (context_manager.py:329-330).
- A failed conversion keeps the raw value with a WARNING, no error (context_manager.py:339-345).
- The converter writes Python type names and string values (src/converters/talend_to_v1/xml_parser.py:105-115), so a Talend Date context variable arrives as `datetime` and stays a string.

`--context_param`
- `python -m src.v1.engine.engine job.json --context_param KEY=VALUE`, repeatable. Split on the first `=`, both sides stripped; no `=` logs and `sys.exit(1)` (engine.py:351-367). Observed: `python src/v1/engine/engine.py job.json` fails with ImportError (relative imports).
- Applied after construction, before execute, through `ContextManager.set(name, value)` with no type (engine.py:335-338, 291-293). Observed: a declared `int` overridden with `n=250` is the string '250'; undeclared names are accepted.

Resolution passes, per component, inside `execute()`

| Pass | Where | Rule |
|---|---|---|
| 0 | base_component.py:225 | config = deep copy of the pristine config, on every execute |
| 1 validate | base_component.py:228 | `_validate_config()` runs BEFORE resolution and sees `${context.x}` / `{{java}}` text (observed) |
| 2 `{{java}}` | base_component.py:332-333, 339-438 | only if a bridge is attached. Any string that STARTS WITH `{{java}}`, at any depth of dicts and lists (base_component.py:348-358). All context variables and all globalMap entries are pushed to the bridge first (base_component.py:372-384); one batch call; each marked value is replaced by whatever the bridge returns, type included (base_component.py:416, 431). A result starting `{{ERROR}}` raises RuntimeError (base_component.py:405-411) |
| 3 context | base_component.py:336-337; context_manager.py:258-308 | returns a new dict. str -> `resolve_string`; dicts and lists recursed, lists of lists too; other types untouched; dict keys never resolved. Keys `java_code`, `imports`, `python_code`, `code_start`, `code_main`, `code_end` are skipped at any depth (context_manager.py:63-70, 274-276) |

`resolve_string` (context_manager.py:220-256); every line below was observed
- A non-str is returned as is. A string starting with `{{java}}` is returned untouched, so with no bridge it reaches the component as literal text with no warning.
- `\$\{context\.(\w+)\}` then `\bcontext\.(\w+)\b`, each replaced by `str(value)`. The result is ALWAYS a str: `${context.n}` with n=100 gives '100'; a bool gives 'True'; Decimal '1.10'; a datetime '2024-01-31 00:00:00'.
- Unknown name, or a variable whose value is None: the text is left verbatim. No error, no log. An empty-string value substitutes as ''.
- No quoting: `row1.id == context.n` -> `row1.id == 100`; `context.name + '/f.csv'` -> `beta + '/f.csv'`.
- The bare pattern hits any `context.` token: `/data/context.csv` becomes `/data/<value>` when a variable `csv` exists; `my.context.name` matches; `mycontext.name` does not.
- The second pattern re-reads the output of the first: a value that itself holds `context.y` is substituted again.

Timing
- Resolution runs at the start of each `execute()`. Observed: a context value set at run time by an earlier component is seen by later components in the same subjob and in later subjobs; iterate body components re-resolve on every iteration.
- Trigger conditions resolve context when evaluated (trigger_manager.py:347).

Component overrides of this step (code)
- Map and PyMap resolve context only in a few scalar keys and skip the Java pass (components/transform/map/map_component.py:34; components/transform/py_map.py:182).
- RowGenerator makes the Java pass a no-op (components/transform/row_generator.py:188); FilterRows withholds `advanced_cond` (components/transform/filter_rows.py:361); XMLMap strips the marker from `expression_filter` (components/transform/xml_map.py:450).
- The base never resolves `globalMap.get(...)` text. Without `{{java}}` only tDie, tWarn, tFixedFlowInput and tRunJob do it themselves (components/control/die.py:25, components/control/warn.py:24, components/file/fixed_flow_input.py:274, components/control/run_job.py:22).

## 3. Flows

Flow `type` -> result key (output_router.py:22-29)

| `type` | Result key |
|---|---|
| `flow`, `filter`, `unique` | `main` |
| `reject`, `duplicate` | `reject` |
| `iterate` | `iterate`; no component returns that key, so iterate flows carry no data |
| anything else | none; only the flow-name fallback below applies. Observed: `main`, `FLOW`, `bogus` were not routed and their consumers stalled. Matching is case sensitive |

The converter lower-cases the Talend connector name; it accepts FLOW, MAIN, REJECT, FILTER, UNIQUE, DUPLICATE, ITERATE (src/converters/talend_to_v1/converter.py:27-30, 246).

Routing a result dict (output_router.py:102-156), in this order
1. For each outgoing flow, in `flows` order: take result[key for the type]; if that is None and the flow NAME is a key of the result, take that (output_router.py:127-135). Still None: the flow is not written (output_router.py:137-138).
2. Then every result key other than `main`, `reject`, `stats` with a non-None value is stored under its own name if that name is in the component's `outputs`, else under `<comp_id>_<key>` (output_router.py:143-156). This runs last and overwrites step 1 (observed: with both `main` and a key named after the flow, the named key won).
- One store keyed by flow name (output_router.py:96). Two producers writing one name: last writer wins (observed). A frame fanned out to several flows is the SAME object in each, no copy (observed).
- tMap returns one key per output name and no `main` (components/transform/map/map_component.py:387-391); it relies on the name fallback and step 2.
- Nothing is routed for a component that raised (executor.py:728-729, 746).

What a consumer receives (output_router.py:162-181), driven by ITS `inputs` list, not by `flows`

| `len(inputs)` | Argument of `execute()` |
|---|---|
| 0 | None |
| 1 | the stored object itself, a bare DataFrame, or None if absent |
| 2 or more | dict `{flow_name: object or None}` in `inputs` order. Observed: order follows `inputs`, not `flows` order and not execution order |

- An iterate-typed input counts: one iterate input plus one data input gives `{iter: None, row: df}` (observed). `inputs: ["f", "f"]` gives a one-key dict (observed).
- Components depend on the shape. Join takes `inputs[0]` as main and `inputs[1]` as lookup (components/transform/join.py:113-114). Unite returns an empty frame unless it gets a dict (components/transform/unite.py:55); observed: a real Unite with one input flow turned 2 rows into 0, status `success`. Unite concatenates in `inputs` order (observed). FlowToIterate prefixes its globalMap keys with `inputs[0]` (components/iterate/flow_to_iterate.py:198).

Missing and empty inputs
- Ready = every non-iterate input name is a key in the store (output_router.py:196-208). An empty DataFrame is ready and the consumer runs with it (observed).
- Not ready: WARNING and the component is skipped. Not executed, no status, no stats, no triggers (executor.py:344-351).
- At job end, a created component that never executed, is not marked skipped, and sits in an attempted subjob raises `ConfigurationError("Runtime stall detected ...")` (executor.py:153-171); the engine returns it as `status: error` (engine.py:277-289). Files already written stay written.
- So a producer returning None (or no key) for a wired flow stalls the job. Observed with real components: `FileInputDelimited` returns `reject: None` when no row is rejected (components/file/file_input_delimited.py:801, 996, 317). `tests/fixtures/jobs/file/csv_with_reject.json` on a clean file writes main.csv and ends `status: error`; `core/reject_routing.json` with one bad row ends `success`. By code, Join also returns `reject: None` when nothing is rejected (components/transform/join.py:312), and FilterRows does so on empty input (components/transform/filter_rows.py:229).
- Iterate body components are force-marked executed after the loop (executor.py:368-370), so a skipped body component never raises a stall (section 9).
- A flow's data is dropped when its producing subjob ends, unless a consumer outside that subjob has not run yet (executor.py:405-407; output_router.py:224-279). Step-2 names that are not flows are never dropped.

## 4. Execution order

Subjob membership
- If any component has a truthy `subjob_id`: subjobs are the `subjob_id` groups in components-list order (engine.py:251-260). A component without one belongs to no subjob and never runs; observed: no error, `status: success`.
- Otherwise auto-detected: connected components over ALL flows (any type, both directions), BFS from each unvisited component in list order, named `subjob_1..N` (execution_plan.py:255-293). The converter never writes `subjob_id` (no occurrence in `src/converters/talend_to_v1`); only the four hand-written fixtures in `tests/fixtures/jobs/core` carry it.
- The top-level `subjobs` key is not consulted (engine.py:158 builds from components only). Triggers never merge subjobs (execution_plan.py:283-287 follows flows only).

Inside a subjob (execution_plan.py:295-338)
- `graphlib.TopologicalSorter.static_order()` over flows with both ends in the subjob, iterate flows included. Nodes are added in member order, edges in `flows` order.
- The result is layered: first every component with no incoming in-subjob flow, in member order; then each next layer in the order components became ready. Observed: listed `src1, map, src2, log1, log2` runs `src1, src2, map, log1, log2`; a diamond `s->x1->x2->j`, `s->y1->j` runs `s, x1, y1, x2, j`.
- A cycle raises ConfigurationError in the constructor (execution_plan.py:329-332).

Across subjobs
- Initial subjobs = not the target of any top-level trigger of any type (execution_plan.py:184-191), in subjob order (list position of the first member); then subjobs holding a `tPrejob`/`Prejob` component are moved first and `tPostjob`/`Postjob` last (execution_plan.py:168-176, 192-201; observed).
- The queue is drained depth-first (executor.py:222-266). After a subjob, its children = subjobs queued by component-level firing during it (executor.py:257-259) + targets of its OnSubjobOk / OnSubjobError / RunIf edges in `triggers` order (executor.py:260, 845-879), pushed to the FRONT. Observed: root->b1(->b1_child), root->b2 runs `root, b1, b1_child, b2`.
- Each subjob runs at most once per job (executor.py:224-225).
- Subjobs with no trigger between them all run, in list order, even after another one failed (observed).
- The constructor raises "Unreachable subjobs detected" when a subjob is a trigger target, is not reachable from an initial subjob, and is not a RunIf target (execution_plan.py:504-538). Observed to raise: a trigger whose source and target are in the same subjob (when nothing else reaches it), a trigger cycle, a trigger from an unknown id.

Iterate (tFlowToIterate, tFileList, tForeach; type names hard-coded at execution_plan.py:44-48)
- Body = components reachable from the targets of the component's `iterate` flows through outgoing non-iterate flows and outgoing triggers, limited to the same subjob (execution_plan.py:386-425). Nested iterate raises (execution_plan.py:481-498).
- The component's `execute()` only prepares an iterator (base_iterate_component.py:117-196). The executor then runs the body plan once per item, resetting body components and clearing body flows in between (executor.py:463-595); the outer loop skips body components afterwards (executor.py:332-336, 368-370).

Is it deterministic
- Membership, subjob order and in-subjob order: yes, pure functions of the list orders in the config (execution_plan.py:268, 320-325, 188-201 use only lists and dicts).
- Iterate body order: NO when the body has more than one valid order. The body is a set turned into a list before sorting (execution_plan.py:452-453). Observed: four independent body components ran in three different orders under PYTHONHASHSEED=1, 2, 3.

## 5. Triggers

Types, exact strings (trigger_manager.py:70-76): `OnSubjobOk`, `OnSubjobError`, `OnComponentOk`, `OnComponentError`, `RunIf`. Any other value raises ValueError in the constructor (trigger_manager.py:93; observed).

Two firing points
- A, after each component that did not abort its subjob (executor.py:398, 786-826): the manager is asked about EVERY registered trigger, sorted by `output_id` then list order (trigger_manager.py:221-224). A target fires at most once per job on this path (trigger_manager.py:228-233). A fired target in another subjob queues that subjob (executor.py:818-826); a target in the source's own subjob queues nothing.
- B, after the subjob (executor.py:828-881): the top-level trigger edges leaving it, in `triggers` list order, for OnSubjobOk / OnSubjobError / RunIf.
- A queued subjob starts only after the current subjob has finished (executor.py:248-266). Observed: OnComponentOk on the first of two chained components runs its target after the second component.
- Converter side: triggers are written sorted by (`from`, `output_id`), and every trigger leaving a component whose id starts with `tPrejob` is rewritten to OnComponentOk (src/converters/talend_to_v1/trigger_mapper.py:98, 70-72). A missing `output_id` counts as 0 (engine.py:235).

| Type | Fires when | Observed notes |
|---|---|---|
| OnComponentOk | A: the source returned (trigger_manager.py:258-259) | - |
| OnComponentError | A: the source raised (trigger_manager.py:261-262) | A is not reached when the failing component has `die_on_error` true: the `break` (executor.py:381-388) comes before executor.py:398. With the default it NEVER fires |
| OnSubjobOk | A or B: every member of the source subjob has status success (trigger_manager.py:271-288); B also needs subjob result `success` (executor.py:857-859) | fires at A on the last component, so sibling order is by `output_id`, even against an OnComponentOk on that same component: OnSubjobOk (output_id 1) ran before OnComponentOk (output_id 2) |
| OnSubjobError | A or B: any member has status error (trigger_manager.py:290-303; executor.py:861-863) | fires for tolerated failures too |
| RunIf | A: right after its source component; B: again after the subjob (trigger_manager.py:264-267; executor.py:865-867) | runs its target if the condition is true at EITHER time. At B it is evaluated even when the source failed or was skipped |

- OnSubjobOk needs a status for every member (trigger_manager.py:284-288): a subjob holding an unknown-type component never fires it (observed).
- `condition` is ignored for all types but RunIf (trigger_manager.py:252-267). Empty or missing = true (trigger_manager.py:331-332).

RunIf evaluation (trigger_manager.py:309-372): the text is rewritten, then `eval(text, {"__builtins__": {}, None, True, False, int, str, float, bool}, {})` (trigger_manager.py:40-49, 360) and the result goes through `bool()`. There is no `globalMap` or `context` object in that namespace; references are replaced by `repr()` literals first.

| Step | Rewrite |
|---|---|
| 0 (trigger_manager.py:374-417) | `${context.X}` and bare `context.X` -> `repr(value)` when X exists; an unknown X is left as is and fails in eval |
| 1 (trigger_manager.py:419-455) | `((T)globalMap.get("k"))` with T in Integer, Long, Short, Byte (int), Float, Double (float), Boolean (bool), String (str). Missing or None -> `0`, `False`, or the STRING `"None"`. Failed int/float conversion -> `0`. Unknown T -> `repr(raw)` |
| 2 (trigger_manager.py:457-468) | remaining `globalMap.get("k")` or `('k')` -> `repr(value)`, or `None` |
| 3 (trigger_manager.py:470-496) | `&&` -> and, `\|\|` -> or, `!` not followed by `=` -> not, `null` -> None, `true`/`false` -> True/False. Purely textual: it also rewrites inside string literals and inside substituted values |

- Any exception becomes `TriggerEvaluationError` (trigger_manager.py:364-372). The executor does not catch it: the job ends `status: error` and the remaining subjobs do not run (observed).
- The language is Python. Observed to raise: `.equals(...)`, `.length()`, `? :`, `len(...)`, `((Integer) globalMap.get("k"))` with a space, `(Integer)globalMap.get("k")` with single parentheses, a datetime context value.
- Observed traps: `((Boolean)globalMap.get("f"))` with the string 'false' is True; `globalMap.get("k") == 1` with a stored '1' is False while the `(Integer)` cast makes it True; `((String)globalMap.get("missing")) == null` is False.
- The converter rewrites Talend conditions toward this form (src/converters/talend_to_v1/trigger_mapper.py:84). Observed: `((String)globalMap.get("status")).equals("OK")` -> `(globalMap.get('status')) == "OK"`; `"Y".equals(context.RUN_FLAG)` -> `"Y" == ${context.RUN_FLAG}`.

Three real conditions
- `((Integer)globalMap.get("should_run")) == 1` (tests/fixtures/jobs/core/trigger_runif.json:125). tSetGlobalVar stored the string "1"; the cast is what makes it match.
- `globalMap.get('tFileExist_1_EXISTS') == True` (tests/integration/test_file_exist_e2e.py:73).
- `"Customer" in globalMap.get("tFileList_1_CURRENT_FILE")` (tests/v1/engine/test_executor.py:426).

Downstream subjobs after a failure (observed with `Probe`)

| Situation | What happens next |
|---|---|
| a component raises, `die_on_error` true or absent | rest of its subjob marked `skipped`. OnComponentError does not fire. An OnSubjobError target runs. OnSubjobOk targets, and everything behind them, do not run and are not reported. OnComponentOk targets of components that had already succeeded still run. RunIf is still evaluated. Other initial subjobs still run. The postjob subjob is skipped |
| a component raises, `die_on_error` false | the subjob continues. OnComponentError and OnSubjobError targets run; OnSubjobOk does not. Consumers of the failed component are not ready, so the job ends in a stall, `status: error` |
| tDie, or any exception carrying `exit_code` | the job stops at once: no handlers, no later subjobs, no postjob (executor.py:268-270, 400-401) |
| no handler | nothing special: the failed subjob's OnSubjobOk successors silently do not run |

- Postjob: a subjob holding a tPostjob marker is skipped when anything failed or the job was terminated (executor.py:235-243). The code calls this a deliberate divergence from Talend.

Final status and exit code

| `status` | When |
|---|---|
| `success` | no component raised |
| `failed` | at least one component raised, tolerated or not (executor.py:175-176) |
| `error` | terminated by an `exit_code` exception or an iterate set-up failure (executor.py:173-174, 491-494); or any exception escaping the executor, such as a stall or a bad RunIf (engine.py:277-289) |

- `job_aborted` = terminated, or some failed component has `die_on_error` true (executor.py:182-185).
- Process exit code: the CLI logs the stats as JSON and returns (engine.py:370-373). Observed: exit 0 for success, for a failed job, and for tDie with `exit_code: 7`. Observed exit 1: an exception in the constructor (bad trigger type) and a malformed `--context_param`. tDie's code is only recorded, in `component_stats[id]["exit_code"]` and globalMap `JOB_EXIT_CODE` (executor.py:764-768; components/control/die.py:113-118).

## 6. Errors

`die_on_error`
- Base: `True` at construction (base_component.py:192); re-read in `execute()` as `config.get("die_on_error", True)` AFTER validation and resolution (base_component.py:234). Not coerced: the string "false" is truthy (observed). If `_validate_config` or resolution raises, the earlier value stands (True on a first run), so config errors always abort the subjob (observed).
- Iterate components: `bool(config.get("die_on_error", False))` (base_iterate_component.py:177).
- The executor reads the instance attribute (executor.py:378-379). The base uses it to choose raise or reject in schema validation (base_component.py:806-820).
- Components read the key again inside `_process`, with their own default.

| Own default | Where (under `components/`) |
|---|---|
| False | file/file_input_delimited.py:173, file/file_input_excel.py:223, file/file_input_xml.py:127, file/file_input_msxml.py:99, file/file_input_raw.py:121, file/file_input_positional.py:107, transform/extract_delimited_fields.py:98, transform/extract_json_fields.py:124, transform/extract_xml_fields.py:97, transform/extract_positional_fields.py:97, context/context_load.py:310, database/oracle_output.py:1139, database/oracle_bulk_exec.py:412 |
| True | file/file_input_json.py:211, file/file_output_excel.py:123, transform/extract_regex_fields.py:86, transform/join.py:323, transform/unpivot_row.py:100, transform/xml_map.py:444, transform/map/map_config.py:168, transform/swift_transformer.py:456, transform/swift_block_formatter.py:244, control/send_mail.py:189 |
| the base value | file/file_copy.py:193, file/set_global_var.py:184, file/file_touch.py:104, transform/python_row_component.py:329, transform/py_map.py:514 |

- With the key absent, a file input tolerates its own row errors (False) while the engine treats any exception it lets out as fatal (True). In the 37 converted samples the key is absent for most types; FileInputDelimited carries `false` in 27 of 31.

When a component raises (executor.py:746-780)
- `BaseComponent.execute` lets `ConfigurationError` through and wraps anything else as `ComponentExecutionError(id, str(e), cause=e)` (base_component.py:268-274).
- The executor catches `Exception`. If the error, its `.cause` or its `__cause__` has an `exit_code` attribute, the job is terminated (executor.py:752-770). Otherwise: trigger status `error`; the id goes into `failed_components` AND `executed_components`; `execution_stats[id] = {"status": "error", "error": str(e)}` (executor.py:773-780).
- Nothing is routed. The base's counters are not written for it (those steps follow `_process`, base_component.py:253-254). The engine writes no `<id>_ERROR_MESSAGE`; a few components do (components/transform/join.py:321).
- Then the table in section 5 applies.

Hierarchy (exceptions.py:9-60): `ETLError` is the root of `ConfigurationError`, `DataValidationError`, `ComponentExecutionError(component_id, message, cause)`, `FileOperationError`, `JavaBridgeError`, `ExpressionError`, `TriggerEvaluationError(trigger_type, condition, message, cause)`, `SchemaError`. `exit_code` is not a class: tDie and tRunJob set it as an attribute on a `ComponentExecutionError` (components/control/die.py:131; components/control/run_job.py:74).

What the caller gets
- The constructor can raise: KeyError (component without `id` or `type`), ValueError (trigger type), ConfigurationError (cycle, unreachable subjob, nested iterate), JavaBridgeError. It releases the managers first (engine.py:181-183).
- `ETLEngine.execute()` catches every `Exception` (engine.py:277) and returns a dict. Normal return (executor.py:187-194; engine.py:269-270): `status`, `execution_time`, `components_executed`, `components_failed`, `component_stats`, `job_aborted`, `job_name`, `global_map`. After an escaping exception (engine.py:281-289): `job_name`, `status: "error"`, `error`, `execution_time: 0`, `components_executed`, `components_failed`, `component_stats`; no `job_aborted`, no `global_map`.
- `components_executed` also counts failed components and iterate body components that never ran (executor.py:763, 775, 368-370).
- `component_stats[id]`: the stats plus `execution_time` on success; `{"status": "error", "error"[, "exit_code"]}` on failure; `{"status": "skipped"}` for the rest of an aborted subjob and for a skipped postjob marker; absent for components never reached.
- The returned `global_map` is only the per-component counters (global_map.py:96-98), not the full map. `get_execution_stats()` has the full map and the context (engine.py:299-308).
- `execute()` always shuts down the bridge and DB managers (engine.py:273, 279).

## 7. globalMap and stats

- `GlobalMap` is a flat dict; `get(key, default=None)` (global_map.py:21-28). `put_component_stat(id, name, v)` writes `_component_stats[id][name]` and `_map["<id>_<name>"]` (global_map.py:40-49).
- The base writes every key of `self.stats` once per successful `execute()`, after `_process` and the schema steps (base_component.py:253-254, 615-619). Nothing is written when the component raises (observed).

Values (base_component.py:560-597; observed)

| Key | Value |
|---|---|
| `<id>_NB_LINE` | rows of the input; for a dict input the SUM over all inputs (base_component.py:545-558). If that is 0 (sources): main rows + reject rows |
| `<id>_NB_LINE_OK` | rows of `main` (0 if None, empty or not a DataFrame) |
| `<id>_NB_LINE_REJECT` | rows of `reject` |

- Counted after the base's schema step, so rows the base itself moved to reject are included.
- Other result keys are not counted: a component returning only named outputs reports 0.
- A component that calls `_update_stats()` inside `_process` owns its numbers (base_component.py:574-576, 599-613). Map and PyMap replace the derivation: NB_LINE = total rows over all outputs (components/transform/map/map_component.py:60-75).
- Counters accumulate across `execute()` calls on one instance until `reset()` (observed: 3, then 6). `reset()` zeroes the instance counters but not globalMap (base_component.py:1309-1323).

Iterate
- Per item, before the body runs: the component's own keys (`<id>_CURRENT_VALUE`, `<flow>.<column>`, ...) and `<id>_CURRENT_ITERATION`, 1-based (base_iterate_component.py:325-332).
- After the loop: `<id>_NB_LINE` = items attempted, `_NB_LINE_OK` = items whose body succeeded, `_NB_LINE_REJECT` = items whose body failed, plus `<id>_total_iter_time`, `_avg_iter_time`, `_slowest_iter_time`, `_fastest_iter_time`, `_slowest_iter_index`, `_fastest_iter_index` (executor.py:618-635).
- Observed: `component_stats[<iterate id>]` stays all zero, because the snapshot is taken before the loop (executor.py:732-734), while globalMap has the counts. Body components are reset per item (executor.py:586-590), so their globalMap counters and `component_stats` hold the LAST iteration only: 3 iterations of 2 rows report NB_LINE 2.

Other writers: tDie puts `<id>_MESSAGE`, `_CODE`, `_PRIORITY`, `_EXIT_CODE`, `JOB_ERROR_MESSAGE`, `JOB_EXIT_CODE` (components/control/die.py:113-118). Many components put their own keys inside `_process`, e.g. `<id>_FILENAME` (components/file/file_input_delimited.py:192).

Readers
- RunIf: text substitution (section 5).
- `{{java}}` values and Java components: the whole map is copied to the bridge before each evaluation (base_component.py:378-384). tJava and tJavaRow copy the bridge's context and globalMap back afterwards (components/transform/java_component.py:214, 217).
- Python code components get the live `GlobalMap` object as `globalMap` (components/transform/python_component.py:161; components/transform/python_row_component.py:215).
- There is no engine-level substitution of `globalMap.get(...)` in config strings: the base has only the two passes of section 2 (base_component.py:319-337).

## 8. The base component's execute()

| # | base_component.py | Step |
|---|---|---|
| 1 | 219-220 | status RUNNING; clear the "stats set by component" flag |
| 2 | 225 | `config = deepcopy(_original_config)` |
| 3 | 228 | `_validate_config()` on the unresolved config |
| 4 | 231 | `_resolve_expressions()` (section 2) |
| 5 | 234 | read `die_on_error` |
| 6 | 237 | count input rows |
| 7 | 240 | `_select_mode()` |
| 8 | 243-246 | streaming: `_execute_streaming()`; otherwise `_process(input)` |
| 9 | 248 | batch only: `_enforce_schema_column_order()` |
| 10 | 250 | batch only: `_apply_output_schema_validation()` |
| 11 | 253-254 | derive counters; push them to globalMap |
| 12 | 256-266 | status SUCCESS; `result["stats"] = copy`; return the result |

Iterate components replace the whole method (base_iterate_component.py:117-204): steps 2-5, then `prepare()` and `prepare_iterations()`; no `_process`, no schema steps, no counters. They return `{"main": None, "reject": None, "stats"}`.

Execution mode (base_component.py:444-475)
- `config.execution_mode` is exactly `"batch"` or `"streaming"`; any other value (default `"hybrid"`) means batch, unless the input is one DataFrame of more than 5120 MB deep memory (base_component.py:146, 464-473). A dict input never streams in hybrid.
- The converter never writes `execution_mode` or `chunk_size`, and none of the 62 sample configs has them. Map, PyMap and PivotToColumnsDelimited force batch (components/transform/map/map_component.py:51; components/transform/py_map.py:197; components/transform/pivot_to_columns_delimited.py:95).
- Streaming (base_component.py:488-534) calls `_process` once per `chunk_size` rows (default 10000), runs steps 9-10 per chunk, then concatenates per key.
- It changes results (observed). A row-counting stub returned 3 rows (10, 10, 5) instead of 1 (25). A key whose chunks are all empty becomes None instead of an empty frame, so a wired consumer stalls. A 0-row input never calls `_process` and yields a frame with no columns. A dict input fails with `'dict' object has no attribute 'iloc'`. A source (input None) skips steps 9-10 entirely.
- The plan's `requires_full_data` flag is computed and never consulted (execution_plan.py:32-37, 204-212).

Step 9, column order and fill (base_component.py:625-775). Only when the schema is non-empty and the value is a DataFrame.
- Schema columns missing from the frame are CREATED. Nullable: NA, NaN or NaT. Non-nullable: 0, 0.0, False, "", 1970-01-01, Decimal("0") (base_component.py:723-775).
- Order = schema columns in schema order, then the extra columns, which are kept (base_component.py:676-683).
- Names match exactly. Observed: schema `id` with data `ID` gives a new `id` column of 0 and keeps `ID`.
- Same for `reject` against `schema.reject` (base_component.py:686-718).

Step 10 (base_component.py:781-835)
- First, on `main` only, even with no schema: columns `errorCode` and `errorMessage` are renamed `errorCode_user` and `errorMessage_user` (base_component.py:804, 837-869).
- `main` against `schema.output`: `die_on_error` true -> `validate_schema`, which raises; false -> `_validate_with_reject_routing` (base_component.py:809-820).
- `reject` against `schema.reject` with every column forced nullable (base_component.py:824-833).

Per column, in schema order, for columns present (base_component.py:1017-1054)
1. `treat_empty_as_null`: default True for int, float, bool, datetime, Decimal and False for str (base_component.py:91, 1026-1027). str + True: "" -> NA. Non-str + False with a "" present: DataValidationError, even when `die_on_error` is false (observed).
2. Null check on the values as they are NOW, before coercion (base_component.py:1031-1034).
3. Coercion (base_component.py:1177-1261). Any exception inside it is logged as a WARNING and the column is left as it was at that point (base_component.py:1255-1259).
4. `precision`: Decimal -> quantize; float -> round. Unused for other types (base_component.py:1040-1054).
- `nullable` has two effects only: the null check of step 2 when false, and the int target dtype (`Int64` or `int64`). Coercion of the other types ignores it.

Coercion per schema type. "Observed" used object-dtype input on pandas 3.0.5.

| Type | Code | Observed |
|---|---|---|
| `str` | none (base_component.py:1253) | ints, floats and bools pass through unchanged; `length` is never applied |
| `int` | `pd.to_numeric(errors="coerce")`, then `astype(Int64)` if nullable else `astype("int64")` (base_component.py:1219-1226) | '1', '2.0', ' 7 ', '1e3' -> 1, 2, 7, 1000; True -> 1. Nullable: 'abc' and '' -> NA; one '2.5' makes the cast fail and the whole column stays float64. Non-nullable: 'abc' or '' leaves the column float64 with NaN, WARNING only; '2.5' and 3.9 -> 2 and 3 (truncated) |
| `float` | `pd.to_numeric(errors="coerce")` (base_component.py:1228-1229) | 'abc', '', '1,5' -> NaN; 'inf' -> inf; all-integer text gives dtype int64 |
| `bool` | `astype("bool")` (base_component.py:1231-1232) | 'true', 'false', '0', 'N' -> True; '' -> False; None -> False; NaN -> True |
| `datetime` | `_parse_datetime_column` (base_component.py:1264-1303) | dtype datetime64[us]; see below |
| `Decimal` | per value `Decimal(str(v))`; None/NaN -> NA; unparsable values kept (base_component.py:1234-1251) | 'abc' and '' stay in the column as str, silently |
| anything else (`object`, `id_*`, `string`) | none (base_component.py:1211, 1253) | unchanged |

`date_pattern` and datetime
- With a pattern: the Java tokens yyyy, yy, MM, dd, HH, hh, mm, ss, SSS are replaced textually (base_component.py:71-81, 97-112), then `pd.to_datetime(format=..., errors="coerce")`. It is accepted when at least one value parsed (base_component.py:1283-1288); the other values become NaT.
- The converter already stores strptime text such as `%Y-%m-%d` (src/converters/talend_to_v1/components/base.py:188); the token replace leaves that unchanged (observed).
- Pattern matched nothing, or no pattern: try `%Y-%m-%d %H:%M:%S`, `%Y-%m-%d`, `%d/%m/%Y`; a format wins only when ALL non-empty values parse (base_component.py:84-88, 1291-1299); else `pd.to_datetime(errors="coerce")` inference (base_component.py:1302).
- Observed: '01/02/2024' is 1 Feb when the column fits dd/MM/yyyy, and 2 Jan when another value ('12/31/2024') forces inference. Mixed formats: the first value's format wins and the rest are NaT. Unsupported tokens (`MMM`, a quoted `'T'`) fall through to inference.

`precision`
- Decimal: `quantize(10 ** -int(precision), ROUND_HALF_UP)` (base_component.py:1131-1175). Observed: precision 2 turns 1.005 into 1.01 and '1' into 1.00; 0 gives an integer; -1 turned 1234.567 into 1235. The converter writes `precision` whenever it is >= 0 (src/converters/talend_to_v1/components/base.py:185); the samples have Decimal columns with precision 0.
- float: `Series.round(int(precision))` (base_component.py:1046-1049). Observed for 2: 1.005 -> 1.0, 2.675 -> 2.68, 1.115 -> 1.12, 0.125 -> 0.12.

Rows that fail

| Case | `die_on_error` true | `die_on_error` false |
|---|---|---|
| null in a non-nullable column, present before coercion | DataValidationError; the component fails | row removed from main and appended to reject with its original values, `errorCode = "SCHEMA_VIOLATION"`, `errorMessage = "Column 'c': non-nullable column has null"` (base_component.py:911-918, 958-974) |
| value that cannot be coerced | stays in main as NaN, NaT or the raw text | same; never rejected. The "type coercion failed" reason in the docstring has no code path (base_component.py:886 against 897-944) |

- Observed side effect of the false path: coercion runs on the whole column before the split, so one bad or null value leaves the surviving int rows as float64.

## 9. Surprises

Iterate
1. OnSubjobOk on a subjob that contains an iterate loop fires at the end of the first clean iteration, and its target runs between items 1 and 2. Mechanism: the iterate component already has status success (executor.py:737), body components fire triggers per iteration (executor.py:398), and queued subjobs are drained inside the loop (executor.py:598-601). Observed with real components: tForeach of 3 values appending 2 rows each, OnSubjobOk to a copy subjob: the appended file ends with 6 rows, the copy has 2.
2. A subjob triggered from an iterate body runs at most once per job, on the first iteration whose trigger fires (trigger_manager.py:228-229; executor.py:224-225). With auto-detected subjobs a trigger target that is not flow-connected to the loop is in another subjob, so it is never part of the body (execution_plan.py:412-413). Observed: OnComponentOk and RunIf targets of a body component each ran once in 3 iterations.
3. A lookup feeding a body component from outside the iterate link is not in the body. It runs once. If it comes AFTER the iterate component in the subjob order (section 4; observed with the lookup listed after it) it has not run when the loop starts: the body consumers are skipped on every iteration, then marked executed, and the job reports `success` (executor.py:344-351, 368-370). Listed before it, the same job works (observed).
4. Body order varies between processes (section 4).
5. A body failure with `die_on_error` true lets both OnSubjobOk (from an earlier clean iteration) and OnSubjobError targets run (observed). The outer subjob result never reflects body failures (executor.py:357-374).

Flow and failure
6. A wired flow whose producer returns None stalls the job: `status: error` after the other outputs were written. FileInputDelimited with a reject link and zero rejected rows does exactly this (section 3).
7. `die_on_error: false` on a component that raises and has a consumer also ends in a stall `error`, not in `failed` (observed).
8. OnComponentError never fires with the default `die_on_error` (section 5).
9. RunIf is evaluated twice and fires from failed or skipped sources; a condition that raises kills the job (section 5).
10. Unknown component type: a WARNING only. Its consumers stall; its subjob's OnSubjobOk never fires (observed).
11. tDie stops everything, error handlers and postjob included; the postjob subjob is also skipped after any ordinary failure (section 5).
12. The process exit code is 0 whatever the status (section 5).

Config and context
13. `subjobs` is ignored; a partial `subjob_id` silently drops components (section 4).
14. Context substitution is text. Typed values arrive as strings (`"100"`), unquoted, and any `context.<name>` token in any string is a candidate, file paths included (section 2).
15. `--context_param` values are untyped strings (section 2).
16. A wrong `default_context` loads nothing useful and says nothing (section 2).
17. `_validate_config` sees unresolved text; `die_on_error` is read after resolution and is not coerced (sections 2, 6).
18. The single-input argument is a bare DataFrame, the multi-input one a dict; a real Unite with one input drops every row (section 3).

Schema
19. `nullable: false` is checked before coercion, so text that fails to parse ends as NaN or NaT in a non-nullable column: a WARNING for int, nothing at all for float and datetime (observed; section 8).
20. `bool` turns every non-empty string, 'false' included, into True (section 8).
21. A reject flow that passes through any component as its `main` gets its columns renamed. Observed with real components: reject -> tLogRow -> file writes the header `id;errorCode_user;errorMessage_user;name;amount`; the same reject written directly keeps `errorCode;errorMessage`.
22. Missing schema columns are invented with zero-like values, and a case-different name counts as missing (section 8).
23. The same date text can parse day-first or month-first depending on the other values in its column (section 8).
24. `precision: 0` on a Decimal column rounds to integers (section 8).

Stats
25. Counters of iterate body components are last-iteration values; `component_stats` of the iterate component is zero (section 7).
26. NB_LINE of a multi-input component is the sum of all its inputs, lookups included, unless the component overrides it (section 7).
27. The `global_map` in the engine's return value is not the globalMap (section 6).

Described where they belong
28. Component-level `triggers` do not gate anything (section 1). Flow `type` values outside the six known ones are not routed (section 3). A `{{java}}` value with no bridge is passed on as literal text (section 2). OnSubjobOk and OnComponentOk siblings order by `output_id` (section 5). `execution_mode: streaming` changes results (section 8).
