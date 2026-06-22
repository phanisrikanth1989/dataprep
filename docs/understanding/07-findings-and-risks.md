# Findings, Risks & Improvement Opportunities

This document aggregates every finding reported by the fleet of code readers into a
single prioritized register. It is the actionable punch-list for engineers extending
the DataPrep codebase and driving each module to the 95% per-module coverage floor.

Findings are grouped first by **severity** (high / medium / low), then by **type**
(bug / risk / smell / improvement). A separate **Strengths to Preserve** section
collects the `good` findings (design decisions worth protecting during refactors),
and a final **Open Questions** section gathers the unresolved questions raised across
all subsystems.

The most load-bearing high-severity claims (TriggerManager class-scoping bug,
engine.py SyntaxError, oracle_output identifier bugs, expression_converter `convert()`
corruption, swift_transformer `__import__` exposure) were re-verified against current
source while preparing this register; they are real as described.

## How to read this register

- **Severity** = impact if the issue fires (high = breaks a subsystem / RCE / data
  loss; medium = wrong results or fragility in realistic cases; low = cosmetic,
  perf, or edge-case).
- **Type** = `bug` (incorrect behavior), `risk` (latent / security / parity hazard),
  `smell` (maintainability), `improvement` (suggested enhancement), `good`
  (strength to preserve).
- File references use repo-relative paths; line numbers reflect the readers' notes
  and may drift as the tree changes. Where a reader's line number was found to be
  stale during verification, the issue itself was still confirmed.

## Severity counts (excluding `good`)

| Severity | bug | risk | smell | improvement | Total |
|----------|----:|-----:|------:|------------:|------:|
| High     |  5  |  4   |  1    |     0       |  10   |
| Medium   |  9  |  6   |  8    |     2       |  25   |
| Low      |  6  |  6   |  21   |     8       |  41   |

There are also 25 `good` findings catalogued under Strengths to Preserve.

---

## HIGH severity

These break a subsystem at import/runtime, lose data silently, or open a remote-code-execution
surface. Several are mutually entangled around one commit (`0ad1ee0`) and the Oracle
identifier refactor (`bafc8e7`) and should be fixed together.

### HIGH - bugs

#### H-B1. `engine.py:225-226` - SyntaxError blocks the entire engine package from importing
- **File:** `src/v1/engine/engine.py:225-226`
- **What:** The `add_trigger()` call is missing a comma after `trigger.get('condition')`
  before `output_id=...`. `import src.v1.engine` raises
  `SyntaxError: invalid syntax. Perhaps you forgot a comma?`.
- **Why it matters:** This is a hard SyntaxError. Nothing in `src.v1.engine` can be
  imported, so the engine, the API layer (which imports `ETLEngine`), and any pytest
  run whose conftest touches the engine fail at collection. It also masks other
  breakage (e.g. the oracle_output bugs below) because CI never gets past collection.
  Introduced by commit `0ad1ee0` (output_id enhancement). **Verified in source.**

#### H-B2. `trigger_manager.py:142` - class-scoping bug makes the entire trigger subsystem non-functional
- **File:** `src/v1/engine/trigger_manager.py:142`
- **What:** `add_trigger` is defined at module level (indent 0) instead of inside
  `TriggerManager`. Because `register_subjob`, `set_component_status`,
  `get_triggered_components`, `should_fire_trigger`, `_check_subjob_ok`,
  `_check_subjob_error`, `_evaluate_condition`, and `reset` are all indented under it,
  they become local closures of the module-level `add_trigger`. AST confirms
  `TriggerManager` has only `__init__` as a method.
- **Why it matters:** Every Executor call such as `self.trigger_manager.set_component_status(...)`
  / `get_triggered_components(...)` / `should_fire_trigger(...)`
  (`executor.py:329,692,716,728,767,855`) raises `AttributeError`. OnSubjobOk /
  OnComponentOk / RunIf flow control is entirely broken. `test_trigger_manager.py:246`
  would fail. A critical Talend-parity break. Introduced by `0ad1ee0`. Fix: re-indent
  line 142+ to 4 spaces (method body to 8). **Verified in source.**

#### H-B3. `oracle_output.py:132` - `NameError: IDENTIFIER_RE` on every DDL/DML path
- **File:** `src/v1/engine/components/database/oracle_output.py:132`
- **What:** Line 71 defines `_IDENTIFIER_RE`; line 132 calls `IDENTIFIER_RE.match(name)`
  (missing underscore). `_quote_ident` is invoked by every CREATE/INSERT/UPDATE/DELETE/SELECT
  builder.
- **Why it matters:** Any tOracleOutput execution raises `NameError: name 'IDENTIFIER_RE'
  is not defined` - the component is completely broken. Introduced by commit `bafc8e7`
  ("Refactor Oracle identifier handling ... preventing ORA-00942"). **Verified in source.**

#### H-B4. `oracle_output.py:252` - method renamed to `qualified_table()` but all call sites use `self._qualified_table()`
- **File:** `src/v1/engine/components/database/oracle_output.py:252`
- **What:** The definition at line 252 is `def qualified_table`, but 13 call sites
  (lines 321, 358, 367, 384, 388, 396, 476, 506, 525, 556, 569, 1081) call
  `self._qualified_table()`. Unit tests also call `_qualified_table()`.
- **Why it matters:** `AttributeError` throughout tOracleOutput. Compounds H-B3 - the
  component cannot run at all. **Verified in source.**

#### H-B5. `oracle_output.py:283-286` - `qualified_table()` references undefined local `schema` and a module function as a method, reads wrong config key
- **File:** `src/v1/engine/components/database/oracle_output.py:283-286` (also 278-279)
- **What:** Lines 283/285/286 use `schema`, which is never assigned (only `table` is, at
  line 278). Line 278 calls `self._quote_ident(...)` but `_quote_ident` is module-level
  (not a method) -> `AttributeError`. Line 279 reads
  `self.config.get('table') or self.config.get('dbschema')`, but the converter emits
  `schema_db` for schema and `table` for table, so schema qualification is dropped and
  the wrong fallback key is consulted.
- **Why it matters:** Even after H-B3/H-B4 are fixed, schema-qualified table names are
  computed incorrectly. **Verified in source** (call sites use `self._quote_ident`,
  `qualified_table` definition references `schema`).

### HIGH - risks

#### H-R1. `swift_transformer.py:721-741` - `__import__` exposed inside `eval` enables arbitrary code execution from config
- **File:** `src/v1/engine/components/transform/swift_transformer.py:721-741`
- **What:** `_evaluate_python_expression` builds an `eval_context` whose
  `__builtins__['__import__'] = __import__` (line 722), then `eval(expression, eval_context)`
  (line 741). A crafted YAML/JSON `transform_config` `python_expression` can run
  `__import__('os').system(...)`. Config files load from context-resolved paths and are
  not in `SKIP_RESOLUTION_KEYS`.
- **Why it matters:** Directly contradicts the locked-down `_code_component_mixin` / PyMap
  namespaces (which deliberately omit `__import__`). Reuse `_build_safe_builtins()` from
  the mixin. **Verified in source** (`__import__` and `eval` present at those lines).

#### H-R2. `python_routines.py` (POST/PUT) - unauthenticated arbitrary `.py` write that the engine imports and `exec`s (RCE by design)
- **File:** `api/routes/python_routines.py`
- **What:** POST/PUT write arbitrary `.py` source into `src/python_routines/`, which
  `PythonRoutineManager` imports and `python_component` `exec`s.
- **Why it matters:** With no auth (H-R4), an attacker writes a routine file then triggers
  a job that imports/executes it - remote code execution.

