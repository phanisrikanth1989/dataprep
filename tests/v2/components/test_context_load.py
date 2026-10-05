"""Context load, against v1 on the same job config: files, context values, globalMap and log lines."""
import datetime
import json
import logging
import warnings
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Tuple

import pytest

from src.v2 import load_job
from src.v2 import run_job as run_on_v2
from src.v2.components.context.context_load import ContextLoad
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import REPO_ROOT, JobRun, differences, run_job, run_v1

from .kit import columns, flow, job, reader, writer

V1_LOGGER = "src.v1.engine.components.context.context_load"
V2_LOGGER = "src.v2.components.context.context_load"
V1_CONTEXT_LOGGER = "src.v1.engine.context_manager"

CONTEXT = {
    "name": {"value": "old", "type": "str"},
    "n": {"value": "5", "type": "int"},
    "rate": {"value": "1.5", "type": "float"},
    "flag": {"value": "false", "type": "bool"},
    "amt": {"value": "1.10", "type": "Decimal"},
}
EVERY = b"key;value\nname;new\nn;042\nrate;2.50\nflag;TRUE\namt;3.140\n"
SOME = b"key;value\nname;new\nbrand_new;hello\n"


def loading(config=None, schema="key:str, value:str", context=CONTEXT, path="${context.name}.csv"):
    """key/value file -> context load; then a second subjob writes a file named by the context."""
    load = {"id": "load", "type": "ContextLoad", "config": config or {},
            "schema": {"input": columns(schema), "output": []}, "inputs": ["row1"], "outputs": []}
    made = job(
        [reader(schema, header_rows=1), load, reader("a:str", component_id="in2", path="data.csv", outputs=("row2",)),
         writer("a:str", path=path)],
        [flow("row1", "in", "load"), flow("row2", "in2", "out")],
        triggers=[{"type": "OnSubjobOk", "from": "in", "to": "in2"}],
    )
    made["context"] = {"Default": context}
    return made


@dataclass
class Seen:
    """What one engine left behind."""

    run: JobRun
    context: Dict[str, Any] = field(default_factory=dict)
    global_map: Dict[str, Any] = field(default_factory=dict)
    lines: List[Tuple[str, str]] = field(default_factory=list)
    kept: List[str] = field(default_factory=list)


def both(tmp_path, caplog, made, data, fails=False) -> Tuple[Seen, Seen]:
    """Run a job on v1 and on v2 and check they agree on the files, the messages and what was loaded."""
    state: Dict[str, Tuple[Dict[str, Any], Dict[str, Any]]] = {}

    def on_v1(job_config):
        from src.v1.engine.engine import ETLEngine

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            engine = ETLEngine(job_config)
            result = engine.execute()
        state["v1"] = (dict(engine.context_manager.context), dict(engine.global_map.get_all()))
        if result.get("status") != "success":
            raise RuntimeError(f"v1 ended with status {result.get('status')!r}")

    def on_v2(job_config):
        result = run_on_v2(job_config)
        state["v2"] = (result.context, result.global_map)
        result.raise_for_status()

    caplog.set_level(logging.INFO)
    caplog.clear()
    inputs = {"in.csv": data, "data.csv": b"x\n"}
    v1 = Seen(run_job(made, inputs, tmp_path / "v1", on_v1), *state.get("v1", ({}, {})))
    v2 = Seen(run_job(made, inputs, tmp_path / "v2", on_v2), *state.get("v2", ({}, {})))
    for seen, name in ((v1, V1_LOGGER), (v2, V2_LOGGER)):
        seen.lines = [(record.levelname, record.getMessage()) for record in caplog.records if record.name == name]
    # A value that does not fit its type is warned about by v1's context, and by v2's component.
    v1.kept = [record.getMessage() for record in caplog.records
               if record.name == V1_CONTEXT_LOGGER and record.levelno == logging.WARNING]
    v2.kept = [text for level, text in v2.lines if level == "WARNING" and "kept as it is" in text]
    v2.lines = [line for line in v2.lines if line[1] not in v2.kept]

    assert differences(v1.run, v2.run) == []
    assert v2.run.succeeded is not fails, v2.run.error
    assert v2.lines == v1.lines
    assert len(v2.kept) == len(v1.kept), (v1.kept, v2.kept)
    for key in ("load_NB_CONTEXT_LOADED", "load_KEY_NOT_INCONTEXT", "load_KEY_NOT_LOADED"):
        assert v2.global_map.get(key) == v1.global_map.get(key), key
    return v1, v2


