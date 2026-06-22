# tests/v1/engine/components/transform/test_java_flex_script.py
from src.v1.engine.components.transform.java_flex_script import build_script


def test_auto_propagate_before_emits_matching_cols_before_main():
    src = build_script(
        code_start="int n=0;",
        code_main="row2.status = \"OK\";",
        code_end="System.out.println(n);",
        input_cols=["id", "name", "extra_in"],
        output_cols=["id", "name", "status"],
        input_row_name="row1",
        output_row_name="row2",
        auto_propagate=True,
        propagate_timing="before",
    )
    # START before the loop, END after it
    assert src.index("int n=0;") < src.index("for (")
    assert src.index("System.out.println(n);") > src.index("for (")
    # auto-propagate copies only id+name (intersection), NOT extra_in/status
    assert "row2.id = row1.id" in src
    assert "row2.name = row1.name" in src
    assert "row2.extra_in" not in src and "row2.status = row1.status" not in src
    # copies appear before the user MAIN line
    assert src.index("row2.name = row1.name") < src.index('row2.status = "OK";')


def test_auto_propagate_after_places_copies_after_main():
    src = build_script(
        code_start="", code_main='row2.status="OK";', code_end="",
        input_cols=["id"], output_cols=["id", "status"],
        input_row_name="row1", output_row_name="row2",
        auto_propagate=True, propagate_timing="after",
    )
    assert src.index('row2.status="OK";') < src.index("row2.id = row1.id")


def test_auto_propagate_off_emits_no_copies():
    src = build_script(
        code_start="", code_main="", code_end="",
        input_cols=["id"], output_cols=["id"],
        input_row_name="row1", output_row_name="row2",
        auto_propagate=False, propagate_timing="before",
    )
    assert "row1.id" not in src