#### H-R3. `jobs.py:97,199,208-211` - path traversal on `job_id`/`run_id` -> arbitrary file load -> effective RCE
- **File:** `api/routes/jobs.py:97,199,208-211`
- **What:** `job_path = JOBS_DIR / f'{job_id}.json'` is built from the raw URL string with
  no UUID validation, so `..`-style ids let get/delete/run reach arbitrary `*.json`.
- **Why it matters:** Combined with the engine loading arbitrary Java JARs and Python
  routine dirs from job config, `run_job` on an attacker-reachable file is effectively RCE.

#### H-R4. `api/app.py` - no authentication/authorization on any endpoint; open CORS with credentials
- **File:** `api/app.py`
- **What:** No auth on any route; `allow_origins=['*']` with `allow_credentials=True`.
  `POST /run-inline` executes an arbitrary `job_config` dict with no persistence or check
  (`jobs.py:127`).
- **Why it matters:** Any reachable client can upload+execute job configs that load JARs
  and import Python routine modules. The whole HTTP surface is the amplifier for H-R1/H-R2/H-R3.
  The API reads as a trusted single-user dev tool, not production-ready (see Open Questions).

### HIGH - smell

#### H-S1. `tests/v1/engine/components/database/test_oracle_output.py` - tests assert the OLD quoted-identifier behavior, so the component ships effectively untested/red
- **File:** `tests/v1/engine/components/database/test_oracle_output.py`
- **What:** Tests assert `_quote_ident('emp_id') == '"emp_id"'` and
  `comp._qualified_table() == '"HR"."EMP"'` (quoted), while the `bafc8e7` refactor intends
  unquoted emission and renamed the method. Combined with H-B3/H-B4/H-B5, no oracle_output
  test can currently pass.
- **Why it matters:** The DDL/DML path has no green coverage. The pre-existing SyntaxError
  (H-B1) additionally blocks pytest collection, masking the breakage in any CI run that only
  checks collection. Resolve the quoted-vs-unquoted contract (see Open Questions) and realign
  tests in the same change.

---

## MEDIUM severity

Wrong results or fragility in realistic jobs, parity divergences, or maintainability
problems with real blast radius.

### MEDIUM - bugs

#### M-B1. `expression_converter.py` - `convert()` corrupts surviving `!=` comparisons in RunIf conditions
- **File:** `src/converters/talend_to_v1/expression_converter.py` (null-check `re.sub` at
  ~285-286; blanket `expression.replace('!', ' not ')` at ~293; JSON cited 205-206 / 212)
- **What:** After the null-check regexes handle `!= null`, the blanket
  `replace('!', ' not ')` rewrites any remaining inequality like `a != b` into
  `a  not = b`, which is invalid Python. This path feeds RunIf trigger conditions
  (`trigger_mapper.py:83`).
- **Why it matters:** Non-null inequality conditions in RunIf triggers convert to broken
  expressions - silently wrong trigger semantics. **Verified in source.**

#### M-B2. `expression_converter.py` - `detect_java_expression` treats `-` as a Java operator, mismarking hyphenated literals as `{{java}}`
- **File:** `src/converters/talend_to_v1/expression_converter.py`
- **What:** Any hyphenated string not matching the specific 2-segment pattern
  `^[a-zA-Z0-9]+-[a-zA-Z0-9-]+$` is marked `{{java}}` (e.g. `_id-foo`, `a.b-c`).
- **Why it matters:** False `{{java}}` markers force unnecessary Java-bridge round-trips and
  can fail if the literal is not valid Java. Aggressive-by-design but warrants a carve-out.

#### M-B3. `base.py` - `_convert_date_pattern` token table is incomplete, producing corrupt strftime
- **File:** `src/converters/talend_to_v1/components/base.py`
- **What:** `_DATE_TOKENS` lacks `MMM/MMMM` (month name), `EEE/EEEE` (day name), standalone
  `D/u/z/Z/G`, and single `d/M`. Verified: `'EEE, d MMM yyyy'` -> `'EEE, d %mM %Y'` (MMM
  half-matched to `%m` leaving stray `M`; `EEE` and single `d` left literal).
- **Why it matters:** Any schema column with a textual or single-letter Java date pattern
  silently yields a wrong/garbage Python pattern. (Related low-severity: `SSS` -> `%f` maps
  milliseconds to microseconds - off by 1000x in width.)

#### M-B4. `file_input_delimited.py` - stride-based TABLE parsers silently drop a whole row on a missing/reordered field
- **File:** `src/converters/talend_to_v1/components/file/file_input_delimited.py`
- **What:** `_parse_trim_select`/`_parse_decode_cols` (and stride parsers in positional /
  msxml / output_positional / output_xml) assume exactly N consecutive entries per row; a
  missing field shifts all subsequent rows and `break` discards a valid trailing group.
- **Why it matters:** Real risk for hand-edited or sparse `.item` TABLEs. Accumulator-style
  parsers elsewhere are robust to this; the two idioms should be unified (see M-S1).

#### M-B5. `join.py` (converter) - tJoin `needs_review` entries are factually wrong about engine key casing
- **File:** `src/converters/talend_to_v1/components/transform/join.py:144-148`
- **What:** The entries claim the engine reads UPPERCASE `USE_INNER_JOIN`/`JOIN_KEY` and
  `{main,lookup}` config keys, but engine `join.py` reads lowercase
  `use_inner_join`/`join_key` with `{input_column,lookup_column}` - exactly what the converter
  emits. The `main`/`lookup` keys in the engine refer to the input DataFrame dict, not the
  join_key structure.
- **Why it matters:** These describe a parity gap that does not exist and would mislead
  reviewers. Only the `use_lookup_cols`/`lookup_cols` entries are accurate. Delete/correct
  the four bogus entries.

#### M-B6. `aggregate_row.py` (engine) - global (no-group-by) `first`/`last` aggregation crashes with AttributeError
- **File:** `src/v1/engine/components/aggregate/aggregate_row.py:476-477`
- **What:** `_build_agg_func` returns the string `"first"`/`"last"`; `_global_aggregation`
  calls `getattr(df[in_col], "first")()`, but a pandas Series has no `.first()`/`.last()`.
  Verified on pandas 3.0.1. The grouped path is fine (GroupBy.first/last exist).
- **Why it matters:** Ungrouped tAggregateRow with a first/last operation raises
  `AttributeError`. Fix: special-case first/last in `_global_aggregation`
  (e.g. `series.iloc[0]` / `series.dropna().iloc[0]`).

#### M-B7. `flow_to_iterate.py` (engine) - incomplete `pd.NA -> None` coercion leaks `NaN` to globalMap/Java bridge
- **File:** `src/v1/engine/components/iterate/flow_to_iterate.py:201,216`
- **What:** `set_iteration_globalmap` uses `None if value is pd.NA else value`, an identity
  check against the `pd.NA` singleton. But `to_dict('records')` on float64/object columns
  yields `float('nan')`, not `pd.NA` (only Int64/boolean/string extension dtypes produce
  `pd.NA`). So the common null case pushes bare `NaN` to globalMap. Fix: use `pd.isna(value)`.
- **Why it matters:** Defeats the documented null-handling fix and sends `NaN` to the Java
  bridge instead of `None`.

#### M-B8. `convert_type.py` (engine) - MANUALTABLE coercion to a renamed column leaves the original column in the output
- **File:** `src/v1/engine/components/transform/convert_type.py:196-200`
- **What:** When `in_col != out_col`, the coerced value is written to `df.loc[idx, out_col]`
  and the original column is left in place. Column projection is delegated entirely to
  downstream schema validation.