def same_values(v1: Seen, v2: Seen, *names: str) -> None:
    for name in names or sorted(set(v1.context) | set(v2.context)):
        assert name in v2.context and name in v1.context, name
        ours, theirs = v2.context[name], v1.context[name]
        assert ours == theirs and type(ours) is type(theirs), f"{name}: v1 has {theirs!r}, v2 has {ours!r}"


# ------------------------------------------------------------------
# Who sees a loaded value
# ------------------------------------------------------------------

def test_loaded_value_is_seen_by_a_later_subjob(tmp_path, caplog):
    _, v2 = both(tmp_path, caplog, loading(), b"key;value\nname;new\n")
    assert v2.run.files == {"new.csv": b"a\nx\n"}
    assert v2.context["name"] == "new"


def test_loaded_value_is_seen_by_a_later_component_of_the_same_subjob(tmp_path, caplog):
    schema = "key:str, value:str"
    load = {"id": "load", "type": "tContextLoad", "config": {},
            "schema": {"input": columns(schema), "output": []}, "inputs": ["row1"], "outputs": []}
    made = job(
        [reader(schema, header_rows=1, outputs=("row1", "row2")), load, writer(schema, path="${context.name}.csv")],
        [flow("row1", "in", "load"), flow("row2", "in", "out")],
    )
    made["context"] = {"Default": CONTEXT}
    _, v2 = both(tmp_path, caplog, made, b"key;value\nname;new\n")
    assert v2.run.files == {"new.csv": b"key;value\nname;new\n"}


def test_without_the_load_the_old_value_is_used(tmp_path, caplog):
    _, v2 = both(tmp_path, caplog, loading(), b"key;value\nother;1\n")
    assert list(v2.run.files) == ["old.csv"]


# ------------------------------------------------------------------
# A value takes the type of its variable
# ------------------------------------------------------------------

def test_values_take_the_type_of_the_variable(tmp_path, caplog):
    path = "${context.name}_${context.n}_${context.rate}_${context.flag}_${context.amt}.csv"
    v1, v2 = both(tmp_path, caplog, loading(path=path), EVERY)
    assert list(v2.run.files) == ["new_42_2.5_True_3.140.csv"]
    assert v2.context == {"name": "new", "n": 42, "rate": 2.5, "flag": True, "amt": Decimal("3.140")}
    same_values(v1, v2)


@pytest.mark.parametrize(
    "kind, start, text",
    [
        ("int", "5", "42"), ("int", "5", " 7 "), ("int", "5", "-3"), ("int", "5", "4.0"), ("int", "5", "12x"),
        ("float", "1.5", "2.50"), ("float", "1.5", "1e3"), ("float", "1.5", "7"), ("float", "1.5", "abc"),
        ("bool", "false", "true"), ("bool", "false", "TRUE"), ("bool", "false", "yes"), ("bool", "false", "1"),
        ("bool", "true", "Y"), ("bool", "true", "no"), ("bool", "true", "0"),
        ("Decimal", "1.10", "3.140"), ("Decimal", "1.10", "7"), ("Decimal", "1.10", "x"),
        ("str", "old", "new"), ("str", "old", "  spaced  "), ("str", "old", "42"),
        ("int", "5", ""), ("float", "1.5", ""), ("bool", "true", ""), ("Decimal", "1.10", ""), ("str", "old", ""),
    ],
)
def test_conversion_to_the_declared_type(tmp_path, caplog, kind, start, text):
    context = {"v": {"value": start, "type": kind}}
    v1, v2 = both(tmp_path, caplog, loading(context=context, path="out.csv"), f"key;value\nv;{text}\n".encode())
    same_values(v1, v2, "v")


def test_text_that_does_not_fit_the_type_is_kept_as_text(tmp_path, caplog):
    v1, v2 = both(tmp_path, caplog, loading(path="out.csv"), b"key;value\nn;12x\nrate;abc\namt;x\n")
    same_values(v1, v2)
    assert (v2.context["n"], v2.context["rate"], v2.context["amt"]) == ("12x", "abc", "x")
    assert v2.kept == [
        "[load] context variable 'n': '12x' is not a valid int, kept as it is",
        "[load] context variable 'rate': 'abc' is not a valid float, kept as it is",
        "[load] context variable 'amt': 'x' is not a valid Decimal, kept as it is",
    ]


