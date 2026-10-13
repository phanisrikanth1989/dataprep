# v1 delimited files: what it holds in memory and what it writes (observed)

Date: 2026-10-05. Versions: pandas 3.0.5, Python 3.14.6 (numpy 2.5.2, pyarrow
25.0.0). Everything below was observed on one Mac (macOS 26.6.2, arm64);
nothing was run on the RHEL servers or against another pandas.

- What ran: the v1 engine (`src/v1`) on 592 small jobs, FileInputDelimited
  feeding FileOutputDelimited, loaded from job JSON modelled on
  `tests/talend_xml_samples/converted_jsons/Job_tFileInputDelimited_0.1.json`,
  with `java_config.enabled` false and no `{{java}}` string.
- Evidence: `probes/probe_v1_delimited_bytes.py`, run from the repo root with
  `.venv/bin/python .scratch/engine-v2/research/probes/probe_v1_delimited_bytes.py`.
  The ids in the `case` column are printed in brackets in its output, each
  with the full input bytes, config, held frame, reject frame and output
  bytes. In an id, `*` and `{a,b}` stand for several ids and `6.01-6.04` is a
  range.
- Provenance: an observation says what v1 does with this pandas on this Mac.
  `pyproject.toml` allows `pandas>=2.0,<4` and CLAUDE.md says 3.0.1; the
  installed build is 3.0.5. Rows marked (pandas) come from pandas, not from
  v1's own code, and are the likeliest to differ elsewhere. All of it is
  provisional for the target servers until the probe is re-run there.
- `where` cites v1 at the commits that last touched each file: FID =
  `src/v1/engine/components/file/file_input_delimited.py` (cf80a888), FOD =
  `src/v1/engine/components/file/file_output_delimited.py` (69ea03df), BC =
  `src/v1/engine/base_component.py` (d572ba8f).
- Baseline config: the key sets the converter emits, with `fieldseparator`
  `;`, `encoding` UTF-8 on both sides, reader `die_on_error` false and
  `remove_empty_row` true, writer `os_line_separator` true, `include_header`
  false and `file_exist_exception` true. The `config` column lists only what
  differs. The writer's `schema.input` copies the reader's `schema.output`
  and its `schema.output` is `[]` (as the converter emits) unless stated.
  "plain" means `csv_option` false, "csv" means `csv_option` true.
- Notation: bytes are written as in a Python bytes literal (`\n`, `\xe9`,
  `\\` for one backslash). "held" is the frame the reader hands the writer,
  shown as Python reprs (`<NA>`, `nan`, `NaT`). Schema shorthand is
  `name:type`, with `!` for nullable false, `#n` for precision n and
  `@pattern` for date_pattern.

## How the reader converts (needed to read the tables)

The reader loads every field as text, then converts each non-`str` schema
column on one of three paths. The same text can come out differently on each.

- Path A, vectorized (the default): pandas converts the whole column at once
  (FID:751-754, 828-855). `Decimal` is left as text here (FID:855).
- Path B, per-row fallback: if A raises for any one value of a column, every
  value of that column is converted by Python instead (`int(float(x))`,
  `float(x)`, `datetime.strptime`) and the failing rows are rejected
  (FID:755-790, 1036-1070). Texts that push an int or float column onto B:
  whitespace only, `NaN`, `nan`, `null`, `NA`, `None`, `""`, `1_000`, `1,000`,
  `0x1A`, other junk [3.vec.int, 3.vec.float]. An empty field does not.
- Path C, chunked: when `check_fields_num` or `check_date` is true, every
  column of every row goes through that same Python conversion (FID:703-713,
  857-998).

Afterwards the base class coerces again (BC:981-1056, 1177-1261): int to
`Int64` or `int64`, Decimal text to `Decimal` then quantize to `precision`,
float rounding to `precision`, and the nullable check.

Two reader steps, the control-character scrub (FID:262) and `trim_all`
(FID:647), pick their columns with `select_dtypes(include=["object"])`. Text
columns are dtype `str` here, and pandas 3.0.5 still returns them for
`object` only "for backward compatibility", with a deprecation warning on
every run (section 0 of the probe output). Both steps worked in every case
below; on a pandas without that shim they would silently do nothing.

## 1. Types on read and write

| case | input | config | observed | where |
|---|---|---|---|---|
| 1.01 | `a;1;1.5;true;2024-01-31;12.345\n` | `s:str, i:int, f:float, b:bool, d:datetime@%Y-%m-%d, m:Decimal#2`, all nullable | held dtypes: `str` (pandas `StringDtype(na_value=nan)`, pyarrow storage), `Int64`, `float64`, `bool`, `datetime64[us]`, `object` holding `decimal.Decimal('12.35')`. Written `a;1;1.5;true;2024-01-31;12.35\n` | FID:405-416, 828-855; BC:1219-1251 |
| 1.02 | same | every column nullable false | int is held as numpy `int64`; the other dtypes and the bytes are the same | BC:1221-1226 |
| 1.03, 8.04 | same | writer `schema.input` empty, or not listing the column | no formatting: Python `str()` of the held value: `True`, `2024-01-31 00:00:00`, `12.35` | FOD:426-428, 834-856 |
| 1.04 | same | writer `schema.input` names in another case (`B`, `D`, `M`) | same as no schema: the writer matches its schema to the frame by exact column name | FOD:433-434, 483-484, 549-550 |
| 1.05 | `true false 1 0 yes no True False Yes No YES NO` | `bool` | exactly these twelve spellings convert on path A; written `true` / `false` | FID:832-844; FOD:555-565 |
| 1.06 | `TRUE`, `FALSE`, ` true `, empty, `Y`, `N`, `t`, `f`, `on`, `2` | `bool` | any spelling outside the twelve sends the column to path B: there `true/1/yes/false/0/no` match in any case with spaces stripped; `Y N t f on 2` are rejected; empty becomes `False` | FID:839-843, 1054-1062 |
| 1.07, 1.08 | `31/01/2024`; `2024-01-31 10:11:12` | `%d/%m/%Y`; `%Y-%m-%d %H:%M:%S` | `date_pattern` is Python strptime/strftime dialect on both sides; these round-trip to the same text | FID:851-853; FOD:448-449 |
| 1.09 | `2024-01-31 10:11:12.123`, `...12.5` | `%Y-%m-%d %H:%M:%S.%f` | written with six fraction digits: `.123000`, `.500000` | FOD:449 |
| 1.10 | `01-FEB-2024` | `%d-%b-%Y` | accepted; written `01-Feb-2024` | FOD:449 |
| 1.11 | `2024-1-5`, ` 2024-02-01 `, `2024-02-30`, `2024-01-31 10:00:00`, `31/01/2024` | `%Y-%m-%d` | first two accepted and written `2024-01-05`, `2024-02-01`; the other three rejected | FID:853, 1063-1066 |
| 1.12, 1.13 | `2024-01-31` | reader pattern `yyyy-MM-dd` (Java dialect) | every row rejected (`time data '2024-01-31' does not match format 'yyyy-MM-dd'`), output is a 0-byte file; with `die_on_error` true the job fails | FID:853, 1066 |
| 1.14 | `2024-01-31` | writer pattern `yyyy-MM-dd` | the literal text `yyyy-MM-dd` is written for every non-null row | FOD:449 |
| 1.15, 1.19 | datetime values | writer column has no `date_pattern` | `str(Timestamp)`: `2024-01-31 00:00:00`, `1999-12-31 01:02:03.500000` | FOD:438-439, 856 |
| 1.16 | `01/02/2024`, `31/01/2024` | reader has no `date_pattern` | guessed per value: 2 January and 31 January in one column (pandas warns) | FID:854 (pandas) |
| 1.17 | `0001-01-01`, `0999-12-31`, `1677-09-20`, `2262-04-12`, `9999-12-31` | `%Y-%m-%d` | all parse; years below 1000 are written unpadded: `1-01-01`, `999-12-31` | FOD:449 (pandas) |
| 1.18 | `2024-01-31` | reader `%Y-%m-%d`, writer `%d/%m/%Y %H:%M:%S` | `31/01/2024 00:00:00`: the writer's own pattern decides the text | FOD:437-449 |
| 1.20 | str column: `2024-01-31`, `31/01/2024`, `junk` | writer declares `datetime@%Y-%m-%d` | the writer re-parses the text with its pattern; values that do not match are written as empty fields, silently | FOD:441-450 |
| 1.21, 1.22 | Decimal held `1.01`, `7.00`, `30200.00` | writer `Decimal#4`; writer `Decimal` without precision | `1.0100`, `7.0000`; without precision trailing zeros go: `1.01`, `7`, `30200` | FOD:492-523 |
| 1.23 | Decimal held `1.01`, `7.00` | writer declares `float` | `str(Decimal)`: `1.01`, `7.00` | FOD:490-491 |
| 1.24 | float held 2.005, 2.675, 3.0, nan | writer declares `Decimal#2` | `2.00`, `2.67`, `3.00`, empty (binary float formatting, not half-up) | FOD:498-508 |
| 1.25-1.27 | str held `7.10`, `abc`, empty, `1e3`, `TRUE`, `None` | writer declares `Decimal#2` / `Decimal` / `bool` | `#2`: unchanged. No precision: `7.1`, `1000`, rest unchanged. `bool`: `TRUE` becomes `true`, `None` becomes empty, rest unchanged | FOD:498-523, 555-565 |
| 1.28 | `12345;abcdefghij` | `length` 1 on the int, 3 on the str | `length` is ignored | BC:928-930 |

