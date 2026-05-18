"""Groovy script generation for tMap (active + reject scripts, $ escape)."""
from src.v1.engine.components.transform.map.map_compiled_script import (
    groovy_escape_expression,
)


def test_escape_no_strings_passes_through():
    assert groovy_escape_expression("row1.amount + 5") == "row1.amount + 5"


def test_escape_dollar_inside_double_quoted_string():
    # Groovy GString interpolation: $identifier triggers eval. Escape it.
    assert groovy_escape_expression('"Total: $100"') == '"Total: \\$100"'


def test_escape_dollar_outside_string_unchanged():
    # $ outside a string is a legal Java/Groovy identifier char; leave alone
    assert groovy_escape_expression("var.$amount + 5") == "var.$amount + 5"


def test_escape_handles_escaped_quotes_inside_string():
    # \" inside a string is a 2-char escape; must not break out of string
    src = '"he said \\"hi\\" and $5"'
    assert groovy_escape_expression(src) == '"he said \\"hi\\" and \\$5"'


def test_escape_handles_single_quoted_strings_as_non_strings():
    # Single quotes are Groovy char literals; treat as outside-string region
    assert groovy_escape_expression("'$abc'") == "'$abc'"


from src.v1.engine.components.transform.map.map_compiled_script import (
    build_active_script,
)
from src.v1.engine.components.transform.map.map_config import parse_config


def _basic_cfg(die_on_error=True, with_variables=False, with_filter=False,
               with_reject=False, with_catch=False):
    """Return a minimal parsed MapConfig for script tests."""
    raw = {
        "component_type": "Map",
        "inputs": {
            "main": {"name": "row1", "filter": "", "activate_filter": False,
                     "matching_mode": "UNIQUE_MATCH", "lookup_mode": "LOAD_ONCE"},
            "lookups": [],
        },
        "variables": [],
        "outputs": [{
            "name": "out", "is_reject": False, "inner_join_reject": False,
            "catch_output_reject": False,
            "filter": "row1.amount > 0" if with_filter else "",
            "activate_filter": with_filter,
            "columns": [
                {"name": "id", "expression": "row1.id", "type": "int", "nullable": True},
                {"name": "label", "expression": '"row_" + row1.id', "type": "str", "nullable": True},
            ],
        }],
        "die_on_error": die_on_error,
    }
    if with_variables:
        raw["variables"] = [
            {"name": "v1", "expression": "row1.amount", "type": "int", "nullable": True},
            {"name": "v2", "expression": 'Var.get("v1") + 100', "type": "int", "nullable": True},
        ]
    if with_reject:
        raw["outputs"].append({
            "name": "rej", "is_reject": True, "inner_join_reject": False,
            "catch_output_reject": False, "filter": "", "activate_filter": False,
            "columns": [{"name": "id", "expression": "row1.id", "type": "int", "nullable": True}],
        })
    if with_catch:
        raw["outputs"].append({
            "name": "errs", "is_reject": False, "inner_join_reject": False,
            "catch_output_reject": True, "filter": "", "activate_filter": False,
            "columns": [
                {"name": "id", "expression": "row1.id", "type": "int", "nullable": True},
                {"name": "errorMessage", "expression": "", "type": "str", "nullable": True},
                {"name": "errorStackTrace", "expression": "", "type": "str", "nullable": True},
            ],
        })
    return parse_config(raw)


# ===== Task 3.2: basic script structure =====

def test_build_active_script_basic_includes_imports_and_buffer_decls():
    cfg = _basic_cfg()
    src = build_active_script(cfg)
    assert "import java.util.*;" in src
    assert "import com.citi.gru.etl.RowWrapper;" in src
    assert "Object[][] out_data = new Object[rowCount][2];" in src
    assert "int out_count = 0;" in src


def test_build_active_script_basic_row_loop_shape():
    cfg = _basic_cfg()
    src = build_active_script(cfg)
    assert "for (int i = 0; i < rowCount; i++) {" in src
    assert 'RowWrapper row1 = buildRowWrapper(inputRoot, i, "row1");' in src
    assert "out_tempRow[0] = row1.id;" in src
    assert 'out_tempRow[1] = "row_" + row1.id;' in src
    assert "out_data[out_count++] = out_tempRow;" in src


def test_build_active_script_basic_returns_results_map():
    cfg = _basic_cfg()
    src = build_active_script(cfg)
    assert "Map<String, Map<String, Object>> results = new HashMap<>();" in src
    assert 'results.put("out", out_result);' in src
    assert "return results;" in src


# ===== Task 3.3: variables, filters, rejects, catch, die_on_error =====

def test_build_active_script_with_variables_chained():
    cfg = _basic_cfg(with_variables=True)
    src = build_active_script(cfg)
    assert 'Var.put("v1", row1.amount);' in src
    assert 'Var.put("v2", Var.get("v1") + 100);' in src


def test_build_active_script_with_filter():
    cfg = _basic_cfg(with_filter=True)
    src = build_active_script(cfg)
    assert "if (row1.amount > 0) {" in src


def test_build_active_script_with_is_reject_emits_matched_any():
    cfg = _basic_cfg(with_reject=True)
    src = build_active_script(cfg)
    assert "boolean matchedAny = false;" in src
    assert "matchedAny = true;" in src
    assert "if (!matchedAny) {" in src
    assert "rej_data[rej_count++] = rej_tempRow;" in src


def test_build_active_script_with_catch_emits_error_tracking_and_stacktrace():
    cfg = _basic_cfg(with_catch=True)
    src = build_active_script(cfg)
    assert "Map<Integer, String> errorMap = new HashMap<>();" in src
    assert "Map<Integer, String> stackTraceMap = new HashMap<>();" in src
    assert "catch (Exception innerE)" in src
    assert "innerE.printStackTrace(new java.io.PrintWriter(sw));" in src
    assert "stackTraceMap.put(i, sw.toString());" in src
    assert 'errorInfo.put("stackTraces", stackTraceMap);' in src


def test_build_active_script_die_on_error_false_emits_error_tracking_too():
    cfg = _basic_cfg(die_on_error=False)
    src = build_active_script(cfg)
    # Even without catch_output_reject, die_on_error=false needs error tracking
    assert "Map<Integer, String> errorMap = new HashMap<>();" in src
    assert 'errorInfo.put("messages", errorMap);' in src