- **Why it matters:** If `output_schema` does not list `in_col`, the stale source column
  leaks downstream. Talend tConvertType maps input->output names and does not retain the
  source under its original name.

#### M-B9. `oracle_output.py` (engine) - upsert PK SELECT does not chunk to Oracle's 1000-item IN limit (ORA-01795)
- **File:** `src/v1/engine/components/database/oracle_output.py`
- **What:** For single-PK upsert, `WHERE pk IN (:1..:N)` with N up to `batch_size`
  (default 10000) exceeds Oracle's 1000-expression IN-list limit. The composite-PK OR-chain
  avoids the limit but generates very large SQL.
- **Why it matters:** Single-PK upsert with batches > 1000 keys raises ORA-01795. Sub-chunk
  the PK SELECT to <= 1000.

#### M-B10. `mssql_input.py` (engine) - `set_query_timeout` mutates a shared connection's timeout and never restores it
- **File:** `src/v1/engine/components/database/mssql_input.py:89`
- **What:** Sets `conn.timeout` when `use_existing_connection=True` and `owns_connection=False`.
  pyodbc timeout is connection-scoped, so a later tMSSqlInput on the same shared connection
  inherits the prior component's timeout.
- **Why it matters:** Cross-component timeout leakage. Save/restore around the cursor, or apply
  per-cursor.

#### M-B11. `aggregate_row.py` (converter) - inaccurate `union` parity warning contradicts the map and an in-file comment
- **File:** `src/converters/talend_to_v1/components/aggregate/aggregate_row.py:76-80`
- **What:** `_normalise_function` maps `union -> union` (passthrough), but the emitted warning
  says "no engine equivalent ... will fall back to sum"; the comment at line 279 says union is
  "now implemented in engine". The converter never produces `sum`.
- **Why it matters:** The warning misleads operators about both the gap and the actual fallback.
  Reconcile the map, the warning text, and the comment.

#### M-B12. `pagination.py` (engine) - non-numeric amount/balance raises uncaught `decimal.InvalidOperation`, aborting the whole job
- **File:** `src/v1/engine/components/transform/pagination.py:300,454` (and `_compute_page_balances`)
- **What:** `_to_decimal_amount` does `Decimal(text)` and `_stage2_aggregate` does
  `Decimal(ob_str)` with no try/except; `Pagination._process` has no wrapper. Any bad cell
  aborts the job (wrapped as `ComponentExecutionError`) regardless of `die_on_error`.
- **Why it matters:** A SWIFT/statement feed with one dirty value crashes a 1:1 broadcast job.
  Tests cover NULL/blank/NaN but not garbage like `'ABC'` or a malformed OPBAL. High-value
  robustness gap given Pagination is brand new and churned heavily.

#### M-B13. `ArrowSerializer.java` - output Decimal vector hardcoded to `decimal128(38,18)`, ignoring per-output precision
- **File:** `src/v1/java_bridge/java/.../ArrowSerializer.java:180-183,255-258`
- **What:** `createVectorForType` has no precision parameter and `setVectorValue` forces
  `decimal.setScale(18, HALF_UP)`. The Python output schema's precision is not propagated to
  the Java output vector (unlike the input path, which uses `extract_precision_map`).
- **Why it matters:** A Talend `Decimal(20,2)` output silently gains 16 fractional zeros and
  rounds at 18 places instead of 2. Round-trip parity for non-`(38,18)` Decimals is lost.

#### M-B14. `_runs` registry (jobs.py) - unbounded growth, process-local, lost on restart
- **File:** `api/routes/jobs.py`
- **What:** `_runs` has no TTL/eviction; `list_runs`/`get_run_status` lose all history on
  restart, and a multi-worker uvicorn deployment routes polls to workers that never saw the run.
- **Why it matters:** Memory leak plus broken status polling under any realistic deployment.

### MEDIUM - risks

#### M-R1. `validator.py` - reference-integrity layer flags every unconnected component as an orphan, producing noise on valid single-component jobs
- **File:** `src/converters/talend_to_v1/validator.py:150-158`
- **What:** Every component with no flow/trigger is flagged as an orphan warning, with no
  allowance for intentionally-standalone nodes (e.g. a lone `tFixedFlowInput` or `tJava` prejob).
- **Why it matters:** False-positive warnings on legitimately valid configs erode trust in the
  validator output.

#### M-R2. `oracle_connection.py` (converter) - `tDBConnection` forced to Oracle defaults with no needs_review flag
- **File:** `src/converters/talend_to_v1/components/database/oracle_connection.py:45`
- **What:** `tDBConnection` shares `OracleConnectionConverter` and is unconditionally given
  Oracle-specific defaults (`CONNECTION_TYPE ORACLE_SID`, port 1521, `ORACLE_18`, Oracle thin URL).
- **Why it matters:** A generic/non-Oracle `tDBConnection` job is silently converted with Oracle
  semantics and no warning. (Mirrored in the engine `tDBConnection`/`tOracleConnection` registration.)

#### M-R3. `output_router.py` (engine) - `route_outputs` last-writer-wins with no guard against flow-name collisions
- **File:** `src/v1/engine/output_router.py:134`
- **What:** `_data_flows[flow_name] = value` overwrites silently. Intended for the batch/chunk
  re-route case, but a converter bug producing duplicate flow names from distinct upstream
  components manifests as silent data loss rather than an error.
- **Why it matters:** Wrong results with no signal. Consider asserting flow-name uniqueness.

#### M-R4. `executor.py` (engine) - tDie `exit_code` discovery is a fragile 3-level attribute walk
- **File:** `src/v1/engine/executor.py:664-685`
- **What:** tDie detection relies on `exit_code` being on the exception, its `.cause`, or
  `__cause__`. `BaseComponent.execute` wraps every `_process` exception once in a fresh
  `ComponentExecutionError(cause=e)`, so detection survives exactly one wrap level.
- **Why it matters:** If a tDie-style exception is wrapped more than once, `exit_code` lands on
  a deeper cause and a job-halt downgrades to an ordinary component error. A recursive cause-chain
  walk would be robust.

#### M-R5. `extract_json_fields.py` (engine) - multi-match JSONPath serialized as a JSON-array string, diverging from Talend scalar semantics
- **File:** `src/v1/engine/components/transform/extract_json_fields.py:266-272`
- **What:** A single match returns the scalar (dumps only for list/dict), but >1 matches returns
  `json.dumps(matches)`.
- **Why it matters:** Talend tExtractJSONFields with a non-loop mapping query generally takes a
  single node; a bracketed JSON-array string could surprise downstream type coercion. Needs a
  parity test against Talend.

#### M-R6. `xml_map.py` (engine) - `expression_filter` fail-opens (includes all rows) when the Java bridge is unavailable
- **File:** `src/v1/engine/components/transform/xml_map.py:595-608`
- **What:** `_compute_filter_mask` returns `[True]*N` when `self.java_bridge` is falsy or errors;
  the docstring references a native ISNULL/ISNOTNULL evaluator (`_evaluate_groovy_filter_natively`)
  that is not present in the file.
- **Why it matters:** Mismatched row counts vs Talend with no error raised. The documented native
  fallback effectively does not exist.

### MEDIUM - smells

#### M-S1. `file_input_delimited.py` (converter) - two divergent TABLE-parsing idioms for identically-structured tables
- **File:** `src/converters/talend_to_v1/components/file/file_input_delimited.py`
- **What:** `_parse_trim_select` here uses strict fixed-stride slicing and breaks on an incomplete
  trailing group, while excel/positional converters use a push-on-next-`SCHEMA_COLUMN` accumulator
  that tolerates ragged groups.