## 2. Missing values

The matrix file is `1;<good>\n2;<text>\n` with schema `id:int, v:<type>`
(Decimal has precision 2). "rejected" means row 2 goes to the reject flow
and is absent from the output. Plain and csv mode gave the same result for
every cell except the text `""` (two quote characters), as noted.

| case | input (text in `v`) | config | observed (held, then written) | where |
|---|---|---|---|---|
| 2.plain.str.*, 2.csv.str.* | any of the seven texts | `str` | never null: held verbatim (`''`, `'   '`, `'NaN'`, `'null'`, `'NA'`, `'None'`) and written back byte for byte. `""` is two quote characters in plain mode and empty text in csv mode | FID:413-415, 748 |
| 2.plain.int.empty | empty | `int` | `<NA>`; written as an empty field | FID:829; BC:1220-1224 |
| 2.plain.int.spaces | `   ` | `int` | `<NA>`; empty field (the column is on path B) | FID:1043-1045 |
| 2.plain.int.NaN | `NaN` | `int` | rejected: `TYPE_CONVERSION`, `Column 'v': cannot convert float NaN to integer` | FID:829, 1051 (pandas) |
| 2.plain.int.{null,NA,None,quoted} | `null`, `NA`, `None`, plain-mode `""` | `int` | rejected: `Column 'v': could not convert string to float: 'null'` | FID:1051 |
| 2.plain.float.{empty,spaces,NaN} | empty, `   `, `NaN` | `float` | `nan`; empty field (the text `NaN` is not written back) | FID:831, 1053; FOD:848-852 |
| 2.plain.float.{null,NA,None,quoted} | as for int | `float` | rejected, same message as int | FID:1053 |
| 2.plain.bool.{empty,spaces} | empty, `   ` | `bool` | `False`; written `false`: a missing bool becomes false | FID:1043-1045; BC:1231-1232 |
| 2.plain.bool.{NaN,null,NA,None,quoted} | as named | `bool` | rejected: `Column 'v': Cannot convert 'NaN' to bool` | FID:1062 |
| 2.plain.datetime.{empty,spaces,NaN} | empty, `   `, `NaN` | `datetime@%Y-%m-%d` | `NaT`; empty field | FID:853, 1043-1045; FOD:450 |
| 2.plain.datetime.{null,NA,None,quoted} | as named | same | rejected: `Column 'v': time data 'null' does not match format '%Y-%m-%d'` | FID:1066 |
| 2.plain.Decimal.{empty,spaces} | empty, `   ` | `Decimal#2` | not null: held as the text itself (`''`, `'   '`) inside the object column; written back as is | FID:855; BC:1246-1249 |
| 2.plain.Decimal.NaN | `NaN` | `Decimal#2` | `Decimal('NaN')`; written `NaN` | BC:1247 |
| 2.plain.Decimal.{null,NA,None,quoted} | as named | `Decimal#2` | no reject: held as text and written verbatim (`null`, `NA`, `None`, `""`) | BC:1248-1249 |
| 2.csv.*.quoted | `""` | csv, any type | same as the empty field for that type | FID:561-571 |
| 2.91 | second row `;;;;;y` | `i:int, f:float, b:bool, d:datetime@%Y-%m-%d, m:Decimal#2, s:str`, path A | held `(<NA>, nan, False, NaT, '', 'y')`; written `;;false;;;y\n` | as above |
| 2.92, 2.93 | same | `check_fields_num` true (path C) | the Decimal cell is `<NA>` and is written as the five characters `<NA>`, with or without precision: `;;false;;<NA>;y\n` | FID:1043-1045; BC:1237-1241; FOD:505-506, 520-521 |
| 2.91, 2.92, 5.25, 6.92 | - | what a null is, by held dtype | `Int64`: `<NA>`. `float64`: `nan`. `datetime64[us]`: `NaT`. `bool`: none (an empty value is `False`). Decimal column: empty text on paths A and B, `<NA>` on path C. `str`: an empty field is empty text, not null; `nan` appears only for a field missing from a short row (csv mode or the python parser). Every null is written as an empty field, except the Decimal `<NA>` | FOD:848-852 |
| 2.95 | nulls and empty text | writer csv | every null and every empty text is written `""`: `"2";"";"false";"";"";""\n` | FOD:778 |
| 2.notnull.str.* | empty, two spaces | `str!`, any `die_on_error` | not a violation: kept and written | BC:1031 |
| 2.notnull.{int,float,datetime}.empty.die=False, 2.90 | empty | `int!` / `float!` / `datetime!`, `die_on_error` false | rejected by the base class: `SCHEMA_VIOLATION`, `Column 'v': non-nullable column has null`. The reject row carries typed values, `(2, nan, 'b', ...)`, written `2;;;b;SCHEMA_VIOLATION;Column 'n': non-nullable column has null`. For int the surviving rows stay float64 and are written `5.0` | BC:912-918, 959-963, 1226, 1255-1259 |
| 2.notnull.{int,float,datetime}.empty.die={True,absent} | empty | same, `die_on_error` true or key absent | job fails: `Column 'v' has NULL values but is not nullable`; no output file | BC:234, 1031-1034 |
| 2.notnull.{int,float,datetime}.spaces.die={False,absent}, 2.notnull.bool.*.die={False,absent} | two spaces; for bool also empty | `!` types, `die_on_error` false or key absent | rejected by the reader: `TYPE_CONVERSION`, `Column 'v': Empty value for non-nullable column`; the reject row carries the raw text `('2', '  ', 'b', ...)` | FID:173, 1043-1048 |
| 2.notnull.{int,float,datetime}.spaces.die=True, 2.notnull.bool.*.die=True | same | `die_on_error` true | job fails: `Schema/coercion failed for 1 row(s); first error: Column 'v': Empty value for non-nullable column` | FID:305-310 |
| 2.notnull.Decimal.* | empty, two spaces | `Decimal!#2`, any `die_on_error` | no violation on paths A and B: the text is kept and written; job succeeds | BC:1031, 1246-1249 |
| 2.94 | empty | `Decimal!#2`, path C | rejected: `Cannot convert '' to Decimal for column 'm' - Line: 2` | FID:1048, 968-973 |

