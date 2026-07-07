# ETL component config surfaces (code-verified ground truth)

*Generated 2026-07-03 by code investigation. Source: engine component source, `_validate_config`, module constants, dataclasses, and test fixtures. `ui_registry.json` was deliberately NOT used (it is incomplete/wrong for this).*

This is the authoritative input for authoring the curated per-component config schemas (plan 2). Every claim cites `file:line`. Keep in sync with the code via the enum-ref drift check + fixture-consistency tests.

## Universal base keys (BaseComponent — all components)

Read in `BaseComponent.execute()` before `_process()` (`src/v1/engine/base_component.py`).

| key | type | default | source | notes |
|---|---|---|---|---|
| die_on_error | bool | **True** | base_component.py:234 | Drives schema-violation routing. Several components ALSO read their own `die_on_error`/`dieonerror` with default False (dual-default landmine). |
| execution_mode | str | "hybrid" | base_component.py:454 | batch/streaming/hybrid. Map overrides `_select_mode` -> always BATCH. |
| chunk_size | int | 10000 | base_component.py:507 | streaming chunk size. |

## 1. FileInputDelimited
File: `file/file_input_delimited.py`. Register: `("FileInputDelimited","tFileInputDelimited")` (105). No dataclass; `self.config.get`. `_validate_config` requires `filepath` (135).

| key | type | default | required | enum | line |
|---|---|---|---|---|---|
| filepath | str | "" | YES | - | 157 |
| fieldseparator | str | ";" | no | - | 158 |
| row_separator | str | "\\n" | no | soft {\\n,\\r\\n,\\r} | 159 |
| encoding | str | "ISO-8859-15" | no | - | 160 |
| header_rows | int | 0 | no | - | 161 |
| footer_rows | int | 0 | no | - | 162 |
| limit | str | "" | no | int-parsed | 163 |
| remove_empty_row | bool | True | no | - | 164 |
| csv_option | bool | False | no | - | 165 |
| csv_row_separator | str | "\\n" | no | - | 166 |
| escape_char | str | '"' | no | - | 167 |
| text_enclosure | str | '"' | no | - | 168 |
| trim_all | bool | False | no | - | 169 |
| trim_select | list[{column:str,trim:bool}] | [] | no | - | 170 |
| check_fields_num | bool | False | no | - | 171 |
| check_date | bool | False | no | - | 172 |
| die_on_error | bool | False (local) | no | - | 173 |
| uncompress/split_record/random/advanced_separator/enable_decode | bool | False | no | DEFERRED (warn) | 176 via `_DEFERRED_FEATURES` (96) |

Stale docstring keys (never read): nb_random, decode_cols, tstatcatcher_stats. Fixture-only (ignored): decimal_separator, thousands_separator, label.

## 2. FileOutputDelimited
File: `file/file_output_delimited.py`. Register: `("FileOutputDelimited","tFileOutputDelimited")` (78). No dataclass; bools via `_bool()`. Requires `filepath` (228).

| key | type | default | required | enum | line |
|---|---|---|---|---|---|
| filepath | str | "" | YES | - | 271 |
| csv_option | bool | False | no | - | 256 |
| include_header | bool | False | no | - | 257 |
| append | bool | False | no | - | 258 |
| create_directory | bool | True | no | - | 264 |
| split | bool | False | no | - | 265 |
| delete_empty_file | bool | False | no | - | 266 |
| file_exist_exception | bool | True | no | - | 267 |
| os_line_separator | bool | True | no | - | 268 |
| streamname | str | "outputStream" | no | {{java}} | 272 |
| fieldseparator | str | ";" | no | - | 273 |
| row_separator | str | "\\n" | no | - | 274 |
| encoding | str | "ISO-8859-15" | no | - | 275 |
| escape_char | str | '"' | no | - | 276 |
| text_enclosure | str | '"' | no | - | 277 |
| csvrowseparator | str | "LF" | no | soft {LF,CR,CRLF} via `_CSV_ROW_SEPARATORS` (71) | 278 |
| split_every | str | "1000" | no | int-parsed | 279 |
| compress/usestream/row_mode/flushonrow/advanced_separator | bool | False | no | DEFERRED | 291 via `_DEFERRED_FEATURES` (57) |

Stale docstring: die_on_error (base-only), thousands_separator, decimal_separator. Fixture-only: flush_row_count (code reads flushonrow), label, tstatcatcher_stats.