- **Why it matters:** Same logical TABLE parsed two ways with different edge-case behavior (root
  cause of M-B4). Unify into a single shared base helper.

#### M-S2. `file_output_delimited.py` (converter) - inconsistent `{{java}}` marking across path/stream fields
- **File:** `src/converters/talend_to_v1/components/file/file_output_delimited.py`
- **What:** delimited/input-xml mark `filepath`/`streamname` via `mark_java_expression`, but
  output_excel, output_positional, output_xml, input excel/json/raw, and most utilities do NOT
  mark their path fields.
- **Why it matters:** A `FILENAME` containing a Java concat expression in e.g. tFileOutputExcel
  is not tagged, so the engine/Java bridge will not resolve it - a parity gap captured by no
  `needs_review`.

#### M-S3. `convert_type.py` (engine) - MANUALTABLE coerces one row at a time in a Python loop
- **File:** `src/v1/engine/components/transform/convert_type.py:193-211`
- **What:** Iterates `df[ok_mask].index` and calls `_coerce_series` on a single-element Series per
  row, re-entering pandas parsing per row for datetime/object targets.
- **Why it matters:** O(n) with heavy per-call overhead. A vectorized coerce-with-mask (as in
  schema_compliance_check) would be far faster while still capturing failures for reject routing.

#### M-S4. `python_routine_manager.py` - modules registered in global `sys.modules` under their bare stem
- **File:** `src/v1/engine/python_routine_manager.py:145-167`
- **What:** `sys.modules[module_name] = module` keyed by filename stem. Two routine files with the
  same stem in different subdirs, or a stem colliding with an installed package, overwrite each
  other / shadow real imports process-wide.
- **Why it matters:** Silent module shadowing. Namespace the key (e.g. a sentinel package prefix).

#### M-S5. `oracle_row.py` (engine) - unconditional `conn.commit()` on shared connections defeats tOracleCommit/tOracleRollback
- **File:** `src/v1/engine/components/database/oracle_row.py:413-414`
- **What:** Commits whenever `conn.autocommit` is False, including USE_EXISTING_CONNECTION shared
  connections. oracle_output/oracle_sp share the pattern.
- **Why it matters:** A downstream tOracleRollback cannot undo an already-committed statement -
  parity risk for multi-statement transactional jobs.

#### M-S6. `send_mail.py` (engine) - breaks the `_validate_config` contract and carries dead code
- **File:** `src/v1/engine/components/control/send_mail.py:89,148,286-299`
- **What:** `_validate_config` returns a `List[str]` and never raises, so the lifecycle validation
  gate is a no-op; validation only fires because `_process` manually re-calls `_validate_config`.
  Separately, `validate_config()` (bool) is never called anywhere in `src/v1` (dead).
- **Why it matters:** Inconsistent with every other component, which raises from `_validate_config`.
  Migrate to raise; delete the dead bool method.

#### M-S7. `swift_block_formatter.py` (engine) - `logger.setLevel(logging.DEBUG)` global side effect on every execution
- **File:** `src/v1/engine/components/transform/swift_block_formatter.py:203`
- **What:** Permanently raises log verbosity for the whole `swift_block_formatter` logger namespace
  for the rest of the process, with no reset. **Verified in source.**
- **Why it matters:** Floods logs and affects other jobs/components. Log level belongs to engine
  config, not `_process`.

#### M-S8. `schema_compliance_check.py` (engine) - non-ASCII em-dash inside logger calls violates the ASCII-only logging rule
- **File:** `src/v1/engine/components/transform/schema_compliance_check.py:179,196,249,331`
- **What:** Em-dash (U+2014) is emitted in `logger.info/warning/debug` strings (e.g.
  `"Empty input -- nothing to validate"`).
- **Why it matters:** Logged output, not just comments, so it breaches the hard ASCII-only project
  rule and can corrupt logs under non-UTF-8 handlers.

### MEDIUM - risks (engine base / java bridge)

#### M-R7. `JavaBridge.java` - shared mutable `context`/`globalMap`/`loadedRoutines` HashMaps are not thread-safe
- **File:** `src/v1/java_bridge/java/.../JavaBridge.java:190-191,291-292,485-486,591-592`
- **What:** Plain `java.util.HashMap` mutated via `putAll`/`put` in every `execute_*` method, but
  Py4J `GatewayServer` dispatches each client connection on its own thread. Only
  `compiledScriptClasses` is a `ConcurrentHashMap`.
- **Why it matters:** Today the Python client is single-threaded per bridge, masking this. But the
  class-cache comment touts "truly parallel chunk execution"; any move to concurrent dispatch hits
  unsynchronized shared state (corruption / infinite loop). Use `ConcurrentHashMap` or per-call
  snapshots.

#### M-R8. `JavaBridge.java` / `bridge.py` - context/globalMap keys can never be deleted end-to-end (additive `putAll` + `dict.update`)
- **File:** `src/v1/java_bridge/java/.../JavaBridge.java:190-191`; `bridge.py:1172-1173`
- **What:** Both sides only add/overwrite. A key deleted on the Python side is never removed from
  the Java maps and is resurrected on the next sync. The only explicit pop is the Python-only
  `reject_mode` wrap.
- **Why it matters:** Diverges from Talend, where a variable can be cleared. Latent correctness gap
  for any job that clears a context/global var mid-run.

#### M-R9. `base_component.py` (engine) - StreamingMetadata `requires_full_data` is computed but never consumed; mode is chosen purely by 5GB memory threshold
- **File:** `src/v1/engine/execution_plan.py` (computed) / `src/v1/engine/base_component.py` (`_select_mode`)
- **What:** Streaming vs batch is decided in `BaseComponent._select_mode` purely by
  `MEMORY_THRESHOLD_MB` (5120). A sort/aggregate over a >5GB frame can be switched to STREAMING by
  the memory heuristic even though the plan marks it `requires_full_data=True`.
- **Why it matters:** Per-chunk sort/aggregate produces wrong results on very large inputs. The
  plan-level intent and the runtime decision are disconnected.

#### M-R10. `python_dataframe_component.py` (engine) - does NOT use the D-11 hardened namespace (full builtins incl. `__import__`/`open`/`eval`)
- **File:** `src/v1/engine/components/transform/python_dataframe_component.py:98-116`
- **What:** Builds a plain exec namespace that inherits real `__builtins__` (no `__builtins__` key
  set). Also re-implements `_get_context_dict` locally instead of inheriting `CodeComponentMixin`.
- **Why it matters:** Inconsistent with the other 3 Python components (which use
  `_build_safe_builtins`), re-introducing the broad-builtins surface the mixin was created to remove.

### MEDIUM - improvements

#### M-I1. `file_input_positional.py` (engine) - `trim_select` parsed by converter but completely ignored by engine
- **File:** `src/v1/engine/components/file/file_input_positional.py:304-308`
- **What:** Only `trim_all` (default True) is honored; per-column TRIMSELECT is dropped, so every
  string column is trimmed by default.
- **Why it matters:** Diverges from Talend per-column TRIMSELECT and can corrupt fixed-width fields
  where leading/trailing spaces are significant. Apply per-column trim like `FileInputDelimited._apply_trim`.

#### M-I2. `check_per_module_coverage.py` - gate never asserts the EXPECTED set of in-scope modules is present
- **File:** `scripts/check_per_module_coverage.py`
- **What:** The gate floors per-module coverage but a module never imported during the test run
  simply does not appear in `files` and is silently un-gated (the post-lock pagination/mssql modules
  would pass invisibly if no test imports them).