## 3. Numbers

The one-value files are `x;<text>\n` with schema `k:str, v:<type>`
[3.one.<type>.NN]; the column cases put one value per row [3.cNN, 3.kNN].
`int!` is int with nullable false.

| case | input | config | observed (written field) | where |
|---|---|---|---|---|
| 3.one.*.{01,02} | `1`; `1.0` | str / int / float / Decimal#2 / Decimal | `1`, `1`, `1.0`, `1.00`, `1`; and `1.0`, `1`, `1.0`, `1.00`, `1` | FID:829-831; BC:1158-1170; FOD:504, 518-519 |
| 3.one.*.03 | `1.50` | same five | str `1.50`; int: the column becomes float64 (a warning is logged) and writes `1.5`; float `1.5`; Decimal#2 `1.50`; Decimal `1.5` | BC:1224, 1255-1259 |
| 3.one.int!.03, 3.c09 | `1.50`, `2.9`, `-2.9` | `int!` | truncated toward zero: `1`, `2`, `-2` | BC:1226 |
| 3.c02 | `1`, `1.50` | `int` | one fractional value makes the whole column float: `1.0`, `1.5` | BC:1224, 1255-1259 |
| 3.c07, 3.k01 | `1.50`, `2.9` (3.c07 also `-2.9`) | `int` on path B (a whitespace-only value in the column) or path C | truncated: `1`, `2` (`-2`) | FID:1051 |
| 3.one.*.04 | `30200.00` | five types | `30200.00`, `30200`, `30200.0`, `30200.00`, `30200` | FOD:518-519 |
| 3.one.*.05 | `1e5` | five types | `1e5`, `100000`, `100000.0`, `100000.00`, `100000` | as above |
| 3.one.*.06, 3.c03 | `1234567890123456789` (19 digits) | five types | str, Decimal#2 (`...789.00`) and Decimal exact; float `1.2345678901234568e+18`; int exact when every value in the column is integer text | FID:829 |
| 3.c04, 3.c05, 3.c06, 3.k01 | same value, in an `int` column | beside an empty value, beside `1.0`, on path B, or on path C | `1234567890123456768`: the column passes through float64 | FID:829, 1051; BC:1220-1224 |
| 3.one.int.{07,08,09} | `9223372036854775807`; `9223372036854775808`; 23 digits | `int` | exact; held uint64 and written exact; float64 `1.2345678901234568e+22` | BC:1224, 1255-1259 |
| 3.one.int!.{08,09} | `9223372036854775808`; 23 digits | `int!` | `-9223372036854775808`; `9223372036854775807` (on this arm64 Mac) | BC:1226 (numpy) |
| 3.one.*.10, 3.c10, 3.c11, 3.k02 | `-0` | five types | str `-0`; int `0`; Decimal#2 `-0.00`; Decimal `-0`; float `0.0` when it is the only value in the column, `-0.0` beside decimal values on path A and on paths B and C | FID:831 (pandas) |
| 3.one.*.11 | `-0.0` | five types | `-0.0`, `0`, `-0.0`, `-0.00`, `-0` | as above |
| 3.one.*.12, 3.c13, 3.c14 | `007` (3.c14 also `00`) | five types | str keeps `007`; int `7` (and `0` for `00`); float `7.0`; Decimal#2 `7.00`; Decimal `7` | FID:748, 829 |
| 3.one.*.{13,14} | `+5`; ` 7 ` | int, float, Decimal | `5`, `7`; `5.0`, `7.0`; Decimal#2 `5.00`, `7.00` (str keeps the text as is) | FID:829 |
| 3.one.*.15 | `1_000` | int, float, Decimal#2 | accepted: `1000`, `1000.0`, `1000.00` (Python parsing on path B, and `Decimal`) | FID:1051-1053; BC:1247 |
| 3.one.*.{16,17} | `1,000`; `0x1A` | int, float; Decimal | int and float: rejected (`could not convert string to float: '1,000'`); Decimal: held as text, written verbatim | FID:1051; BC:1248-1249 |
| 3.k04 | `1.234,56`, `7,5` | `advanced_separator` true, `decimal_separator` `,`, `thousands_separator` `.` on both sides | the keys are ignored (warning logged): both rows rejected | FID:176-181 |
| 3.one.*.18, 3.float.{13,14} | `inf`, `-inf`, `nan` | int / float / Decimal#2 | int column becomes float64 `inf`; float `inf`, `-inf`, and `nan` written empty; Decimal `Infinity` | BC:1255-1259; FOD:848-852 |
| 3.float.01-12 | `0.1`, `2.50`, `1e15`, `1e16`, `1e22`, `0.0001`, `0.00001`, `5e-324` | `float` | Python float repr: `0.1`, `2.5`, `1000000000000000.0`, `1e+16`, `1e+22`, `0.0001`, `1e-05`, `5e-324` | FOD:856 |
| 3.float.02, 3.c10 | `0.30000000000000004`; `9345049367.241609` | `float`, path A | not correctly rounded: `0.3`; `9345049367.241608` | FID:831 (pandas) |
| 3.c11, 3.c12, 3.k02 | same two values | `float` on path B (column also holds `   ` or `NaN`) or path C | exact: `0.30000000000000004`; `9345049367.24161` | FID:1053 |
| 3.parse | 20000 random decimal texts per row | `pandas.to_numeric` against Python `float()` | up to 15 significant digits: 0 differ. 16 digits: about 3% differ. 17 digits: 28% to 60% differ | (pandas) |
| 3.floatprec0.* | `0.5`, `1.5`, `2.5`, `2.675`, `-0.004` | `float#0` | rounded on read, half to even: `0.0`, `2.0`, `2.0`, `3.0`, `-0.0` | BC:933-938, 1046-1049 |
| 3.floatprec2.* | `1.005`, `2.675`, `1.234567`, `-0.004` | `float#2` | `1.0`, `2.68`, `1.23`, `-0.0` | BC:933-938, 1046-1049 |
| 3.intprec0.* | `1`, `1.50` | `int#0` | precision has no effect on int: `1`, `1.5` | BC:1040-1046 |
| 3.dec.Decimal#0.* | `1.50`, `0.5`, `2.5`, `-1.005` | `Decimal#0` | quantized on read, half up: `2`, `1`, `3`, `-1` | BC:1158-1170 |
| 3.dec.Decimal#{2,4}.* | `1.005`, `2.675`, `-1.005`, `1e5`, `1E-7`, `100`, `1.50` | `Decimal#2`; `Decimal#4` | `1.01`, `2.68`, `-1.01`, `100000.00`, `0.00`, `100.00`, `1.50`; with 4: `1.0050`, `2.6750`, `-1.0050`, `100000.0000`, `0.0000`, `100.0000`, `1.5000` | BC:1158-1170; FOD:504 |
| 3.dec.Decimal.* | `1.50`, `0.00`, `100`, `1e5`, `1E-7`, `-0` | `Decimal`, no precision | held exactly as typed; trailing zeros stripped on write: `1.5`, `0`, `100`, `100000`, `0.0000001`, `-0` | FOD:510-523 |
| 3.dec.*.{12,13} | `123456789012345678901234567890.125`; `0.1234567890123456789012345678901` | Decimal with more than 28 significant digits | `#2` writes `...890.12` (quantize is skipped, the format rounds half-even); no precision writes `123456789012345678901234567900` and `0.1234567890123456789012345679` | BC:1171-1172; FOD:504, 519 |
| 3.k03 | `NaN` | `Decimal#2`, path C | held `<NA>`, written `<NA>` | BC:1240-1241; FOD:505-506 |