def test_value_column_of_whole_numbers(tmp_path, caplog):
    made = loading(schema="key:str, value:int", path="out.csv")
    v1, v2 = both(tmp_path, caplog, made, b"key;value\nname;7\nn;42\nrate;3\nflag;1\nfresh;9\nname;\n")
    same_values(v1, v2)
    assert v2.context == {"name": None, "n": 42, "rate": 3.0, "flag": True, "amt": Decimal("1.10"), "fresh": "9"}


def test_value_column_of_numbers(tmp_path, caplog):
    made = loading(schema="key:str, value:float", path="out.csv")
    v1, v2 = both(tmp_path, caplog, made, b"key;value\nname;7.5\nn;42\nrate;3.25\nflag;1\namt;2.5\n")
    same_values(v1, v2)
    assert v2.context == {"name": "7.5", "n": 42, "rate": 3.25, "flag": False, "amt": Decimal("2.5")}


@pytest.mark.parametrize(
    "kind, text",
    [
        ("id_Integer", "42"), ("id_Long", "42"), ("id_Short", "7"), ("id_Byte", "7"), ("id_Float", "2.50"),
        ("id_Double", "1e3"), ("id_Boolean", "YES"), ("id_Boolean", "n"), ("id_Character", "xyz"),
        ("id_BigDecimal", "1.10"), ("id_String", "text"), ("id_Object", "thing"),
        ("id_Date", "2025-02-03 04:05:06"), ("id_Date", "2025-02-03"), ("id_Date", "02/03/2025"),
        ("id_Date", "03/02/2025 04:05"), ("id_Date", "not a date"),
        ("int", "9"), ("float", "9"), ("bool", "true"), ("Decimal", "9.90"), ("str", "9"), ("datetime", "2025-02-03"),
        ("object", "9"), ("weird", "9"), ("", "9"), ("id_Integer", "x"), ("id_Integer", ""),
    ],
)
def test_type_column_decides_the_type_of_its_row(tmp_path, caplog, kind, text):
    made = loading(schema="key:str, value:str, type:str", path="out.csv")
    v1, v2 = both(tmp_path, caplog, made, f"key;value;type\nn;{text};{kind}\nfresh;{text};{kind}\n".encode())
    same_values(v1, v2, "n", "fresh")


def test_date_set_by_one_load_stays_a_date_at_the_next(tmp_path):
    typed = "key:str, value:str, type:str"
    first = {"id": "first", "type": "ContextLoad", "config": {},
             "schema": {"input": columns(typed), "output": []}, "inputs": ["row0"], "outputs": []}
    made = loading(path="out.csv")
    made["components"] = [reader(typed, component_id="in0", path="typed.csv", outputs=("row0",), header_rows=1),
                          first] + made["components"]
    made["flows"].insert(0, flow("row0", "in0", "first"))
    made["triggers"] = [{"type": "OnSubjobOk", "from": "in0", "to": "in"},
                        {"type": "OnSubjobOk", "from": "in", "to": "in2"}]
    inputs = {"typed.csv": b"key;value;type\nday;2025-02-03;id_Date\n",
              "in.csv": b"key;value\nday;2026-03-04 05:06:07\n", "data.csv": b"x\n"}
    seen = {}

    def on_v1(job_config):
        from src.v1.engine.engine import ETLEngine

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            engine = ETLEngine(job_config)
            engine.execute()
        seen["v1"] = engine.context_manager.context["day"]

    def on_v2(job_config):
        seen["v2"] = run_on_v2(job_config).context["day"]

    v1, v2 = run_job(made, inputs, tmp_path / "v1", on_v1), run_job(made, inputs, tmp_path / "v2", on_v2)
    assert differences(v1, v2) == [] and v2.succeeded
    assert seen["v2"] == seen["v1"] == datetime.datetime(2026, 3, 4, 5, 6, 7)


def test_date_in_a_date_column_is_taken_as_it_is(tmp_path, caplog):
    made = loading(schema="key:str, value:datetime@%Y-%m-%d, type:str", path="out.csv")
    v1, v2 = both(tmp_path, caplog, made, b"key;value;type\nday;2025-02-03;id_Date\n")
    assert v2.context["day"] == v1.context["day"] == datetime.datetime(2025, 2, 3)
    assert type(v2.context["day"]) is datetime.datetime


