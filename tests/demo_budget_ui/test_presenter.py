# tests/demo_budget_ui/test_presenter.py
from demo.budget_ui.daemon import presenter as P

def test_classify_curated_types():
    assert P.classify({"id": "in_trades", "type": "FileInputDelimited",
                       "config": {"filepath": "trades.csv"}})["label"] == "Read trades"
    assert P.classify({"id": "f", "type": "FilterRows",
                       "config": {"conditions": [{"column": "status", "operator": "==", "value": "SETTLED"}]}}) \
        == {"kind": "filter", "label": "Keep status = SETTLED", "sub": "filter rows"}
    j = P.classify({"id": "j", "type": "tJoin",
                    "config": {"use_inner_join": False, "join_key": [{"lookup_column": "account_id"}]}},
                   lookup_name="accounts")
    assert j["kind"] == "join" and j["label"] == "Match accounts" and "left join" in j["sub"]
    assert P.classify({"id": "d", "type": "tPythonDataFrame",
                       "config": {"python_code": "df['market_value'] = df['quantity']"}})["label"] == "Compute market_value"
    assert P.classify({"id": "s", "type": "SortRow",
                       "config": {"criteria": [{"column": "market_value", "order": "desc"}]}})["label"] == "Sort by market_value"
    assert P.classify({"id": "o", "type": "FileOutputDelimited",
                       "config": {"filepath": "trade_positions.csv"}})["kind"] == "output"

def test_classify_unknown_type_humanizes_not_raw_id():
    v = P.classify({"id": "src_1", "type": "tOracleInput", "config": {}})
    assert v["kind"] == "source"          # name ends in Input -> source
    assert "Oracle" in v["label"]          # humanized, never the raw id "src_1"
    assert v["label"] != "src_1"

def test_classify_map_family_not_misread_as_simple_join():
    # PyMap/tMap must not fall through to the tJoin branch
    assert P.classify({"id": "m", "type": "PyMap", "config": {}})["kind"] == "map"
    assert P.classify({"id": "m", "type": "tMap", "config": {}})["kind"] == "map"

# add to tests/demo_budget_ui/test_presenter.py
import json, pathlib
FIX = pathlib.Path(__file__).parent / "fixtures" / "trade_position_demo"
def _load(name): return json.loads((FIX / name).read_text())

def _forbidden_values():
    """Every raw sample/expected cell value in the real extract_doc -- must never leak."""
    doc = _load("extract_doc.json")
    vals = set()
    for rows in list(doc.get("sample_input", {}).values()) + list(doc.get("expected_output", {}).values()):
        for row in rows:
            for v in (row.values() if isinstance(row, dict) else row):
                if isinstance(v, str) and v.strip():
                    vals.add(v)
    return [v for v in vals if v not in ("SETTLED",)]  # SETTLED is also a rule literal (allowed)

def test_ev_sources_lists_sources_and_is_data_free():
    ev = P.ev_sources(_load("extract_doc.json"))
    assert ev["type"] == "sources"
    ids = [n["id"] for n in ev["nodes"]]
    assert set(ids) == {"trades", "accounts", "prices"}
    assert all(n["kind"] == "source" for n in ev["nodes"])
    P.assert_data_free(ev, _forbidden_values())        # e.g. "Gamma Funds", "30200.00", "A999" never appear

def test_ev_rules_counts_and_labels():
    ev = P.ev_rules(_load("requirement_spec.json"))
    assert ev["type"] == "rules" and ev["count"] == 6
    kinds = {i["kind"] for i in ev["items"]}
    assert {"join", "filter", "sort", "derive", "schema_validate"} <= kinds
    P.assert_data_free(ev, _forbidden_values())

def test_ev_nodes_uses_skeleton_and_is_data_free():
    ev = P.ev_nodes(_load("flow_plan.json"))   # flow_plan has NO config -> config-free skeleton
    assert ev["type"] == "nodes"
    kinds = {n["kind"] for n in ev["nodes"]}
    assert {"source", "filter", "join", "derive", "validate", "sort", "output"} <= kinds
    labels = {n["label"] for n in ev["nodes"]}
    assert "Filter rows" in labels and "Compute a value" in labels  # business labels arrive via node_config
    P.assert_data_free(ev, _forbidden_values())
