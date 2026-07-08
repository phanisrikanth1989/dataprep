# Component config reference (code-verified)

## AggregateRow
Aliases: tAggregateRow
- `groupbys`: type=list; default=[]
  items:
    - `input_column`: type=str; REQUIRED
    - `output_column`: type=str; REQUIRED
- `operations`: type=list; default=[]
  items:
    - `function`: type=str; REQUIRED; one of "avg", "count", "count_distinct", "first", "last", "list", "list_object", "max", "median", "min", "population_std_dev", "std", "sum", "union", "variance"
    - `input_column`: type=str; REQUIRED
    - `output_column`: type=str
    - `ignore_null`: type=bool
- `list_delimiter`: type=str; default=','
- `use_financial_precision`: type=bool; default=True

## ConvertType
Aliases: tConvertType
- `autocast`: type=bool; default=False
- `emptytonull`: type=bool; default=False
- `dieonerror`: type=bool; default=False
- `manualtable`: type=list; default=[]
  items:
    - `input_column`: type=str; REQUIRED
    - `output_column`: type=str

## FileInputDelimited
Aliases: tFileInputDelimited
- `filepath`: type=str; default=''; REQUIRED
- `fieldseparator`: type=str; default=';'
- `row_separator`: type=str; default='\\n'
- `encoding`: type=str; default='ISO-8859-15'
- `header_rows`: type=int; default=0
- `footer_rows`: type=int; default=0
- `limit`: type=str; default=''
- `remove_empty_row`: type=bool; default=True
- `csv_option`: type=bool; default=False
- `csv_row_separator`: type=str; default='\\n'
- `escape_char`: type=str; default='"'
- `text_enclosure`: type=str; default='"'
- `trim_all`: type=bool; default=False
- `trim_select`: type=list; default=[]
  items:
    - `column`: type=str
    - `trim`: type=bool
- `check_fields_num`: type=bool; default=False
- `check_date`: type=bool; default=False
- `die_on_error`: type=bool; default=False
- `uncompress`: type=bool; default=False
- `split_record`: type=bool; default=False
- `random`: type=bool; default=False
- `advanced_separator`: type=bool; default=False
- `enable_decode`: type=bool; default=False

## FileOutputDelimited
Aliases: tFileOutputDelimited
- `filepath`: type=str; default=''; REQUIRED
- `csv_option`: type=bool; default=False
- `include_header`: type=bool; default=False
- `append`: type=bool; default=False
- `create_directory`: type=bool; default=True
- `split`: type=bool; default=False
- `split_every`: type=str; default='1000'
- `delete_empty_file`: type=bool; default=False
- `file_exist_exception`: type=bool; default=True
- `os_line_separator`: type=bool; default=True
- `streamname`: type=str; default='outputStream'
- `fieldseparator`: type=str; default=';'
- `row_separator`: type=str; default='\\n'
- `encoding`: type=str; default='ISO-8859-15'
- `escape_char`: type=str; default='"'
- `text_enclosure`: type=str; default='"'
- `csvrowseparator`: type=str; default='LF'
- `compress`: type=bool; default=False
- `usestream`: type=bool; default=False
- `row_mode`: type=bool; default=False
- `flushonrow`: type=bool; default=False
- `advanced_separator`: type=bool; default=False

## FilterRows
Aliases: FilterRow, tFilterRow, tFilterRows
- `use_advanced`: type=bool; default=False
- `advanced_cond`: type=str; default=''
- `logical_op`: type=str; default='&&'; one of "&&", "||", "AND", "OR"
- `conditions`: type=list; default=[]
  items:
    - `column`: type=str; REQUIRED
    - `operator`: type=str; REQUIRED; one of "!=", "<", "<=", "==", ">", ">=", "CONTAINS", "ENDS_WITH", "IS_NOT_NULL", "IS_NULL", "LENGTH_GT", "LENGTH_LT", "MATCHES", "NOT_CONTAINS", "STARTS_WITH"
    - `function`: type=str
    - `value`: type=str

