"""Engine component for OracleRow (tOracleRow).

Executes arbitrary SQL/DDL/DML against either a shared connection
(USE_EXISTING_CONNECTION + CONNECTION ref) or an ad-hoc connection.
Supports prepared statements with full PARAMETER_TYPE coverage per D-C3.

Talaxie tOracleRow_java.xml PARAMETER_TYPE enum (verified 2026-05-07):
  BigDecimal, Blob, Boolean, Byte, Bytes, Clob, Date, Double, Float,
  Int, Long, Object, Short, String, Time, Null

Source: https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/main/plugins/org.talend.designer.components.localprovider/components/tOracleRow/tOracleRow_java.xml
(see lines 333-352 of the XML for the SET_PREPAREDSTATEMENT_PARAMETERS table.)

Open Question 2 resolution (RESEARCH.md): The Talaxie enum is 16 values.
Differences from the original RESEARCH.md "16-Type Coercion Table":
  - Talaxie HAS:    Blob, Clob, Null  (three additional values)
  - Talaxie LACKS:  Integer, BigInteger, Timestamp
                     (these were inferred from Talend documentation but are
                      not present in the actual Talaxie XML enum)

For maximum safety and Talend feature parity we map ALL of these:
  Talaxie's 16 verified values + the 3 RESEARCH.md inferred values
  (Integer / BigInteger / Timestamp) as defensive aliases.
This protects against converter emitting any of the 19 names; unknown values
still raise ConfigurationError per D-C3.

PROPAGATE_RECORD_SET=true is refused per D-C4 (Talend's live ResultSet-as-FLOW
pattern doesn't translate cleanly to DataFrame semantics; rewrite as
tOracleInput -> downstream component when this is needed).

Config keys consumed (~28 total; the converter at
src/converters/talend_to_v1/components/database/oracle_row.py emits these):
    use_existing_connection (bool, default False) -- shared vs ad-hoc connection
    connection            (str, default "")       -- cid ref of upstream
                                                     tOracleConnection (when
                                                     use_existing_connection=True)
    connection_type, host, port, dbname,          -- ad-hoc connection params
    user, password, ...                              (mirror oracle_connection.py)
    query                 (str, REQUIRED)         -- SQL/DDL/DML; goes through
                                                     engine resolution before
                                                     _process runs (BaseComponent
                                                     _resolve_expressions)
    use_nb_line           (str enum, default      -- one of NONE / NB_LINE_INSERTED
                          "NONE")                  / NB_LINE_UPDATED / NB_LINE_DELETED
    use_preparedstatement (bool, default False)
    set_preparedstatement_parameters (list[dict]) -- each entry:
                                                       {parameter_index,
                                                        parameter_type,
                                                        parameter_value}
    propagate_record_set  (bool, default False)   -- True raises
                                                     ConfigurationError per D-C4
    commit_every          (int, default 10000)    -- relevant only for
                                                     prepared-statement loops
    die_on_error          (bool, default False)   -- handled by BaseComponent
    ... + framework params

Returns: {"main": input_data, "reject": None} -- passthrough.
Side effects:
    - optionally writes f"{cid}_NB_LINE_*" globalMap key per use_nb_line (D-C5)
    - always writes f"{cid}_QUERY" (the resolved SQL) (D-C8)

Security note (T-11-01):
    The QUERY field MAY contain user-controlled SQL. The SAFE channel for
    parameter values is the prepared-statement path -- positional binds via
    cursor.execute(query, [vals]). The 16-type coercion table converts each
    bind value to a typed Python value before binding. When
    use_preparedstatement=False, the raw QUERY string is executed verbatim;
    BaseComponent._resolve_expressions has already substituted context.var
    values BEFORE _process runs. Trust boundary is internal Citi job authors.
"""
# NOTE (Task 1 commit -- pre-implementation stub):
# This file exists at this commit so Task 1's <verify> grep can pass:
#   grep -E "Talaxie tOracleRow_java.xml PARAMETER_TYPE enum" src/v1/engine/components/database/oracle_row.py
#
# The OracleRow class, _PARAM_TYPE_COERCERS dispatch table, and registration
# decorator are added in Task 2 (next commit). This intentional split keeps
# the Open Question 2 resolution auditable in the git history.