def test_type_column_gives_a_date(tmp_path, caplog):
    made = loading(schema="key:str, value:str, type:str", path="out.csv")
    _, v2 = both(tmp_path, caplog, made, b"key;value;type\nday;2025-02-03 04:05:06;id_Date\n")
    assert v2.context["day"] == datetime.datetime(2025, 2, 3, 4, 5, 6)


# ------------------------------------------------------------------
# Which rows set a variable
# ------------------------------------------------------------------

def test_blank_keys_are_skipped_keys_are_stripped_and_the_last_value_wins(tmp_path, caplog):
    data = b"key;value\n;lost\n   ;lost\n  name  ;first\nname;second\nn;1\nn;2\n"
    v1, v2 = both(tmp_path, caplog, loading(config={"print_operations": True}), data)
    same_values(v1, v2)
    assert (v2.context["name"], v2.context["n"]) == ("second", 2)
    assert v2.global_map["load_NB_CONTEXT_LOADED"] == 2
    assert list(v2.run.files) == ["second.csv"]


def test_empty_flow_sets_nothing(tmp_path, caplog):
    v1, v2 = both(tmp_path, caplog, loading(config={"disable_warnings": False}), b"key;value\n")
    same_values(v1, v2)
    assert v2.global_map["load_KEY_NOT_LOADED"] == "amt,flag,n,name,rate"
    assert v2.lines[-1] == ("INFO", "[load] Loaded 0 context variables (0 new, 0 updated, 5 unloaded)")


def test_flow_without_key_and_value_columns_fails(tmp_path, caplog):
    _, v2 = both(tmp_path, caplog, loading(schema="k:str, v:str"), b"k;v\nname;new\n", fails=True)
    assert "Input must have 'key' and 'value' columns, got: ['k', 'v']" in v2.run.error


# ------------------------------------------------------------------
# Keys that are not variables yet, and variables the flow does not set
# ------------------------------------------------------------------

def test_new_variable_is_created_as_text_and_seen_later(tmp_path, caplog):
    v1, v2 = both(tmp_path, caplog, loading(path="${context.brand_new}.csv"), SOME)
    same_values(v1, v2)
    assert v2.context["brand_new"] == "hello" and list(v2.run.files) == ["hello.csv"]
    assert v2.global_map["load_KEY_NOT_INCONTEXT"] == "brand_new"
    assert v2.global_map["load_KEY_NOT_LOADED"] == "amt,flag,n,rate"
    assert v2.global_map["load_NB_CONTEXT_LOADED"] == 2
    assert v2.lines == [("INFO", "[load] Loaded 2 context variables (1 new, 1 updated, 4 unloaded)")]


@pytest.mark.parametrize("policy", ["ERROR", "WARNING", "INFO", "NO_WARNING", "Warning", "info"])
@pytest.mark.parametrize("quiet", [{}, {"disable_error": True, "disable_warnings": True, "disable_info": True},
                                   {"disable_error": False, "disable_warnings": False, "disable_info": False}])
@pytest.mark.parametrize("key", ["load_new_variable", "not_load_old_variable"])
def test_policies_decide_what_is_said(tmp_path, caplog, key, policy, quiet):
    other = "not_load_old_variable" if key == "load_new_variable" else "load_new_variable"
    v1, v2 = both(tmp_path, caplog, loading(config={key: policy, other: "NO_WARNING", **quiet}), SOME)
    same_values(v1, v2)


def test_what_is_said_exactly(tmp_path, caplog):
    config = {"load_new_variable": "WARNING", "not_load_old_variable": "INFO", "disable_warnings": False,
              "disable_info": False, "print_operations": True}
    _, v2 = both(tmp_path, caplog, loading(config=config), b"key;value\nname;new\nn;42\nzeta;z\nalpha;a\n")
    assert v2.lines == [
        ("INFO", "[load] Context loaded: name = new (type: str)"),
        ("INFO", "[load] Context loaded: n = 42 (type: int)"),
        ("INFO", "[load] Context loaded: zeta = z (type: id_String)"),
        ("INFO", "[load] Context loaded: alpha = a (type: id_String)"),
        ("WARNING", "[load] New context variable 'alpha' not in original job context"),
        ("WARNING", "[load] New context variable 'zeta' not in original job context"),
        ("INFO", "[load] Context variable 'amt' not loaded from incoming flow"),
        ("INFO", "[load] Context variable 'flag' not loaded from incoming flow"),
        ("INFO", "[load] Context variable 'rate' not loaded from incoming flow"),
        ("INFO", "[load] Loaded 4 context variables (2 new, 2 updated, 3 unloaded)"),
    ]