- **Why it matters:** A coverage blind spot precisely where new code lands. Add an expected-module
  manifest check or compare against `[tool.coverage.run].source`.

---

## LOW severity

Cosmetic, performance, edge-case, or doc-drift items. Grouped by type for scanning.

### LOW - bugs

| ID | File | Summary |
|----|------|---------|
| L-B1 | `file_input_excel.py` (engine) | Excel streaming path is dead code: `_read_streaming` uses undefined `self.chunk_size`, and the HYBRID gate (line 904) checks `self.execution_mode` which the engine never assigns (stays BATCH). Large `.xlsx` always loads fully (silent OOM); the streaming branch would `AttributeError` at line 1057. |
| L-B2 | `file_input_excel.py` (engine) | `_apply_date_conversion` returns `df` only inside the `if convert_date_global and date_select:` block, else returns `None` implicitly. Latent footgun if ever wired into the read path. |
| L-B3 | `expression_converter.py` | `convert()` `.equalsIgnoreCase(` -> `.lower() == str(` leaves an unbalanced expression; `.length()` -> `.__len__()`, `.contains(` -> ` in ` produce invalid operand ordering. (Same root cause family as M-B1; listed low as the rewriter is lossy-by-design.) |
| L-B4 | `extract_regex_fields.py` (engine) | Java-literal regex unescape uses a blanket `replace('\\\\','\\')` that corrupts legitimately escaped backslashes in a pattern. |
| L-B5 | `file_copy.py` (engine) | Directory copy bypasses the friendly `replace_file` pre-check (gated on `not is_directory_copy`), so a directory `copytree(dirs_exist_ok=False)` surfaces a raw `FileExistsError` instead of the intended `[id] Destination already exists` message. |
| L-B6 | `filter_rows.py` (engine) | Dead/contradictory empty-input branch (lines 226-229) builds an `errorMessage` column on a local `empty_reject` that is immediately discarded; returns `reject=None`, inconsistent with the non-empty path that always returns a reject DataFrame. |

### LOW - risks

| ID | File | Summary |
|----|------|---------|
| L-R1 | `trigger_manager.py` (engine) | `_evaluate_condition` uses `eval()` with restricted `_SAFE_GLOBALS` (no `__builtins__`). Reasonable for trusted converter output, but a residual eval footgun if job configs are externally supplied; a literal-only AST evaluator would remove it. |
| L-R2 | `base_component.py` (engine) | Source components (input_rows==0) set `NB_LINE = main_count + reject_count`; a transform that legitimately receives 0 input rows is indistinguishable from a source and mis-counts NB_LINE from its outputs. |
| L-R3 | `base_iterate_component.py` (engine) | `execute()` rejects re-execution for RUNNING/SUCCESS without `reset()` but does NOT guard the ERROR state; a second execute after a failed iterate rebuilds the iterator buffer. |
| L-R4 | `file_input_delimited.py` / `file_input_positional.py` (engine) | Non-printable scrub regex `[^\x20-\x7E\t\n\r]` replaces ALL non-ASCII codepoints (valid Latin-1/UTF-8 accented chars) with a space, mangling legitimate ISO-8859-15 data. |
| L-R5 | `file_input_json.py` (engine) | `urlopen(urlpath)` has no scheme allowlist, timeout, or size cap - a context-driven `urlpath` could fetch `file://`/internal endpoints (SSRF) or hang. |
| L-R6 | `file_output_positional.py` (engine) | append+compress writes to a gzip stream opened `ab`/`wb`, producing a multi-member gzip (valid, but some readers mishandle) rather than one contiguous stream. |

### LOW - smells (converter)

| ID | File | Summary |
|----|------|---------|
| L-S1 | `converter.py` | `self._expr_converter` constructed in `__init__` but never used; component converters and trigger_mapper instantiate their own. Dead member. |
| L-S2 | `converter.py` | `_JAVA_COMPONENT_TYPES` is a hardcoded set mixing Talend names with internal/aliased names that duplicates knowledge in the converters and can drift from the registry; converters should declare `requires_java`. |
| L-S3 | `xml_parser.py` | Context string values are quote-stripped twice (parser + base `_get_str`); inconsistent for double-quoted values. Centralize quote handling. |
| L-S4 | `base.py` | `_DATE_TOKENS` maps `SSS` -> `%f` (Java ms = 3 digits, Python `%f` = microseconds = 6) - sub-second patterns off by 1000x in width. |
| L-S5 | `file_input_excel.py` | Date-pattern handling inconsistent: schema columns converted via `_convert_date_pattern`, but `_parse_date_select` keeps raw Java patterns ("engine handles internally"). Two contracts in one component. |
| L-S6 | `file_input_json.py` | Path-field config key inconsistency: input_json/fullrow/raw/msxml/properties/output_excel/output_xml use `filename`; input_delimited/positional/xml/output_delimited/positional use `filepath`. |
| L-S7 | `file_output_xml.py` | Docstring claims `FileOutputXML` is "registered under both names", but only `@REGISTRY.register('tFileOutputXML')` runs; `FileOutputXML` is the engine type_name, not a registry key. |
| L-S8 | `change_file_encoding.py` | Docstring header says "No v1 engine implementation exists" but `convert()` emits zero needs_review and an engine file exists - stale header. |
| L-S9 | `convert_type.py` (converter) | Emits type_name `tConvertType` (keeps t-prefix) and a "no v1 engine implementation" needs_review, but an engine `convert_type.py` exists. Doc/code drift; t-prefix may cause dispatch to miss the engine class. |
| L-S10 | `extract_json_fields.py` (converter) | Stale comment says stride-3 but `_XPATH_MAPPING_FIELDS` has 4 entries and the parser uses stride-4 (constants/parser correct). |
| L-S11 | `map.py` (converter) | `import re` inside `_java_expr` on every call instead of module-level (xml_map.py imports at module level); hot path. |

### LOW - smells (engine / bridge / db / api / tooling)