## 4. Bad values

Cases 4.01 to 4.07 share the input
`1;alice;2024-01-31;10.5\nx2;bob;2024-02-01;20\n3;carol;2024-02-30;30\n4;dave;2024-03-01;\n`
and schema `id:int, name:str, d:datetime@%Y-%m-%d, amt:float`, with the reject
flow wired to a second FileOutputDelimited (header on) except in 4.04. Job
status is what `ETLEngine.execute()` returns: `success`, `failed` (a
component failed) or `error` (the run ended in a runtime stall).

| case | input | config | observed | where |
|---|---|---|---|---|
| 4.01 | shared | `die_on_error` false | job `success`; output `1;alice;2024-01-31;10.5\n4;dave;2024-03-01;\n`; reader NB_LINE 4, OK 2, REJECT 2. Reject frame: columns `id, name, d, amt, errorCode, errorMessage`, all dtype `str`, data columns carry the raw field text. Reject file: `id;name;d;amt;errorCode;errorMessage\nx2;bob;2024-02-01;20;TYPE_CONVERSION;Column 'id': could not convert string to float: 'x2'\n3;carol;2024-02-30;30;TYPE_CONVERSION;Column 'd': day 30 must be in range 1..29 for month 2 in year 2024\n` | FID:755-775, 801 |
| 4.02 | shared | `die_on_error` true | job `failed`; reader error `[tFileInputDelimited_1] [tFileInputDelimited_1] Schema/coercion failed for 2 row(s); first error: Column 'id': could not convert string to float: 'x2'`; both writers `skipped`; neither file is created | FID:305-310 |
| 4.03 | shared | `die_on_error` key absent | same as false | FID:173 |
| 4.04 | shared | no reject flow wired | same output; the rejected rows are dropped; job `success` | - |
| 4.05 | shared | `check_fields_num` true (path C) | messages change form and gain a row number: `Cannot convert 'x2' to int for column 'id' - Line: 2`, `Cannot convert '2024-02-30' to datetime for column 'd' - Line: 3`. Row 4, whose last field is empty, is rejected too: `FIELD_COUNT`, `Field count mismatch: expected 4, got 3 - Line: 4` | FID:900-917, 964-976 |
| 4.06 | shared | `check_date` true (path C) | the bad date is `DATE_FORMAT`, `Date '2024-02-30' does not match pattern '%Y-%m-%d' for column 'd' - Line: 3` | FID:934-956 |
| 4.07 | shared | `check_date` true, `die_on_error` true | job `failed`: `Schema/coercion failed for 2 row(s); first error: Cannot convert 'x2' to int for column 'id' - Line: 2` | FID:305-310 |
| 4.16 | `h;h\nh;h\n1;a\n\nx;b\n` | `header_rows` 2, `check_fields_num` true | `Line: 2` for a value on file line 5: it counts data rows after the header skip and blank-line removal | FID:886-887 |
| 4.08 | `1;alice;2024-01-31;10.5\n` | clean data, reject flow wired | with no rejects the reject writer never runs; job status `error`: `Runtime stall detected: 1 components never executed ... tFileOutputDelimited_2 ... waiting on input flows [rej1]`. The main output is written; no reject file | src/v1/engine/output_router.py:137-138; src/v1/engine/executor.py:151-171 |
| 4.09 | `x;a;notadate;zz\n` | - | one reject row, naming only the first failing column in schema order (`id`) | FID:760-767 |
| 4.10 | `2;abc`, `3;1,000` | `m:Decimal!#2`, `die_on_error` true | no reject and no failure: held as text in the object column and written verbatim | BC:1246-1249 |
| 4.11 | `2;abc` | `m:Decimal#2`, `check_fields_num` true | the reader fails with `[<class 'decimal.ConversionSyntax'>]` although `die_on_error` is false; no output file | FID:963, 1070 |
| 4.12 | `q;b` in `id:int` | `die_on_error` given as the string `"false"` | treated as true: job `failed` | FID:173, 305 |
| 4.13, 4.14 | `1;a\n2;b;c\n` | `die_on_error` false / true | the read fails either way: `Failed to read file '<path>': Error tokenizing data. C error: Expected 2 fields in line 2, saw 3`; no output. Job status is `error` (stall on the writer) when false, `failed` (writer skipped) when true | FID:432-435 |
| 4.15 | input file absent | - | `File not found: '<path>'` | FID:185-188 |

## 5. Text