## 3. FilterRows
File: `transform/filter_rows.py`. Register: `("FilterRows","FilterRow","tFilterRow","tFilterRows")` (154). No dataclass.

| key | type | default | required | enum | line |
|---|---|---|---|---|---|
| use_advanced | bool | False | no | - | 178 |
| advanced_cond | str | "" | YES when use_advanced (183) | must contain {{java}} | 181 |
| conditions | list[dict] | [] | must be list (188) | - | 187 |
| logical_op | str | "&&" | no | `_LOGICAL_OP_MAP` {&&,\|\|,AND,OR} (71) | 287 |

conditions[] sub-keys (325-328): column(str, req 197), operator(str, req 201, enum `_OPERATOR_MAP` validated 206), function(str, `_FUNCTION_MAP`+dynamic LEFT/RIGHT, NOT validated), value(str).
`_OPERATOR_MAP` (32-48, VALIDATED): ==,!=,>,<,>=,<=,MATCHES,CONTAINS,NOT_CONTAINS,STARTS_WITH,ENDS_WITH,IS_NULL,IS_NOT_NULL,LENGTH_LT,LENGTH_GT.
`_FUNCTION_MAP` (54-65): "",LOWER,UPPER,LOWER_FIRST,UPPER_FIRST,LENGTH,TRIM,LTRIM,RTRIM,ABS + LEFT(n)/RIGHT(n).

## 4. AggregateRow
File: `aggregate/aggregate_row.py`. Register: `("AggregateRow","tAggregateRow")` (283). No dataclass.

| key | type | default | required | enum | line |
|---|---|---|---|---|---|
| groupbys | list[{input_column,output_column}] | [] | no (sub-keys hard-required KeyError 356-357) | - | 351 |
| operations | list[dict] | [] | must be list (309) | - | 352 |
| list_delimiter | str | "," | no | - | 353 |
| use_financial_precision | bool | True | no | - | 354 |

operations[] (367-371, validated 314-332): function(str, req 319, enum `_SUPPORTED_FUNCTIONS` validated 328, lowercased), input_column(str, req 323), output_column(str, default=input_column), ignore_null(bool, True).
`_SUPPORTED_FUNCTIONS` (31-35, VALIDATED): count,min,max,avg,sum,first,last,list,list_object,count_distinct,std,population_std_dev,median,variance,union.

## 5. Map / tMap  (ONLY dataclass-backed; needs hand overlay)
Files: `transform/map/map_config.py` (dataclasses+parse_config+validate_config), `map_component.py`. Register: `("Map","tMap")` (26). `_validate_config` -> parse_config + validate_config.

MapConfig top-level: inputs.main(MainInputCfg, main.name req 207), inputs.lookups(list[LookupCfg]), variables(list[VariableCfg]), outputs(list[OutputCfg], >=1 req 209), die_on_error(bool, **True**, 168), enable_auto_convert_type(bool, False), label(str,"").
MainInputCfg (41-48): name(req 207), filter, activate_filter(bool,F), matching_mode(str,"UNIQUE_MATCH"), lookup_mode(str,"LOAD_ONCE").
LookupCfg (50-58): name(req 219), join_keys(list[JoinKeyCfg]), join_mode(str,"LEFT_OUTER_JOIN"), matching_mode("UNIQUE_MATCH"), lookup_mode("LOAD_ONCE"), filter, activate_filter.
JoinKeyCfg (32-39): lookup_column(req 223), expression(req 227), type(str,"str"), nullable(bool,T), operator(str,"="  -- NO-OP: parsed, read by no join path; engine is equality-only).
VariableCfg (61-66): name, expression, type("str"), nullable(T).
OutputCfg (69-77): name(req 213), columns(list[ColumnCfg], non-empty req 215), is_reject(bool,F), inner_join_reject(bool,F), catch_output_reject(bool,F -- ERROR-only, not filter-reject), filter, activate_filter.
ColumnCfg (21-29): name, expression, type, nullable(T), length(int,-1), precision(int,-1), date_pattern(str,"").

Enums NOT engine-validated (validate_config only checks name/column/expression presence + java bridge) -- values below are the ones the engine actually recognizes: join_mode {LEFT_OUTER_JOIN,INNER_JOIN}; matching_mode {UNIQUE_MATCH,FIRST_MATCH,ALL_MATCHES} (ALL_ROWS NOT recognized -- silently aliases UNIQUE_MATCH keep-last, map_joins.py:455-463); lookup_mode {LOAD_ONCE,RELOAD_AT_EACH_ROW} (RELOAD/CACHE_OR_RELOAD NOT recognized -- silently act as LOAD_ONCE, map_joins.py:67); operator {"="} only.