def test_nothing_is_said_about_keys_unless_asked(tmp_path, caplog):
    _, v2 = both(tmp_path, caplog, loading(), SOME)
    assert [level for level, _ in v2.lines] == ["INFO"]


@pytest.mark.parametrize("print_operations", [True, False])
def test_print_operations(tmp_path, caplog, print_operations):
    _, v2 = both(tmp_path, caplog, loading(config={"print_operations": print_operations}), EVERY)
    assert len(v2.lines) == (6 if print_operations else 1)


@pytest.mark.parametrize("key", ["load_new_variable", "not_load_old_variable"])
@pytest.mark.parametrize("die", [True, False])
@pytest.mark.parametrize("quiet", [True, False])
def test_an_error_fails_the_component_only_when_asked_and_not_kept_quiet(tmp_path, caplog, key, die, quiet):
    config = {key: "ERROR", "die_on_error": die, "disable_error": quiet}
    v1, v2 = both(tmp_path, caplog, loading(config=config), SOME, fails=die and not quiet)
    same_values(v1, v2)
    assert v2.context["brand_new"] == "hello"


def test_failure_names_the_first_key_and_leaves_no_counts(tmp_path, caplog):
    config = {"load_new_variable": "ERROR", "not_load_old_variable": "ERROR", "die_on_error": True}
    _, v2 = both(tmp_path, caplog, loading(config=config), b"key;value\nzeta;z\nalpha;a\n", fails=True)
    assert "New context variable 'alpha' not in original job context" in v2.run.error
    assert v2.lines == [("ERROR", "[load] New context variable 'alpha' not in original job context")]
    assert "load_NB_CONTEXT_LOADED" not in v2.global_map and v2.run.files == {}


# ------------------------------------------------------------------
# Where v1 is not the answer
# ------------------------------------------------------------------

def run_alone(tmp_path, made, data):
    state = {}

    def on_v2(job_config):
        state["result"] = run_on_v2(job_config)
        state["result"].raise_for_status()

    run = run_job(made, {"in.csv": data, "data.csv": b"x\n"}, tmp_path / "alone", on_v2)
    return run, state.get("result")


def test_variable_with_no_value_takes_its_declared_type(tmp_path):
    context = {"n": {"value": None, "type": "int"}, "m": {"value": "", "type": "id_Integer"}}
    run, result = run_alone(tmp_path, loading(context=context, path="out.csv"), b"key;value\nn;42\nm;7\n")
    assert run.succeeded and result.context["n"] == 42 and result.context["m"] == 7


def test_flow_without_key_and_value_columns_fails_even_when_it_has_no_rows(tmp_path):
    # v1 looks for the columns only once a row arrives.
    made = loading(schema="k:str, v:str")
    assert run_job(made, {"in.csv": b"k;v\n", "data.csv": b"x\n"}, tmp_path / "v1", run_v1).succeeded
    run, _ = run_alone(tmp_path, made, b"k;v\n")
    assert not run.succeeded and "Input must have 'key' and 'value' columns, got: ['k', 'v']" in run.error


def test_whole_number_becomes_a_decimal(tmp_path):
    # v1 keeps numpy's own integer here: Python's Decimal does not take one.
    run, result = run_alone(tmp_path, loading(schema="key:str, value:int", path="out.csv"), b"key;value\namt;2\n")
    assert run.succeeded and result.context["amt"] == Decimal(2) and isinstance(result.context["amt"], Decimal)


def test_printed_type_is_the_one_the_job_config_declares(tmp_path, caplog):
    # As v1: the type as the job config spells it, and id_String for a variable it gives no type.
    context = {"day": {"value": "2024-01-01", "type": "datetime"}, "obj": {"value": "o", "type": "object"},
               "count": {"value": "7", "type": "id_Integer"}, "plain": "untyped",
               "nothing": {"value": None, "type": "str"}}
    caplog.set_level(logging.INFO)
    data = b"key;value\nday;2025-01-01\nobj;p\ncount;8\nplain;x\nnothing;y\n"
    run, result = run_alone(tmp_path, loading(config={"print_operations": True}, context=context, path="out.csv"), data)
    assert run.succeeded
    assert result.context == {"day": "2025-01-01", "obj": "p", "count": 8, "plain": "x", "nothing": "y"}
    assert [record.getMessage() for record in caplog.records if record.name == V2_LOGGER][:5] == [
        "[load] Context loaded: day = 2025-01-01 (type: datetime)",
        "[load] Context loaded: obj = p (type: object)",
        "[load] Context loaded: count = 8 (type: id_Integer)",
        "[load] Context loaded: plain = x (type: id_String)",
        "[load] Context loaded: nothing = y (type: str)",
    ]