| case | input | config | observed | where |
|---|---|---|---|---|
| 5.01 | `1;"x";z\n2;say "hi";q\n3;"";""\n` | plain | quote characters are data on read and on write: output equals input | FID:413; FOD:823-832 |
| 5.02 | `1;"x;y";z\n2;p;q\n` | plain, 3 columns | the separator inside quotes still splits: line 1 has 4 fields and the 4th is dropped: `1;"x;y"\n2;p;q\n` | FID:462-465 |
| 5.03 | `1;p;q\n2;"x;y";z\n` | plain | read fails: `Error tokenizing data. C error: Expected 3 fields in line 2, saw 4` | FID:428-435 |
| 5.04 | `1;"x;y";z\n2;"say ""hi""";q\n3;"";""\n` | reader csv, writer plain | held `x;y`, `say "hi"`, `''`; written raw: `1;x;y;z\n2;say "hi";q\n3;;\n` | FID:561-571 |
| 5.05 | same | csv on both sides | `"1";"x;y";"z"\n"2";"say ""hi""";"q"\n"3";"";""\n` | FOD:759-778 |
| 5.06 | `1,"x;y","say ""hi"""\n2,"l1\nl2",q\n` | reader csv with `,`; writer plain with `;` | values holding the separator, a quote or a newline are written raw, unquoted: `1;x;y;say "hi"\n2;l1\nl2;q\n` | FOD:823-832 |
| 5.07, 5.08 | `1;"l1\nl2";z\n`; same with CRLF | csv on both sides | an embedded LF or CRLF stays in the field and is written inside the quotes | FID:559 |
| 5.09 | `1;x\ry;z\n2;p;q\n` | reader csv | a bare CR ends the row: three rows, `1;x;`, `y;z;`, `2;p;q` | FID:559-571 |
| 5.10 | `1;"l1\nl2";z\n2;p;q\n` | plain | the LF inside quotes splits the row; here the read then fails on field count | FID:428 |
| 5.11 | `1;ab"cd;z\n2;5" disk;q\n` | csv on both sides | a quote inside an unquoted field is data; written doubled: `"ab""cd"`, `"5"" disk"` | FOD:759-771 |
| 5.12 | `1;"abc;z\n2;p;q\n` | csv | an unterminated quote swallows the rest of the file into one field; the field count then mismatches the schema (see 8.12) | FID:571 |
| 5.13 | `1; "x;y";z\n` | csv | a space before the quote stops it being an enclosure: 4 fields | FID:571 |
| 5.14 | `1;'x;y';'it''s'\n2;"dq";z\n` | csv, `text_enclosure` and `escape_char` both `'`, both sides | held `x;y`, `it's`, `"dq"`; written `'1';'x;y';'it''s'\n'2';'"dq"';'z'\n` | FID:565-569; FOD:759-771 |
| 5.15 | `1;"say \\"hi\\"";"a\\\\b"\n2;"x;y";plain\\n\n` | csv, `escape_char` one backslash, both sides | held `say "hi"`, `a\\b`, and `plainn` (the escape character is consumed outside quotes too). Written with backslash-quote and a doubled backslash: `"1";"say \\"hi\\"";"a\\\\b"\n"2";"x;y";"plainn"\n` | FID:567-569; FOD:759-771 |
| 5.16, 5.17 | any | csv, `escape_char` of two backslashes | reader: `Failed to read file '<path>': "escapechar" must be a unicode character or None, not a string of length 2`. Writer: `Failed to write file ...` with the same reason, leaving a 0-byte output file | FID:596-599; FOD:729-732 |
| 5.18, 5.19 | any | csv, `text_enclosure` empty | the same two failures with `"quotechar" must be a unicode character or None, not a string of length 0` | as above |
| 5.20 | `1;'x';z\n` | plain, `text_enclosure` `'` | ignored on both sides | FID:413 |
| 5.21 | `1\|\|x\|y\|\|z\n` | plain, `fieldseparator` `\|\|`, both sides | split on the two-character text (a single `\|` is data); written joined with `\|\|` | FID:401-403; FOD:831 |
| 5.22 | `1\|\|x\n` | csv, `fieldseparator` `\|\|`, both sides | cut to its first character, with a warning: fields `1`, empty, `x`; written `"1"\|""\|"x"\n` | FID:203-208; FOD:361-366 |
| 5.23, 5.24 | `1\tx\tz\n`; `1.*x.*z\n` | `fieldseparator` `\\t` (backslash, t); `.*` | backslash-t text means TAB; `.*` is literal, not a regex | FID:403, 1014-1020 |
| 5.25 | `1, x, z\n2, p,q\n` | `fieldseparator` `, ` | row 2 has two fields; the third is null and written empty: `2, p,q, \n` | FID:401-403 |
| 5.26, 5.27 | `1;x;z\n` | `fieldseparator` empty | reader fails (`only single character unicode strings can be converted to Py_UCS4, got length 0`); the writer concatenates: `1xz\n` | FID:428; FOD:831 |
| 5.28-5.30 | CRLF file; CR-only file; LF file | plain, `row_separator` `\\n` or `\\r\\n` text | LF, CRLF and CR each end a row whichever of them the key names; no CR is left in the last field | FID:80, 349, 400-428 (pandas) |
| 5.31, 5.33 | `1;x;z@@2;p;q@@`; `h;h;h@@1;x;z@@2;p;q@@f;f;f` | plain, `row_separator` `@@` (5.33: header 1, footer 1) | split on `@@`; header and footer are counted in `@@` rows; a missing final separator is fine | FID:349-397 |
| 5.32 | `1;x\ny;z@@2;p;q@@` | plain, `row_separator` `@@` | an LF inside a row still splits it (rows are re-joined with LF and re-parsed); the read fails here | FID:372-390 |
| 5.34, 5.35 | `1;"x;y";z@@2;p;q@@` | csv, `csv_row_separator` `@@`; csv, `row_separator` `@@` | csv mode reads `csv_row_separator` only; `row_separator` is ignored there | FID:218-229 |
| 5.40-5.43 | `caf\xc3\xa9;\xe2\x82\xac5\n` (UTF-8) or `caf\xe9;\xa45\n` (ISO-8859-15) | both encodings named correctly | all four read/write combinations convert correctly | FID:411; FOD:811 |
| 5.46, 5.47, 7.75 | same | `encoding` key absent | the default is ISO-8859-15 on both sides | FID:160; FOD:275 |
| 5.44, 5.47 | the UTF-8 file | read as ISO-8859-15, written ISO-8859-15 | no error, but not byte-preserving: `\xc3\xa9` survives while `\xe2\x82\xac` comes out `\xe2 \xac` (byte 0x82 decodes to a C1 control, which the reader turns into a space) | FID:76, 262-266 |
| 5.45 | the ISO-8859-15 file | read as UTF-8 | no error: each undecodable byte becomes a space: `caf ; 5\n` | FID:93, 412, 262-266 |
| 5.48 | `ok;fine\n`, a row with two CJK characters, `y;late\n` | writer ISO-8859-15 | writer fails (`'charmap' codec can't encode characters in position 2-3`), job `failed`; the file keeps the rows before the bad one: `ok;fine\n` | FOD:729-732 |
| 5.49, 5.50 | `a\x01b\x1fc\x7fd`, 0x0b, 0x0c, U+0085, U+009F, U+FFFD, TAB, U+00A0; ISO-8859-15 bytes 0x80, 0x9f, 0xa0 | any text column | each control character, C1 character and U+FFFD becomes one space (`a b c d`); TAB and U+00A0 are kept. The pattern in the code covers U+0000-0008, 000B, 000C, 000E-001F, 007F-009F and U+FFFD | FID:76, 262-266 |
| 5.51, 5.52 | `ab\x00cd;x\n` | plain; csv | plain: the field is cut at the NUL (`ab`); csv: the NUL becomes a space (`ab cd`) | FID:428 (pandas); 262-266 |
| 5.53-5.55 | - | `encoding` `latin1` / `utf8`; `NOPE-1` | Python codec names are accepted (`latin1` is not ISO-8859-15: 0xa4 stays the currency sign); unknown: `unknown encoding: NOPE-1` (the writer leaves a 0-byte file) | FID:432-435; FOD:729-732 |
| 5.60, 5.61, 5.65, 5.66 | `\xef\xbb\xbfabc;x\n`; `\xef\xbb\xbf1;x\n` | plain, UTF-8 | the BOM is dropped (C parser, python parser and custom row separator alike); an int first column parses | FID:390, 428 (pandas) |
| 5.62-5.64 | same | csv, UTF-8 | the BOM stays as U+FEFF at the start of the first field: a str value keeps it and it is written back; an int first column rejects row 1; a quoted first field keeps its quotes as data | FID:559 |
| 5.67, 5.68 | same | ISO-8859-15 on both sides; `utf-8-sig` on both sides | ISO-8859-15: the three BOM bytes are data and are written back. `utf-8-sig`: stripped on read, written on output | FID:411; FOD:811 |

