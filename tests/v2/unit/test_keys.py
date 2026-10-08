"""Config-key declarations: how a raw config dict is checked and normalised."""
from src.v2.job.keys import Key, Kind, normalize_config

WHERE = "component in_1 (FileInputDelimited)"


def _norm(raw, keys, **kwargs):
    return normalize_config(raw, keys, WHERE, **kwargs)


def _reasons(refusals):
    return [(r.key, r.reason) for r in refusals]


# ------------------------------------------------------------------
# Names: aliases, unknown keys, both spellings
# ------------------------------------------------------------------

def test_v1_spelling_is_accepted_and_becomes_the_v2_name():
    keys = (Key("path", aliases=("filepath",)),)
    config, refusals = _norm({"filepath": "a.csv"}, keys)
    assert config == {"path": "a.csv"}
    assert refusals == []


def test_both_spellings_of_one_key_are_refused():
    keys = (Key("path", aliases=("filepath",)),)
    _, refusals = _norm({"filepath": "a.csv", "path": "b.csv"}, keys)
    assert len(refusals) == 1
    assert refusals[0].where == WHERE
    assert refusals[0].key == "filepath"
    assert "path" in refusals[0].reason


def test_unknown_key_is_refused_and_a_close_name_is_suggested():
    keys = (Key("delimiter", default=";"),)
    config, refusals = _norm({"delimeter": ","}, keys)
    assert [r.key for r in refusals] == ["delimeter"]
    assert "delimiter" in refusals[0].reason
    assert config == {"delimiter": ";"}


def test_every_problem_is_reported_in_one_pass():
    keys = (Key("path", required=True), Key("limit", type=int))
    _, refusals = _norm({"limit": "many", "bogus": 1}, keys)
    assert sorted(r.key for r in refusals) == ["bogus", "limit", "path"]


# ------------------------------------------------------------------
# Defaults and required keys
# ------------------------------------------------------------------

def test_omitted_key_takes_its_declared_default():
    keys = (Key("delimiter", default=";"), Key("trim_all", type=bool, default=False))
    config, refusals = _norm({}, keys)
    assert config == {"delimiter": ";", "trim_all": False}
    assert refusals == []


def test_missing_required_key_is_refused():
    keys = (Key("path", required=True, aliases=("filepath",)),)
    _, refusals = _norm({}, keys)
    assert _reasons(refusals) == [("path", "required config key is missing")]


def test_mutable_default_is_not_shared_between_configs():
    keys = (Key("columns", type=list, default=[]),)
    first, _ = _norm({}, keys)
    first["columns"].append("x")
    second, _ = _norm({}, keys)
    assert second == {"columns": []}


# ------------------------------------------------------------------
# Kinds: ignored and refused keys
# ------------------------------------------------------------------

def test_ignored_key_is_accepted_and_dropped():
    keys = (Key("label", kind=Kind.IGNORED), Key("path"))
    config, refusals = _norm({"label": "Read orders", "path": "a.csv"}, keys)
    assert config == {"path": "a.csv"}
    assert refusals == []


def test_refused_key_switched_off_is_accepted_and_dropped():
    keys = (Key("uncompress", kind=Kind.REFUSED, reason="zip input is not supported"),)
    config, refusals = _norm({"uncompress": False}, keys)
    assert config == {}
    assert refusals == []


def test_refused_key_in_use_stops_the_job_with_its_reason():
    keys = (Key("uncompress", kind=Kind.REFUSED, reason="zip input is not supported"),)
    _, refusals = _norm({"uncompress": True}, keys)
    assert _reasons(refusals) == [("uncompress", "zip input is not supported")]


def test_refused_key_accepts_its_declared_off_values():
    keys = (Key("split_every", kind=Kind.REFUSED, reason="no splitting", off=("1000", 0)),)
    _, refusals = _norm({"split_every": "1000"}, keys)
    assert refusals == []
    _, refusals = _norm({"split_every": "500"}, keys)
    assert [r.key for r in refusals] == ["split_every"]


# ------------------------------------------------------------------
# Values: types, choices, converters
# ------------------------------------------------------------------

def test_bool_key_accepts_the_strings_v1_job_configs_carry():
    keys = (Key("append", type=bool, default=False),)
    assert _norm({"append": "true"}, keys)[0] == {"append": True}
    assert _norm({"append": "False"}, keys)[0] == {"append": False}


def test_int_key_accepts_digit_strings_and_treats_empty_as_omitted():
    keys = (Key("limit", type=int, default=None),)
    assert _norm({"limit": "25"}, keys)[0] == {"limit": 25}
    assert _norm({"limit": ""}, keys)[0] == {"limit": None}