def test_rows_read_are_counted_by_the_engine_when_something_reads_the_count(tmp_path):
    made = loading(path="out.csv")
    made["triggers"] = [{"type": "RunIf", "from": "load", "to": "in2",
                         "condition": '((Integer)globalMap.get("load_NB_LINE")) == 2'}]
    run, result = run_alone(tmp_path, made, b"key;value\nname;new\nn;1\n")
    assert run.succeeded and result.global_map["load_NB_LINE"] == 2 and "out.csv" in run.files


# ------------------------------------------------------------------
# What v2 says no to, and what it lets pass
# ------------------------------------------------------------------

def refused(made):
    with pytest.raises(JobRefusedError) as caught:
        load_job(made)
    return caught.value.report.format()


@pytest.mark.parametrize(
    "config, said",
    [
        ({"load_new_variable": "LOUD"}, "load_new_variable: 'LOUD' is not allowed"),
        ({"not_load_old_variable": "quiet"}, "not_load_old_variable: 'QUIET' is not allowed"),
        ({"die_on_error": "maybe"}, "die_on_error: expected true or false"),
        ({"print_operations": 1}, "print_operations: expected true or false"),
        ({"bogus": 1}, "bogus: unknown config key"),
    ],
)
def test_refused_config(config, said):
    assert said in refused(loading(config=config))


def test_bad_policy_fails_on_v1_too(tmp_path):
    made = loading(config={"load_new_variable": "LOUD"})
    assert not run_job(made, {"in.csv": SOME, "data.csv": b"x\n"}, tmp_path / "v1", run_v1).succeeded
    assert "is not allowed" in refused(made)


def test_context_load_takes_one_flow_and_gives_none():
    made = loading()
    made["components"].append(writer("a:str", component_id="more", path="more.csv", inputs=("row3",)))
    made["flows"].append(flow("row3", "load", "more"))
    assert "has no 'flow' output" in refused(made)

    made = loading()
    made["flows"] = [flow("row2", "in2", "out")]
    assert "needs 1 input(s), but 0 flows arrive" in refused(made)


def test_variable_only_the_load_sets_is_not_refused_at_load():
    assert load_job(loading(path="${context.brand_new}.csv")).components["load"].cls is ContextLoad


def test_v2_name_and_defaults():
    made = loading()
    made["components"][1]["type"] = "context_load"
    config = load_job(made).components["load"].config
    assert config == {"print_operations": False, "load_new_variable": "WARNING", "not_load_old_variable": "WARNING",
                      "disable_error": False, "disable_warnings": True, "disable_info": True, "die_on_error": False}
    spec = load_job(made).components["load"]
    assert ContextLoad.sets_context is True and ContextLoad(spec, config, None).needs_rows() is True


def test_the_converter_sample_loads():
    path = REPO_ROOT / "tests" / "talend_xml_samples" / "converted_jsons" / "Job_tContextLoad_0.1.json"
    with open(path, encoding="utf-8") as handle:
        sample = json.load(handle)
    source, load = sample["components"][0], sample["components"][1]
    assert (source["type"], load["type"]) == ("FileInputDelimited", "ContextLoad")
    made = job([source, load], sample["flows"], context=sample["context"], default_context=sample["default_context"])
    loaded = load_job(made)
    assert loaded.components[load["id"]].config["load_new_variable"] == "WARNING"
    assert set(load["config"]) == {"print_operations", "die_on_error", "disable_error", "disable_warnings",
                                   "disable_info", "load_new_variable", "not_load_old_variable",
                                   "tstatcatcher_stats", "label"}


def test_the_whole_converter_sample_is_refused_only_for_its_java_component():
    path = REPO_ROOT / "tests" / "talend_xml_samples" / "converted_jsons" / "Job_tContextLoad_0.1.json"
    with pytest.raises(JobRefusedError) as caught:
        load_job(path)
    found = [(refusal.where, refusal.key) for refusal in caught.value.report]
    assert found == [("component tJava_1 (JavaComponent)", "type")]
