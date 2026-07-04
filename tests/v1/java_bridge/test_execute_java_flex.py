"""Live-bridge tests for ``JavaBridge.execute_java_flex`` (tJavaFlex).

These ``@pytest.mark.java`` tests exercise the real JVM subprocess via the
session-scoped ``java_bridge`` fixture (``tests/v1/java_bridge/conftest.py``).
They verify the two parity-critical behaviours of tJavaFlex:

1. START locals (e.g. ``int n = 0``) persist across rows and into END --
   the whole script runs ONCE with the row loop inside the Groovy body.
2. The script runs once even for empty input (START/END must execute), and
   the output carries the declared ``output_schema`` columns.
"""
import pandas as pd
import pytest


@pytest.mark.java
def test_execute_java_flex_shares_start_var_across_rows(java_bridge):
    df = pd.DataFrame({"id": [1, 2], "name": ["a", "b"]})
    script = (
        "int n=0;\n"
        "for (int __i=0; __i<input.size(); __i++){\n"
        " row1=input.get(__i); row2=output.get(__i);\n"
        " row2.id=row1.id; row2.name=row1.name;\n"
        " n++; row2.total=n; }\n"
    )
    out = java_bridge.execute_java_flex(
        df, script=script,
        output_schema={"id": "int", "name": "str", "total": "int"},
        input_schema={"id": "int", "name": "str"},
    )
    assert list(out["total"]) == [1, 2]   # START var shared across rows


@pytest.mark.java
def test_execute_java_flex_empty_input_runs_once(java_bridge):
    df = pd.DataFrame({"id": []})
    script = "globalMap.put(\"ran\", \"yes\");\nfor(int __i=0;__i<input.size();__i++){}\n"
    out = java_bridge.execute_java_flex(
        df, script=script, output_schema={"id": "int"}, input_schema={"id": "int"})
    assert out.empty and list(out.columns) == ["id"]
    assert java_bridge.global_map.get("ran") == "yes"


@pytest.mark.java
def test_execute_java_flex_forward_syncs_context_and_global_map(java_bridge):
    """A flex MAIN must read context/globalMap values set by upstream Python.

    Seed bridge state BEFORE the call (as an upstream tSetGlobalVar /
    context param would) and assert the script sees the forwarded values.
    """
    # Seed upstream state the same way other live java tests do.
    java_bridge.context["upstream_ctx"] = "hi"
    java_bridge.global_map["upstream_gm"] = 7
    try:
        df = pd.DataFrame({"id": [1, 2]})
        script = (
            "for (int __i=0; __i<input.size(); __i++){\n"
            " row1=input.get(__i); row2=output.get(__i);\n"
            " row2.id=row1.id;\n"
            " row2.ctx=context.get(\"upstream_ctx\");\n"
            " row2.gm=globalMap.get(\"upstream_gm\"); }\n"
        )
        out = java_bridge.execute_java_flex(
            df, script=script,
            output_schema={"id": "int", "ctx": "str", "gm": "int"},
            input_schema={"id": "int"},
        )
        assert list(out["id"]) == [1, 2]
        assert list(out["ctx"]) == ["hi", "hi"]      # forwarded context.*
        assert list(out["gm"]) == [7, 7]             # forwarded globalMap value
    finally:
        java_bridge.context.pop("upstream_ctx", None)
        java_bridge.global_map.pop("upstream_gm", None)


@pytest.mark.java
def test_execute_java_flex_output_only_column(java_bridge):
    """An output_schema column absent from the input is emitted from MAIN.

    Input has only ``id``; MAIN propagates ``id`` and sets ``status`` (an
    output-only column). The output must carry both.
    """
    df = pd.DataFrame({"id": [10, 20]})
    script = (
        "for (int __i=0; __i<input.size(); __i++){\n"
        " row1=input.get(__i); row2=output.get(__i);\n"
        " row2.id=row1.id;\n"
        " row2.status=\"OK\"; }\n"
    )
    out = java_bridge.execute_java_flex(
        df, script=script,
        output_schema={"id": "int", "status": "str"},
        input_schema={"id": "int"},
    )
    assert list(out["id"]) == [10, 20]               # input propagated
    assert list(out["status"]) == ["OK", "OK"]       # output-only column set