def test_int_key_refuses_a_bool_and_a_non_number():
    keys = (Key("header_rows", type=int, default=0),)
    for bad in (True, "one", 1.5):
        _, refusals = _norm({"header_rows": bad}, keys)
        assert [r.key for r in refusals] == ["header_rows"], bad


def test_str_key_refuses_a_number():
    keys = (Key("path"),)
    _, refusals = _norm({"path": 5}, keys)
    assert [r.key for r in refusals] == ["path"]


def test_value_outside_the_declared_choices_is_refused():
    keys = (Key("order", choices=("asc", "desc"), default="asc"),)
    _, refusals = _norm({"order": "up"}, keys)
    assert refusals[0].key == "order"
    assert "asc" in refusals[0].reason and "desc" in refusals[0].reason


def test_converter_runs_on_the_checked_value():
    keys = (Key("delimiter", default=";", convert=lambda v: "\t" if v == "\\t" else v),)
    assert _norm({"delimiter": "\\t"}, keys)[0] == {"delimiter": "\t"}


def test_converter_failure_becomes_a_refusal_with_its_message():
    def one_char(value):
        if len(value) != 1:
            raise ValueError("must be a single character")
        return value

    keys = (Key("quote_char", default='"', convert=one_char),)
    _, refusals = _norm({"quote_char": "''"}, keys)
    assert _reasons(refusals) == [("quote_char", "must be a single character")]


def test_none_is_kept_for_a_key_that_allows_it():
    keys = (Key("quote_char", default='"', nullable=True),)
    assert _norm({"quote_char": None}, keys)[0] == {"quote_char": None}


# ------------------------------------------------------------------
# Nested keys
# ------------------------------------------------------------------

CRITERIA = Key(
    "columns",
    type=list,
    aliases=("criteria",),
    items=(
        Key("name", required=True, aliases=("column",)),
        Key("order", choices=("asc", "desc"), default="asc"),
    ),
)


def test_list_items_are_normalised_with_their_own_keys():
    config, refusals = _norm({"criteria": [{"column": "a"}, {"column": "b", "order": "desc"}]}, (CRITERIA,))
    assert refusals == []
    assert config == {"columns": [{"name": "a", "order": "asc"}, {"name": "b", "order": "desc"}]}


def test_problem_inside_a_list_item_is_reported_with_its_position():
    _, refusals = _norm({"criteria": [{"column": "a"}, {"colum": "b"}]}, (CRITERIA,))
    assert sorted(r.key for r in refusals) == ["criteria[1].colum", "criteria[1].name"]


def test_list_item_that_is_not_an_object_is_refused():
    _, refusals = _norm({"criteria": ["a"]}, (CRITERIA,))
    assert [r.key for r in refusals] == ["criteria[0]"]


def test_item_converter_can_accept_a_shorthand_form():
    keys = (
        Key(
            "key_columns",
            type=list,
            items=(Key("column", required=True), Key("case_sensitive", type=bool, default=True)),
            item_convert=lambda item: {"column": item} if isinstance(item, str) else item,
        ),
    )
    config, refusals = _norm({"key_columns": ["id", {"column": "name", "case_sensitive": False}]}, keys)
    assert refusals == []
    assert config == {
        "key_columns": [
            {"column": "id", "case_sensitive": True},
            {"column": "name", "case_sensitive": False},
        ]
    }


def test_dict_fields_are_normalised_with_their_own_keys():
    keys = (Key("main", type=dict, fields=(Key("name", required=True), Key("filter", default="")),),)
    config, refusals = _norm({"main": {"name": "row1", "size_state": "X"}}, keys)
    assert config == {"main": {"name": "row1", "filter": ""}}
    assert [r.key for r in refusals] == ["main.size_state"]


# ------------------------------------------------------------------
# Context references: checked late
# ------------------------------------------------------------------

def test_context_reference_is_left_alone_until_a_resolver_is_given():
    keys = (Key("limit", type=int, default=None), Key("path"))
    raw = {"limit": "${context.max_rows}", "path": "${context.dir}/a.csv"}
    config, refusals = _norm(raw, keys)
    assert refusals == []
    assert config == raw


def test_resolver_output_is_checked_like_any_other_value():
    keys = (Key("limit", type=int, default=None), Key("path"))
    raw = {"limit": "${context.max_rows}", "path": "${context.dir}/a.csv"}
    values = {"${context.max_rows}": "40", "${context.dir}/a.csv": "/data/a.csv"}
    config, refusals = _norm(raw, keys, resolve=values.__getitem__)
    assert refusals == []
    assert config == {"limit": 40, "path": "/data/a.csv"}


def test_bad_value_after_resolving_is_refused():
    keys = (Key("limit", type=int, default=None),)
    _, refusals = _norm({"limit": "${context.max_rows}"}, keys, resolve=lambda text: "lots")
    assert [r.key for r in refusals] == ["limit"]