## Map
Aliases: tMap
- `inputs`: type=dict; REQUIRED
- `outputs`: type=list; REQUIRED
  items:
    - `name`: type=str; REQUIRED
    - `is_reject`: type=bool
    - `inner_join_reject`: type=bool
    - `catch_output_reject`: type=bool
    - `activate_filter`: type=bool
    - `filter`: type=str
    - `columns`: type=list; REQUIRED
      items:
        - `name`: type=str
        - `expression`: type=str
        - `type`: type=str
        - `nullable`: type=bool
        - `length`: type=int
        - `precision`: type=int
        - `date_pattern`: type=str
        - `pattern`: type=str
        - `operator`: type=str
- `variables`: type=list; default=[]
- `die_on_error`: type=bool; default=True
- `enable_auto_convert_type`: type=bool; default=False
- `label`: type=str; default=''

## PyMap
Aliases: (none -- non-Talend, pure-Python map-family)
- `inputs`: type=dict; REQUIRED -- `{main:{name}, lookups:[{name, join_mode, matching_mode, lookup_mode, join_keys:[{lookup_column, expression}]}]}`. Nested mode VALUES are not schema-enforced (the validator does not recurse); engine-recognized: join_mode {LEFT_OUTER_JOIN, INNER_JOIN}; matching_mode {UNIQUE_MATCH, FIRST_MATCH, LAST_MATCH, ALL_MATCHES}; lookup_mode {LOAD_ONCE, RELOAD_AT_EACH_ROW}. Engine requires inputs.main.name, and each lookup's name + join_keys[lookup_column,expression] + join_mode.
- `outputs`: type=list; REQUIRED
  items:
    - `name`: type=str; REQUIRED
    - `is_reject`: type=bool
    - `inner_join_reject`: type=bool
    - `activate_filter`: type=bool
    - `filter`: type=str
    - `columns`: type=list; REQUIRED
      items:
        - `name`: type=str
        - `expression`: type=str (plain Python, evaluated in a SANDBOXED namespace: pd/np/re/datetime/Decimal/json/math; NO os/sys/open/eval/exec -- surfaced at the human gate)
        - `type`: type=str
        - `nullable`: type=bool
        - `length`: type=int
        - `precision`: type=int
        - `date_pattern`: type=str
- `variables`: type=list; default=[]
- `die_on_error`: type=bool; default=True
- `enable_auto_convert_type`: type=bool; default=False
- `label`: type=str; default=''
- LANDMINE: use `float` (not `decimal`) for numeric columns used in arithmetic -- a `decimal` column arrives as pandas StringDtype and would break e.g. `quantity * price`.

## SchemaComplianceCheck
Aliases: tSchemaComplianceCheck
- `schema`: type=list; REQUIRED -- the FLOW column list (normally flow-supplied, not hand-authored)
  items:
    - `name`: type=str; REQUIRED
    - `type`: type=str; REQUIRED
    - `nullable`: type=bool
    - `length`: type=int
    - `date_pattern`: type=str
- `check_all`: type=bool; default=True
- `check_another`: type=bool; default=False
- `checkcols`: type=list; default=[]
  items:
    - `column`: type=str
    - `selected_type`: type=str
    - `date_pattern`: type=str
    - `nullable`: type=bool
    - `max_length`: type=bool (a Talend checkbox flag, NOT the length value -- the actual length check uses the schema column's `length`)
- `strict_date_check`: type=bool; default=False (enforce date_pattern on datetime columns)
- `all_empty_are_null`: type=bool; default=True
- `empty_null_table`: type=list; default=[]
  items:
    - `column`: type=str
    - `empty_is_null`: type=bool
- `check_string_by_byte_length`: type=bool; default=False
- `charset`: type=str; default=''
- `customer` / `sub_string` / `fast_date_check` / `ignore_timezone`: type=bool; default=False (DEFERRED/no-op -- logged as WARNING when true)

## SortRow
Aliases: tSortRow
- `criteria`: type=list; default=[]; REQUIRED
  items:
    - `column`: type=str; REQUIRED
    - `sort_type`: type=str; one of "alpha", "date", "num"
    - `order`: type=str; one of "asc", "desc"
- `external`: type=bool; default=False

## UniqueRow
Aliases: tUniqRow, tUniqueRow, tUnqRow
- `key_columns`: type=list; default=[]
- `keep`: type=any; default='first'; one of "first", "last", false
- `case_sensitive`: type=bool; default=True
- `output_duplicates`: type=bool; default=True
- `is_reject_duplicate`: type=bool; default=True
- `only_once_each_duplicated_key`: type=bool; default=False
