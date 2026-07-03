# tests/agents/knowledge/test_landmines.py
from agents.knowledge.landmines import LANDMINES, landmines_for


def test_registry_has_core_landmines():
    ids = {lm["id"] for lm in LANDMINES}
    assert {"tmap-operator-noop", "tmap-matching-mode-drops-dups",
            "tmap-catch-output-reject-error-only", "die-on-error-dual-default",
            "tmap-pattern-vs-date-pattern"} <= ids
    for lm in LANDMINES:                       # every landmine is fully populated
        assert lm["summary"] and lm["code_anchor"] and lm["guidance"]


def test_landmines_for_map_includes_operator_noop():
    ids = {lm["id"] for lm in landmines_for("Map")}
    assert "tmap-operator-noop" in ids
    assert "tmap-operator-noop" in {lm["id"] for lm in landmines_for("tMap")}   # alias
    assert "die-on-error-dual-default" in ids                                   # global included
