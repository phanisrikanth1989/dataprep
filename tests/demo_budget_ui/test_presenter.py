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

def test_ev_edges_from_flows_and_marks_reject():
    ev = P.ev_edges(_load("job.json"))
    assert ev["type"] == "edges"
    pairs = {(e["from"], e["to"]) for e in ev["edges"]}
    assert ("filter_settled", "join_accounts") in pairs
    assert ("sort_market_value", "trade_positions") in pairs
    assert all(e.get("reject") is False for e in ev["edges"])  # this job has no reject route
    P.assert_data_free(ev, _forbidden_values())

def test_ev_node_config_fills_business_label_and_sub():
    ev = P.ev_node_config(_load("job.json"))
    by = {n["id"]: n for n in ev["nodes"]}
    assert by["filter_settled"]["label"] == "Keep status = SETTLED"   # upgraded from real config
    assert by["filter_settled"]["sub"] == "filter rows"
    assert "left join on account_id" in by["join_accounts"]["sub"]    # lookup name resolved from flows
    P.assert_data_free(ev, _forbidden_values())

def test_ev_callouts_are_canned_and_data_free():
    outs = P.ev_callouts(_load("job.json"))
    by_node = {c["node"]: c["text"] for c in outs}
    assert "filter_settled" in by_node and "derive_market_value" in by_node
    assert "sign off" in by_node["derive_market_value"].lower()
    for c in outs:
        P.assert_data_free(c, _forbidden_values())

def test_ev_gate_present_for_code_cell():
    g = P.ev_gate(_load("job.json"))
    assert g["type"] == "gate" and g["node"] == "derive_market_value"
    assert g["status"] == "awaiting" and "market_value" in g["code"]

def test_ev_gate_none_without_code():
    job = {"components": [{"id": "x", "type": "FilterRows", "config": {}}], "flows": []}
    assert P.ev_gate(job) is None
