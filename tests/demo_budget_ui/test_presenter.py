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