| ID | File | Summary |
|----|------|---------|
| L-S12 | `engine.py` | `component.is_subjob_start` set on every component but never read; subjob topology is driven by ExecutionPlan. Dead metadata. |
| L-S13 | `execution_plan.py` | `StreamingMetadata` computed and exposed via `get_streaming_metadata` but never consumed (see M-R9). |
| L-S14 | `context_manager.py` | `resolve_string` substitutes `str(value)`, so a typed context value (`id_Integer`, `id_Date`) becomes its string form when embedded in a config string; TriggerManager deliberately uses `repr()` instead. Asymmetry worth a comment. |
| L-S15 | `bridge.py` | Stray unused `from attr import field` (line 22) pulls in third-party `attrs` unnecessarily; `field` never referenced. **Verified in source.** |
| L-S16 | `mssql_connection.py` / `mssql_input.py` | Encrypted-password handling order differs between the two converters (strip-then-prefix-check vs prefix-check-then-strip); avoidable divergence in files that should behave identically. |
| L-S17 | `warn.py` (converter) | `_PRIORITY_ITEMS` declared at module scope but never referenced; priority emitted as raw string code. Dead constant. |
| L-S18 | `aggregate/__init__.py` | Inconsistent registration import style: aggregate/control import converter CLASSES while database/context/iterate import MODULES. Standardize on module imports with noqa. |
| L-S19 | `mssql_input.py` / `oracle_input.py` (converter) | `_parse_trim_column` duplicated verbatim; same KEY/VALUE stride-2 parsing re-implemented in flow_to_iterate and send_mail. A shared `base._parse_table` would remove ~6 near-identical parsers. |
| L-S20 | `base.py` (converter) | Redundant quote-stripping: `xml_parser._parse_element_params` already strips scalar params, yet `base._get_str` strips again; double strip obscures where canonicalization happens (TABLE-value stripping is NOT redundant). |
| L-S21 | `oracle_bulk_exec.py` (engine) | SQL*Loader control file interpolates table name and INFILE path without identifier validation/quoting, unlike oracle_output - inconsistent with the T-11-04 mitigation. |
| L-S22 | `die.py` / `warn.py` (engine) | Identical module-level helpers (`_resolve_globalmap_vars`, `_log_at_priority`, `_GLOBALMAP_PATTERN`) copy-pasted across both files; extract a shared helper module. |
| L-S23 | `die.py` (engine) | `exit_code` validated/read but the converter never emits it (emits only `code`/`exit_jvm`), so every tDie reports exit code 1; dead/decoupled config or a parity gap. |
| L-S24 | `java_component.py` (engine) | ~7-line comment inaccurately describes `groovy_escape_expression` as handling "backslashes, quotes, and newlines"; it only escapes `$` inside double-quoted strings. |
| L-S25 | `row_generator.py` (engine) | Bare `eval()` (`__builtins__={}`, only `random`); the fallback returns the raw string on SyntaxError/NameError, so a typo'd expression silently becomes a literal value rather than erroring. |
| L-S26 | `swift_transformer.py` (engine) | `_init_transformer_config` and `_ensure_config_loaded` duplicate ~25 lines of config-section extraction (drift risk); factor into `_apply_transform_config`. |
| L-S27 | `file_delete.py` (engine) | A missing path is silently a soft reject (rows_reject=1) regardless of `failon`; Talend tFileDelete FAILON typically raises on missing target. Verify parity. |
| L-S28 | `file_output_delimited.py` (engine) | `_resolve_line_separator` checks `os_line_separator` (default True) FIRST, so `csvrowseparator`/`row_separator` are silently ignored unless `os_line_separator=false` is also set. |
| L-S29 | `file_archive.py` (engine) | When archiving a directory, `arcname=relpath(file, source)` drops the source folder name from the archive (members become top-level), possibly diverging from Talend tFileArchive. |
| L-S30 | `file_copy.py` (engine) | File-mode copy with `create_directory=True` calls `os.makedirs(destination)` on the whole destination, surprising when destination is meant as a file path. |
| L-S31 | `replace.py` (engine) | Simple-mode `.astype(str)` turns NaN/None into literal `'nan'`/`'None'` before substitution, permanently stringifying untouched cells. |
| L-S32 | `apply_filter` in `map_joins.py` (engine tMap) | Silently returns df unchanged when bridge mask length != len(df) (`return df[mask] if mask.size == len(df) else df`), letting reject/filter rows through undetected. |

### LOW - smells (tooling/config)

| ID | File | Summary |
|----|------|---------|
| L-S33 | `pyproject.toml` | Dead omit pattern `src/converters/complex_converter/*` - the directory no longer exists (CLAUDE.md still cites it as active). |
| L-S34 | `add_connectors.py` | No module guard against the in-place `INPUT_FILE==OUTPUT_FILE` rewrite; uses relative paths, so it only works from repo root. |
| L-S35 | `swift_transformer.py` (CLI, `src/python_routines`) | Uses `print()` for warnings rather than logging, and shares the class name `SwiftTransformer` with the engine component - latent naming collision if `python_config.routines_dir` points at `src/python_routines`. |
| L-S36 | `map_component.py` (engine tMap) | `temp_join_key_cols = {}` is passed to `compute_joined_df_schema` but never populated - vestigial wiring implying a removed code path. |

### LOW - improvements

| ID | File | Summary |
|----|------|---------|
| L-I1 | `file_output_excel.py` (converter) | 16 individually-appended needs_review dicts (lines 140-234) could collapse to a `(key, detail)` tuple loop like input components, cutting ~90 lines and drift risk. |
| L-I2 | `__init__.py` (transform converters) | Mixed v1 `type` naming convention: unimplemented components keep the t-prefix (tConvertType, tReplace, ...) while implemented ones use PascalCase. Looks intentional but undocumented and brittle if downstream dispatches on `type`. |
| L-I3 | `filter_rows.py` (converter) | `_translate_function` passes an unrecognized Java FUNCTION template through verbatim with only a `logger.warning`; emit a `needs_review` so it surfaces in the migration report. |
| L-I4 | `aggregate_row.py` (converter) | `list_delimiter` injected only into `list` operations; verify whether `list_object` operations also need `op['delimiter']` at runtime. |
| L-I5 | `unique_row.py` (engine) | Docstring advertises keep `"first"/"last"/False` but the converter pins `"first"`; the other branches would silently break Talend parity. Narrow the contract or validate `keep` against `{"first"}`. |
| L-I6 | `mssql_connection.py` (engine) | Uses `open_ad_hoc(self.id)` for a registered shared connection, diverging from OracleConnection's `register()` path; add a dedicated open+register helper for symmetry. |
| L-I7 | `JavaBridge.java` | `executeJavaRow` rebuilds a HashMap + fresh Script instance and re-runs `addRoutinesToBinding` per row; reuse a single Binding/instance per chunk and swap `input_row`. |
| L-I8 | `JavaBridge.java` | `executeOneTimeExpression`/`executeBatchOneTimeExpressions` build a NEW GroovyShell per call with no caching (tMap caches compiled classes; one-time exprs do not); add a small LRU of compiled expression classes. |
| L-I9 | `py_map.py` (engine) | `RELOAD_AT_EACH_ROW` join and `_apply_filter_py` iterate with `iterrows()` + per-row eval (O(n*m)), only soft-warned at >10k x 10k; document a row cap or vectorize the equality case. |
| L-I10 | `map_component.py` (engine tMap) | `execute_compiled_tmap_chunked` is called with a hardcoded `chunk_size=50000` while `_resolve_expressions` resolves an `output_chunk_size` key that never reaches the bridge - the override is effectively dead for tMap. |
| L-I11 | `python_routine_manager.py` | `_load_module` registers modules in `sys.modules` under their bare stem; a namespaced key (`dataprep_routine.<qualified>`) would make discovery collision-safe (see M-S4). |

---

## Strengths to Preserve (the `good` findings)

These are deliberate, often non-obvious design decisions. Refactors and coverage work
should keep them intact; many encode hard-won parity or correctness fixes.

### Converter

- **Robust failure isolation** (`converter.py:82-110`): the per-node try/except converts any
  converter exception into an `_unsupported` placeholder plus a warning (logged with `exc_info`),
  so one malformed component never aborts a whole job. Combined with the
  `_warnings`/`_needs_review`/`_validation` out-of-band channels, this gives a partial-success
  model well-suited to bulk migration.
- **NUL-delimited placeholder tokens in `_convert_date_pattern`** (`base.py`): avoids
  overlapping-token corruption (MM vs mm, ss vs SSS) - a correct, non-obvious fix to a common
  date-format-translation bug (also noted in conv-rest as a two-phase placeholder swap).
- **`oracle_row._parse_prepared_params` defensive validation**: drops incomplete bind groups
  (WR-03) and rejects non-numeric / `<1` parameter_index (WR-04), piping human-readable warnings
  into `ComponentResult.warnings` instead of letting the engine crash at `int('abc')`. Best-in-subsystem
  input validation worth replicating.
- **`tMap` per-flow input schemas under `schema.inputs`** (`map.py:348-353`): lets the engine build
  a complete declared-type map for the joined DataFrame, preventing the Java-bridge strict boundary
  check from rejecting every main/lookup column. `_java_expr` also collapses CRLF/CR/LF to a single
  space to avoid Groovy Automatic Semicolon Insertion.