DRIFTS (hand-overlay required): (1) column date-format key: dataclass reads `date_pattern` (map_config.py:149) but converter emits **`pattern`** (converter transform/map.py:251) -> date formatting silently unwired; real key is `pattern`. (2) converter emits column `operator` (map.py:248) - no ColumnCfg field. (3) NO-OPs: rows_buffer_size/output_chunk_size context-resolved but never consumed (chunk hardcoded 50000); component_type, change_hash_and_equals_for_bigdecimal unused. (4) Ignored passthrough fixture keys: size_state, persistent, activate_condensed_tool, activate_global_map, tstatcatcher_stats.

## 6. SortRow
File: `transform/sort_row.py`. Register: `("SortRow","tSortRow")` (26). No dataclass.

| key | type | default | required | enum | line |
|---|---|---|---|---|---|
| criteria | list[dict] | [] | YES non-empty (47) | - | 46 |
| external | bool | False | no | logged only | 87 |

criteria[] (94,102-104, validated 51-67): column(str, req 52), sort_type(str,"alpha", enum `_VALID_SORT_TYPES` {num,alpha,date} validated 57), order(str,"asc", enum `_VALID_ORDERS` {asc,desc} validated 63).

## 7. UniqueRow
File: `aggregate/unique_row.py`. Register: `("UniqueRow","tUniqRow","tUniqueRow","tUnqRow")` (40). No dataclass. `_validate_config` weak (only key_columns is-list, 67).

| key | type | default | required | enum | line |
|---|---|---|---|---|---|
| key_columns | list[dict\|str] | [] | must be list if present (67) | - | 91 |
| keep | str\|False | "first" | no | {first,last,False} NOT validated | 92 |
| case_sensitive | bool | True | no | - | 93 |
| output_duplicates | bool | True | no | - | 94 |
| is_reject_duplicate | bool | True | no | - | 95 |
| only_once_each_duplicated_key | bool | False | no | doc-missing | 96 |

key_columns[] (101-106): dict {column:str, case_sensitive:bool(default=global)} OR plain str.

## 8. ConvertType
File: `transform/convert_type.py`. Register: `("ConvertType","tConvertType")` (86). No dataclass. **NO FIXTURE exists** (docstring is accurate here). `_validate_config` type-checks only (108-119).

| key | type | default | required | enum | line |
|---|---|---|---|---|---|
| autocast | bool | False | no | - | 138 |
| emptytonull | bool | False | no | - | 139 |
| dieonerror | bool | False | no | distinct from base die_on_error | 140 |
| manualtable | list[{input_column,output_column(default=input_column)}] | [] | must be list (108) | - | 141 |

Target-type names via `output_schema` (not manualtable), `_TALEND_TO_PANDAS` (40-58): int/integer/long/short/byte->int64; float/double/big_decimal/bigdecimal->float64; boolean/bool->bool; string/str->object; date/datetime/timestamp->datetime64[ns]; object->object.

## Authoring recommendation
- **tMap**: introspect the 7 dataclasses, then hand-overlay (column date_pattern->pattern + operator drift; inject the 4 mode enums; mark no-op/passthrough keys). Add a drift test: dataclass fields superset of converter-emitted keys.
- **FilterRows / AggregateRow / SortRow**: hand-curated manifest; enums are GOLD - reference the live module constants (`_OPERATOR_MAP`, `_SUPPORTED_FUNCTIONS`, `_VALID_SORT_TYPES`/`_VALID_ORDERS`) via enum_ref so they never drift.
- **FileInputDelimited / FileOutputDelimited**: hand-curated; required = filepath; FileOutput csvrowseparator enum from `_CSV_ROW_SEPARATORS` (soft/unenforced). Prune stale docstring keys.
- **UniqueRow**: hand-curated; `_validate_config` weak; `keep` enum hand-sourced; add doc-missing only_once_each_duplicated_key.
- **ConvertType**: fully hand-curated from source (docstring accurate); no fixture to drift-check.

Enums reliably in constants (use enum_ref): FilterRows operator, AggregateRow function, SortRow sort_type/order, FileOutputDelimited csvrowseparator. Hand-sourced enums: tMap modes, UniqueRow keep.