## 6. Rows

The header/footer file is `h1;h2;h3\nH1;H2;H3\n1;x;z\n2;p;q\n3;r;s\nf1;f2;f3\n`;
the empty-row file is `1;x;1.5\n\n;;\n  ; ;\t\n \n2;p;2.5\n` (a blank line, an
all-empty row, a whitespace-only row and a single-space line) with schema
`a:int, b:str, c:float`; the trim file is ` 1 ; x y ;  2.5 \n2;\tp\t;3\n3;   ;4\n`.

| case | input | config | observed | where |
|---|---|---|---|---|
| 6.01-6.04, 6.06 | header/footer file | `header_rows` 0, 1, 2, `"1"`; plain and csv | that many lines are skipped from the top; header text is never used for column names; a numeric string works | FID:161, 409, 574-578 |
| 6.05, 6.16 | same | `header_rows` 10; `footer_rows` 10 | no rows: a 0-byte output file, job `success` | FID:409-410, 429-431 |
| 6.07, 6.08 | `\nh;h;h\n1;x;z\n` | `header_rows` 1, plain and csv | a blank first line counts as the header: `h;h;h` is read as data | FID:409, 574-578 |
| 6.10-6.12 | header/footer file | `header_rows` 2, `footer_rows` 1 or 2; plain and csv | that many rows are dropped from the end | FID:410, 581-590 |
| 6.13, 6.14 | `1;x;z\n2;p;q\nf;f;f\n\n` | `footer_rows` 1, plain and csv | a blank last line counts as the footer: `f;f;f` is kept | FID:410, 581-590 |
| 6.15 | last line without a newline | `footer_rows` 1 | still dropped as the footer | FID:410 |
| 6.20-6.22 | header/footer file | `limit` `"2"`, `2`, `" 2 "` | the first 2 data rows | FID:233-240 |
| 6.23-6.26 | same | `limit` `"0"`, `"-1"`, `"abc"`, `"2.0"` | all rows: 0 and negatives mean no limit; non-integers are ignored with a warning | FID:269-277 |
| 6.27, 6.28 | same | `limit` 2 in csv; with `footer_rows` 2 | the first 2 rows after header and footer removal | FID:273, 421-422 |
| 6.29-6.31 | `\n1;x;z\n2;p;q\n3;r;s\n`; `;;\n1;x;z\n...` | `limit` 2 | the limit is taken before empty rows are removed. Plain with a blank first line: 2 rows. Csv with a blank first line: 1 row. Plain with a `;;` first line: 1 row | FID:269-286 |
| 6.40, 6.42 | empty-row file | `remove_empty_row` true, plain and csv | only the two data rows remain | FID:280-286 |
| 6.41, 6.49 | same; `1;x;1.5\n\n2;p;2.5\n` | `remove_empty_row` false, plain | the blank line and the single-space line are dropped anyway; `;;` and the whitespace row stay as rows: `;;\n; ;\n` | FID:405-416 (pandas) |
| 6.49b | `1;x;1.5\n\n2;p;2.5\n` | `remove_empty_row` false, csv | the blank line is a row of nulls, written `;;` | FID:605 |
| 6.43 | empty-row file | `remove_empty_row` false, csv | as 6.49b for the other rows, but the whitespace-only int value puts column `a` on path B, where the blank-line row is rejected (`cannot convert float NaN to integer`) | FID:755-775 |
| 6.44 | same | plus `check_date` true (path C) | the blank line is rejected carrying the text `nan` in every column; the single-space line is kept and its str field is written as `nan`: `;nan;` | FID:929 |
| 6.45, 6.57, 6.93 | - | reader `remove_empty_row`, `trim_all` or `csv_option` given as the string `"false"` | treated as true (rows removed; values trimmed; quotes parsed) | FID:164-173 |
| 6.46-6.48 | empty file; header only; last row without a newline | - | 0-byte output and `success`; the unterminated last row is read and written with a terminator | FID:429-431 |
| 6.50, 6.51 | trim file | `trim_all` false / true, schema int, str, float | numbers parse either way (`1`, `2.5`). str when false: ` x y `, `\tp\t`, `   `; when true: `x y`, `p`, and empty text (not null) | FID:646-649 |
| 6.52, 6.53 | trim file; `" 1 ";" x ";"  "\n` | `trim_all` true, all str; csv | every str column is trimmed, including text that was inside quotes | FID:646-649 |
| 6.54-6.56 | trim file | `trim_select` b only; an unknown column; `trim_all` true with `trim: false` entries | only columns listed with `trim: true` are trimmed; unknown names are ignored; `trim_all` wins over `trim: false` | FID:650-655 |
| 6.60, 6.61 | `1;x;1.5\n2;y\n3;z;3.5\n` | plain, `check_fields_num` false / true | false: the missing field is null, written `2;y;`. True: the row is rejected, `FIELD_COUNT`, `Field count mismatch: expected 3, got 2 - Line: 2`, reject row `('2', 'y', '')` | FID:900-917 |
| 6.62, 6.63 | `1;x\n2;y;2.5\n3;z;3.5\n` | plain, either setting | the first line is the shortest, so the read fails: `Expected 2 fields in line 2, saw 3` | FID:428-435 (pandas) |
| 6.64, 6.65 | `1;x\n2;y\n` | plain, 3 schema columns | false: third column null, `1;x;\n2;y;\n`. True: every row rejected, 0-byte output | FID:468-470 |
| 6.66, 6.67 | `1;x;1.5\n2;y;\n` | plain | true rejects the row whose last field is empty (`expected 3, got 2`) although the line has 3 fields | FID:901-905 |
| 6.68, 6.69 | `1;;1.5\n2;y;2.5\n` | plain | an empty middle field is never a count error | FID:901-905 |
| 6.70-6.73 | the short-row file | plain with `footer_rows` 1 (python parser), or csv | `check_fields_num` true does not reject the short row: the missing field arrives as NaN, not as empty text | FID:605, 902 |
| 6.90, 6.91, 6.94, 6.92 | `1;x;u\n2;y\n3;z;w\n` (str last column) | those setups, or a two-character separator, with `check_fields_num` or `check_date` true; csv without | on path C the missing str field is written as the text `nan`: `2;y;nan`; on path A it is null: `2;y;` | FID:929 |
| 6.76, 6.77, 6.82, 6.83 | `1;x;1.5\n2;y;2.5;EXTRA\n3;z;3.5\n` | plain (C or python parser), either setting | a line longer than the first line fails the read: `Expected 3 fields in line 2, saw 4` | FID:428-435 (pandas) |
| 6.78-6.81 | first line longest; every line 4 fields | plain, 3 schema columns | extra fields are dropped silently; `check_fields_num` true reports nothing | FID:462-465 |
| 6.74, 6.84, 6.86 | every row short; one long row; every row long | csv, `check_fields_num` false | widest row differs from the schema width: schema columns are all null and the raw fields follow as extra columns: `;;;2;y;2.5;EXTRA\n` | FID:606-612; BC:665-683 |
| 6.75, 6.85, 6.87 | same | csv, `check_fields_num` true | every row rejected (`FIELD_COUNT`, `expected 3, got 4 - Line: 1`, or `got 2` for the short file); the reject frame has only `errorCode` and `errorMessage`; 0-byte output | FID:906-909 |