- **`aggregate_sorted_row` flush-on-OUTPUT_COLUMN state machine** (lines 92-135): correctly handles
  the optional IGNORE_NULL field that would desynchronize a naive stride-4 parser (same pattern in
  split_row).
- **`xml_map` XPath rewriting** avoids `ancestor::` by inferring the loop element's full path and
  emitting `../` relative traversal; uses `str.removeprefix()` over `lstrip()` (D-76) to avoid
  character-class stripping bugs.
- **`file_output_positional` parity hygiene**: proactively emits structured `engine_gap`
  needs_review entries for every key-name/default mismatch and even flags that
  `FileOutputPositional`'s engine class is NOT in `COMPONENT_REGISTRY` - turning silent runtime
  failures into auditable conversion-report data.
- **Strong parity discipline in `aggregate_row`** (engine converter side, WR-10/WR-11/BUG-AGG-001/D-C5):
  inline citations explain count=non-null, `sort=False` group order, ArrayList.toString() replication,
  and the deliberate replacement of dead fallback branches with explicit ConfigurationError guards.

### Engine orchestration / base / services

- **Iterative deque-based subjob/trigger processing** (`executor.py`): deliberately avoids recursion
  to survive long trigger chains; covered by `TestIterativeTriggerFiring.test_long_trigger_chain_no_recursion_error`.
- **Stall detection** (`executor.py:168-188`): raises ConfigurationError naming stuck components and
  their missing input flows, ordered AFTER streaming-sink finalization (CR-01) so output files always
  close.
- **`are_inputs_ready` treats iterate flows as control-flow edges** (`output_router.py:196-202`):
  skips them so iterate-body consumers are not falsely blocked - the matching half of `route_outputs`
  mapping iterate -> `iterate` result key.
- **Iterate body driver** resets body component state and discards them from `executed_components`
  each iteration (`executor.py:506-516`), buffers per-iteration rejects, and re-derives config from
  `_original_config` for clean per-iteration re-execution.
- **Config immutability** (`base_component.py:180-181,225`): `_original_config` deepcopied at
  construction and re-derived each `execute()` so iterate re-execution starts from a clean,
  unresolved config.
- **`_make_default_series`** (`base_component.py:722-775`): explicit-dtype `pd.Series` construction
  preserves column dtype even on empty DataFrames, handling datetime nullability via `pd.NaT` vs
  `pd.Timestamp(0)`.

### Java bridge

- **Py4J Base64 signed-int overflow handling** (`bridge.py`): documented `_PY4J_BYTE_ARG_SAFE_LIMIT`
  (~1.5 GB), pre-flight size guard AND runtime `NegativeArraySizeException` catch, both halving the
  range with front-insertion that preserves row order; single-row overflow correctly re-raises.
- **BRDG-06 compiled-script design** (`JavaBridge.java`): caches the Script Class (not instance) so
  each row/chunk gets a fresh Binding with no `synchronized(script)` bottleneck and no cross-row
  variable bleed.
- **Dynamic port allocation** (`java_bridge_manager.py:140-151`): honestly acknowledges and mitigates
  the TOCTOU race between releasing the probe socket and the JVM binding, with up to 3 retries gated
  on "Address already in use".
- **Vendored Talend routine `CHAR(int)` quirk** (`DataOperation.java`): intentionally Talend-faithful
  (uses `Character.forDigit(i,10)`), preserved for parity - flagged so nobody "fixes" it.

### Database layer

- **Connection-lifecycle design** (`oracle_connection_manager.py`): idempotent start/stop, per-connection
  try/except on close, process-global thick-init guard, credentials never logged or repr'd; MSSql mirrors it.
- **PARAMETER_TYPE coercion table** (`oracle_row.py`): 19-entry map rigorously sourced against the
  Talaxie XML enum (16 verified + 3 defensive aliases), decimal coercion through `str` to avoid float
  roundtrip, unknown types rejected at both validate and process time.

### File / transform engine components

- **`_xml_io.secure_xml_parser`**: hardened against XXE / billion-laughs / network
  (`resolve_entities=False`, `no_network=True`, `load_dtd=False`); `iterparse_loop_query` is
  memory-correct (clears element + prunes preceding siblings) with try/finally cleanup on GeneratorExit;
  `recover=False` fails loud so malformed XML routes to REJECT.
- **`FileInputDelimited` two-tier validation engine**: vectorized fast path falling back to per-row
  only for failing columns, chunked (50k) path when row-level checks are on, with stable errorCode
  constants and date validation before type conversion.
- **`file_unarchive` zip-slip protection**: resolves each member's abspath against `abs_output + os.sep`
  (and equality) BEFORE any write, correctly handling the prefix-collision case (`/out` vs `/output`).
- **`file_output_excel` `_last_data_row` scan**: defends against openpyxl's ghost `max_row=1` on fresh
  sheets, preventing a one-row content shift and duplicate headers on append.
- **`file_list` mask compilation hoisted out of the per-file loop** (WR-07): O(N_files x N_masks) regex
  compiles reduced to O(N_masks); stricter `_normalize_case_sensitive` for CASE_SENSITIVE.
- **`Join` single-pass merge with null sentinel** (`join.py:30,187-216`): null keys never match (SQL/Talend
  semantics) via replace-then-reclassify, with documented removal of proven-dead defensive branches.
- **`xml_map.split_steps`**: bracket-depth-tracking XPath tokenizer that preserves predicates containing
  `/` (BUG-XMP-014) and axis shorthands; per-row loop with a flat-to-flat fast path.
- **`normalize`**: preserves Talend's documented discard->trim->dedupe order and trailing-empty semantics
  (`_strip_trailing_empties` mirrors `lastNoEmptyIndex_`).
- **`UniqueRow` case-insensitive dedup**: lowercased temp columns built only when a key column is
  case-insensitive AND string-typed, on a single lazy `.copy()`, preserving original casing and index
  alignment.

### tMap engine

- **`_attach_empty_lookup_columns`** (`map_joins.py:478-520`): careful dtype-preserving null fill
  (datetime->NaT, int->float64, object->Python None for BigDecimal/str, else dtype NaN) so Arrow renders
  declared types faithfully on empty/missing lookups.
- **`groovy_escape_expression`** (`map_compiled_script.py:322-373`): correct hand-written scanner escaping
  `$` only inside double-quoted string literals (consuming `\\`/`\"` as units), preventing GString
  interpolation of Talend literals like `"Total: $100"`; covered by `test_map_groovy_safety.py`.
- **`map_bridge_sync` id_Float wrapping**: single, well-documented chokepoint wrapping id_Float context
  values via `java.lang.Float` so Py4J's float->Double coercion does not silently change Float-typed
  context vars.

### API / tooling

- **Filename allowlist regex** (`routines.py` / `python_routines.py`): `^[A-Za-z][A-Za-z0-9_]*\.(java|py)$`
  blocks path traversal on the `{filename}` param, applied consistently across list/get/create/update/delete.
- **Context-manager use of `ETLEngine`** (`jobs.py`): `with ETLEngine(...) as engine:` ensures
  `_cleanup()` (Java bridge stop, Oracle/MSSql close) runs even when `execute()` raises.
- **Per-module coverage floor** (`check_per_module_coverage.py`): stdlib-only, ASCII-only, fail-loud
  (SystemExit(2) on malformed/short records); a global `fail_under` would let a 100%-covered module
  average out a 60%-covered one.

---

## Open Questions

Unresolved questions raised by the readers. Most need a Talend reference job, an engine-vs-converter
reconciliation, or a decision about the new (post-doc-lock) components. Resolve these before the
coverage push so tests assert the correct contract, not the current (possibly buggy) behavior.