## 7. Output keys

Unless stated the input is `1;a\n2;b\n` with schema `id:int, name:str`.

| case | input | config | observed | where |
|---|---|---|---|---|
| 7.01, 7.02 | three rows of six types, row 2 all empty | `include_header` false / true | the header is the frame's column names joined by the separator, plus the row separator: `id;name;amt;ok;d;m\n` | FOD:812-821 |
| 7.03, 7.05 | same | `csv_option` true | every field is quoted: numbers, booleans, dates, nulls, empty text and header names: `"id";"name";"amt";"ok";"d";"m"\n"1";"alice";"10.5";"true";"2024-01-31";"1.50"\n"2";"";"";"false";"";""\n` | FOD:763-778 |
| 7.04, 7.26 | - | writer booleans as the string `"false"` | read as false (the writer parses strings; the reader does not) | FOD:130-146 |
| 7.10, 7.18, 7.27 | - | `os_line_separator` true or absent | `os.linesep` (LF here) whatever `row_separator` and `csvrowseparator` say | FOD:268, 959-960 |
| 7.11-7.14 | - | `os_line_separator` false, plain, `row_separator` `\\n`, `\\r\\n`, `\\r` text, `@@` | LF, CRLF, CR, `@@`; the last row is terminated too: `1;a\r\n2;b\r\n` | FOD:964, 1003-1012 |
| 7.15, 7.16 | - | `row_separator` pipe + backslash + n; empty | only a whole-string escape is translated: written literally `1;a\|\\n2;b\|\\n`; empty gives `1;a2;b` | FOD:1010-1012 |
| 7.17, 7.25 | - | plain with `csvrowseparator` set; csv with `row_separator` set | each mode ignores the other mode's key | FOD:961-964 |
| 7.19-7.23 | - | `os_line_separator` false, csv, `csvrowseparator` `LF`, `CR`, `CRLF`, `\\n`, `\\r\\n` | LF, CR, CRLF, LF, CRLF | FOD:71-75, 1029-1042 |
| 7.24 | - | `csvrowseparator` `lf` | written literally: `"1";"a"lf"2";"b"lf` | FOD:1042 |
| 7.30, 7.31 | run 1 `1;a\n2;b\n`, run 2 `3;c\n` | `append` true, `include_header` true | the header is written once: `id;name\n1;a\n2;b\n3;c\n` | FOD:371-372 |
| 7.32 | existing 0-byte file | same | the header is written | FOD:371 |
| 7.33 | existing `old;line-without-newline` | same | no newline is inserted and no header: `old;line-without-newline1;a\n2;b\n` | FOD:700 |
| 7.34 | existing `old;line\n` | `append` true (`file_exist_exception` true) | appended; no exception | FOD:306 |
| 7.35, 7.36 | empty input | `append` true, `include_header` true | the file is left untouched, and is not created if absent | FOD:620-625 |
| 7.40, 7.41, 7.43 | existing `old;line\n` | `file_exist_exception` true or absent, `append` false | job `failed`: `File already exists: '<path>'. Set file_exist_exception=false or append=true to allow writing.`; the file is untouched; raised for empty input too | FOD:267, 306-310 |
| 7.42 | existing three lines | `file_exist_exception` false | overwritten: `1;a\n2;b\n` | FOD:700 |
| 7.45, 7.46 | path `p/q/out.csv`; `p/out.csv` | `create_directory` true / false | true creates both levels. False: `Failed to write file '<path>': [Errno 2] No such file or directory: '<path>'`, job `failed` | FOD:302-303 |
| 7.50-7.53 | empty input | `delete_empty_file` false / true with `include_header` false / true | false: a 0-byte file, or the header alone (`id;name\n`). True: no file | FOD:627-667 |
| 7.54, 7.55 | empty input, file exists, `file_exist_exception` false | `delete_empty_file` true / false | true deletes the existing file; false truncates it to 0 bytes | FOD:628-629, 667 |
| 7.56 | empty input | `include_header` and `csv_option` true | `"id";"name"\n` | FOD:649-656 |
| 7.57, 7.58 | every row rejected upstream | `delete_empty_file` true; `include_header` true | treated as empty input: no file; header-only file | FOD:328 |
| 7.60, 7.61 | five rows | `split` true, `split_every` `"2"` / `5` | files `out0.csv`, `out1.csv`, `out2.csv` (stem, index from 0, suffix), each with the header; `out.csv` is not created; an exact fit gives one file | FOD:375-381, 919-929, 1025-1026 |
| 7.62-7.64 | same | `split_every` `"abc"`, `"0"`, `"-2"` | `abc` falls back to 1000; `0` fails the job (`range() arg 3 must not be zero`); `-2` writes nothing and the job succeeds | FOD:919, 1055-1058 |
| 7.65, 7.66 | same | file name `out.2024.csv`; `outfile` | `out.20240.csv`, `out.20241.csv`; `outfile0`, `outfile1` | FOD:1025-1026 |
| 7.67, 7.68 | same | `split` true, `file_exist_exception` true | only the base path is checked: an existing `out.csv` fails the job; an existing `out0.csv` is overwritten and a stale `out7.csv` stays | FOD:306 |
| 7.69 | existing `out0.csv` = `old0\n` | `split`, `append`, `include_header` true | the header is written again after the old content: `old0\nid;name\n1;a\n2;b\n` | FOD:371 |
| 7.70 | empty input | `split`, `include_header` true | a header-only file at the base path `out.csv`; no `out0.csv` | FOD:328-343 |
| 7.75-7.77 | non-ASCII text | writer `encoding` absent; ISO-8859-15 with a non-ASCII column name; UTF-16 | default ISO-8859-15 (`1;caf\xe9 \xa4\n`); header names are encoded like data; UTF-16 writes a BOM first | FOD:275, 811 |

## 8. Columns

The input is `1;alice;2024-01-31;1.5;true\n2;bob;2024-02-01;2;false\n` with
reader schema `id:int, name:str, d:datetime@%Y-%m-%d, m:Decimal#2, ok:bool`
and `include_header` true, unless stated.

| case | input | config | observed | where |
|---|---|---|---|---|
| 8.01-8.03 | shared | writer `schema.input` in frame order; reversed; writer `schema.output` reversed | the file always follows the frame's order, header included: `id;name;d;m;ok\n1;alice;2024-01-31;1.50;true\n...`. Neither writer schema reorders | FOD:773-778, 812-832 |
| 8.14 | `1;alice\n2;bob\n` | reader schema `name:str, id:str` | frame order and names come from the reader's schema, given to file fields by position: `name;id\n1;alice\n2;bob\n` | FID:465, 468 |
| 8.04 | shared | writer `schema.input` lists only `id`, `name` | the extra frame columns are still written, unformatted: `2024-01-31 00:00:00`, `1.50`, `True` | FOD:430-434 |
| 8.05 | shared | writer `schema.input` adds `extra:str`, absent from the frame | ignored: nothing is added, no error | FOD:433-434 |
| 8.06 | shared | writer `schema.output` adds `extra:int!` | no effect on the file (it is applied to the pass-through frame after the write) | BC:248-250 |
| 8.07 | a row with nulls | writer `schema.output` says `d` is nullable false | the complete file is written, then the writer fails: `Column 'd' has NULL values but is not nullable`; job `failed` | BC:1031-1034 |
| 8.10 | `1;alice\n2;bob\n` | plain; reader schema has six more columns (int, float, bool, datetime, Decimal, str) | missing columns are filled with empty text, then typed: `<NA>`, `nan`, `False`, `NaT`, `''`, `''`; written `1;alice;;;false;;;\n` | FID:468-470 |
| 8.11 | `1;alice;x;y\n` | plain; reader schema of 2 | the extra file fields are dropped | FID:462-465 |
| 8.12, 8.13 | 2 fields for 3 columns; 3 fields for 2 | csv | names are not assigned: header `id;name;s;0;1`, rows `;;;1;alice` | FID:606-612; BC:665-683 |
| 8.15 | `1;alice\n2;bob\n` | no schema on either component | columns are named `0`, `1`, all text; header `0;1` | FID:692-701 |
| 8.16 | same | reader column named `errorCode` | renamed `errorCode_user` in the main flow, and the header shows it | BC:837-869 |

## Most likely to trip a reimplementation

1. The same text gives different bytes depending on its neighbours. One value
   pandas cannot parse (whitespace only, `NaN`, junk) moves the whole column
   to Python parsing, and `check_fields_num` or `check_date` moves every
   column. `1.50` in a nullable int column is `1.5` or `1`; a 19-digit
   integer is exact or `...768`; `0.30000000000000004` is `0.3` or itself;
   `-0` in a float column is `0.0` or `-0.0`.
2. An int column is not always integers on output. One fractional value turns
   a nullable int column into floats (`1` is written `1.0`); one empty value
   in a nullable-false int column leaves the survivors as `5.0`;
   nullable-false int truncates `1.5` to `1` and wraps 2^63 to its negative.
3. Nulls are per type. `str` is never null (`NaN`, `null`, `NA`, `None` and
   empty are data). Empty bool is `false`.
   Empty Decimal stays empty text on the default path, and on the chunked
   path is written as the literal `<NA>`. `NaN` text is null for float and
   datetime, a reject for int and bool, and `NaN` for Decimal.
4. A Decimal column never rejects on the default path: any text passes
   through verbatim, even with nullable false and `die_on_error` true. On the
   chunked path the same text kills the reader.
5. The writer formats by its own `schema.input`, matched by column name:
   bool lower case, dates by its `date_pattern` (strftime dialect, `%f` is
   six digits, years below 1000 unpadded), Decimal to its `precision` or with
   trailing zeros stripped. Without a match it writes `True`,
   `2024-01-31 00:00:00`. Floats are always Python repr (`30200.0`, `1e+16`,
   `1e-05`). Column order is the frame's, never a writer schema's.
6. `precision` rounds on read: float half-to-even (`2.5` at 0 is `2.0`),
   Decimal half-up (`2.5` at 0 is `3`).
7. Plain mode ignores quotes, sizes the file from its first data line (a
   longer later line fails the whole read; extra fields are dropped
   silently), ends rows on CR, LF or CRLF whatever `row_separator` says,
   drops blank lines even with `remove_empty_row` false, and cuts a field at
   a NUL. Csv mode with a field count unlike the schema emits all-null schema
   columns followed by the raw fields.
8. `check_fields_num` rejects any row whose last field is empty, does not see
   short rows in csv mode, with a footer or with a multi-character separator,
   and there writes missing text as `nan`.
9. Text is altered on read: control characters and undecodable bytes become
   spaces, so a UTF-8 file read with the default ISO-8859-15 has its 0x80 to
   0x9f bytes replaced by spaces. A BOM is dropped in plain mode and kept in
   csv mode.
10. Writer line ends: `os_line_separator` true (what the converted samples
    carry) overrides both separator keys; `csv_option` quotes every field, nulls
    and header included.
11. `die_on_error` has two defaults (false for the reader's own conversion,
    true for the base nullable check), reader booleans given as strings are
    always true, and a reject flow with no rejected rows ends the job in
    status `error`.
12. File rules: on append the header is written only into an empty or absent
    file; split files are `out0.csv`, `out1.csv` and only the base path is
    checked by `file_exist_exception`; `delete_empty_file` deletes a file
    that already exists.
13. Row counting: `header_rows` and `footer_rows` count physical lines, blank
    ones included; `limit` is taken before empty rows are removed, so plain
    and csv mode disagree when a blank line is present; `Line: n` in a reject
    message counts data rows, not file lines.