### Correctness / parity decisions

1. **RunIf via `convert()` vs `{{java}}`:** Should RunIf conditions be marked `{{java}}` and deferred
   to the bridge (consistent with the rest of the pipeline) instead of passing through the lossy
   `ExpressionConverter.convert()` rewriter (M-B1, L-B3)? Is the `!=` corruption actually exercised in
   the real corpus, or are RunIf conditions always null-checks? (grep sample `.item` CONDITION params).
2. **Oracle identifier quoting:** Is identifier emission intended to be UNQUOTED (refactor intent,
   fixing ORA-00942 case mismatch) or QUOTED (what `test_oracle_output.py` still asserts)? Production
   code and tests currently disagree (H-B3/H-B4/H-B5/H-S1).
3. **Shared-connection commits:** Should tOracleRow/tOracleOutput/tOracleSP suppress their unconditional
   `conn.commit()` on `use_existing_connection` connections so tOracleCommit/tOracleRollback retain
   transaction control (M-S5)?
4. **tDie exit code:** Does Talend tDie set the process/JVM exit code from the CODE parameter? If so,
   hardcoding `exit_code=1` (never wired from the converter) is a real parity gap; if not, `exit_code`
   is dead config to remove (L-S23).
5. **Global first/last aggregation:** Should the no-group-by AggregateRow path support `first`/`last`
   at all in Talend? If yes, fix `_global_aggregation` (M-B6); if invalid in Talend, `_validate_config`
   should reject it explicitly rather than crash.
6. **tConvertType / tChangeFileEncoding "no engine" claims:** Both have engine files present yet their
   converters claim no engine implementation (L-S8/L-S9). Are these needs_review/docstrings stale, and
   does the t-prefixed type for tConvertType cause dispatch to miss the engine class?
7. **catch_output_reject expressions (tMap):** Is full Java-expression evaluation expected on catch
   outputs? The engine MVP defaults complex expressions to None (a silent parity gap) - needs a Talend
   reference job.
8. **tConvertType stale source column:** Does any job config use MANUALTABLE with `input_column !=
   output_column`, and does `output_schema` always list only the destination so the stale source column
   is dropped (M-B8)?
9. **ExtractJSONFields multi-match:** What is the Talend-verified behavior for a mapping query matching
   multiple nodes in a non-loop context - first match, last match, or array (M-R5)?
10. **Positional reject/trim:** Is `FileInputPositional`'s lack of a reject flow and its ignoring of
    `trim_select` an accepted simplification or a gap to close (M-I1)?
11. **Non-printable scrub:** Is stripping ALL non-ASCII to space intentional given ISO-8859-15 defaults,
    or should it be narrowed to control bytes + U+FFFD to preserve accented characters (L-R4)?
12. **FileArchive root folder / FileDelete missing path / FileOutputExcel non-passthrough:** Confirm Talend
    semantics for (a) whether the source folder name is preserved as the archive root (L-S29), (b) whether
    FAILON raises on a missing delete target (L-S27), and (c) whether Excel returning `main=None` (vs
    pass-through) is intentional for downstream sink chaining.

### Java bridge / types

13. **Bridge concurrency:** Is the JavaBridge ever invoked concurrently (parallel chunks, Py4J callbacks,
    shared bridge)? If so, the unsynchronized `context`/`globalMap`/`loadedRoutines` HashMaps are a real
    correctness risk (M-R7).
14. **Key deletion:** Does the engine ever need to DELETE a context/globalMap key mid-job? Current additive
    `putAll` + `dict.update` makes removal impossible end-to-end except the Python-only reject_mode pop (M-R8).
15. **Decimal output scale:** Where (if anywhere) is the declared output precision/scale applied for
    tMap/tJavaRow Decimal columns? The Java path hardcodes `decimal128(38,18)` (M-B13).
16. **One JVM per job:** Is one JVM strictly one job for the product lifetime? `Numeric.sequence`/`seq_Hash`
    and GroovyShell state are process-global; reuse across jobs would leak sequence counters.
17. **Datetime fidelity:** Is the sub-millisecond truncation + naive(local)/aware(UTC) tz handling acceptable,
    or does parity require a naive-datetime wall-clock round-trip test?
18. **Stray import:** Is `from attr import field` in `bridge.py` intentional or removable dead code (L-S15)?

### Security / API posture

19. **Is the API meant to ship,** or is it a localhost-only dev prototype? The security posture (no auth,
    open CORS, traversal, arbitrary `.py` write) only makes sense for a trusted single-user tool
    (H-R2/H-R3/H-R4).
20. **API launch / multi-worker:** How is the API process launched (no `__main__`/uvicorn entrypoint, no
    `[project.scripts]`)? Is multi-worker deployment a goal (the in-memory `_runs` tracker breaks under it - M-B14)?
21. **swift_transformer python_expression sandbox:** Should it be locked down to the D-11 safe namespace,
    given config files may come from less-trusted sources than inline job code (H-R1)?
22. **PythonDataFrameComponent namespace:** Is the full-builtins namespace (incl. `__import__`) an intentional
    "trusted vectorized path" carve-out or an oversight that should adopt `_build_safe_builtins` (M-R10)?
23. **Standalone swift_transformer.py placement:** Should it live under `src/python_routines` at all? It is a
    CLI, not an engine routine, yet sits in the dir `PythonRoutineManager` scans, colliding with the engine
    `SwiftTransformer` component (L-S35).

### Tooling / coverage / build

24. **Stale 181-module baseline:** Should `14-coverage.json` and the "181 modules" figure in CLAUDE.md be
    re-locked to include the post-lock pagination/mssql/oracle modules, or is 181 a frozen historical
    artifact? The current tree has ~198 in-scope modules (H-R-tooling).
25. **`ui_registry_v2.json`:** Is it live or dead? It uses divergent component keys (PyMap, tFilterRow,
    tExtractJSONFields, tXMLMap) and lacks tPagination; could be loaded by mistake.
26. **`add_connectors.py` vs generated registry:** tPagination's connector spec is only in the generated
    `ui_registry.json`, not in `CONNECTOR_MAP`; is `add_connectors.py` still the intended generator, or did
    registration move to a build-time step (commit cae6127)?
27. **New DB modules and the gate:** Do the new engine oracle/mssql modules have non-oracle-marked unit tests
    so they are actually measured by the coverage gate (which excludes `-m oracle`), or do they escape the
    floor when no Oracle container is present (M-I2)?
28. **`pyproject.toml` runtime deps:** fastapi/uvicorn/python-multipart are declared only under the optional
    `api` extra, so a plain install ImportErrors at import of `api/app.py`. Intended, or should they move to
    core runtime deps?

### Post-lock component integration

29. **Pagination/MSSQL/Oracle wiring:** Where do the new Pagination and MSSQL components register and execute?
    They do not appear in the orchestration core's iterate/full-data/Oracle type sets - confirm they need no
    `execution_plan`/engine wiring beyond the generic REGISTRY path, and that no new connector/trigger types
    fall outside the closed-world `_FLOW_CONNECTOR_TYPES`/`_TRIGGER_TYPE_MAP` frozensets.
30. **Pagination sort:** Is the lexical (string) sort universally desired, or should `sort_columns` optionally
    support numeric/date typing like SortRow (M-B12 context)?
31. **Iterate stats double-count:** Do `tForeach`/`tFlowToIterate` `finalize()` (which sets NB_LINE directly)
    and `BaseIterateComponent.update_iteration_stats` (which accumulates body NB_LINE) ever double-count, given
    Executor ordering?
