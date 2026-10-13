from agents.tools.check_schema_drift import check_drift


def test_no_schema_drift():
    problems = check_drift()
    assert problems == [], "schema drift / fixture inconsistency:\n" + "\n".join(problems)


def test_check_drift_detects_unregistered_type(monkeypatch):
    # NEGATIVE test: prove the gate CAN detect drift, not just that it is clean.
    # Simulate a curated schema whose declared type is no longer registered in the
    # engine by making REGISTRY.get() return None for one known type; check_drift()
    # must surface a "not registered" problem for that schema.
    from src.v1.engine.component_registry import REGISTRY
    real_get = REGISTRY.get
    monkeypatch.setattr(
        REGISTRY, "get",
        lambda name, *a, **k: None if name == "FileOutputDelimited" else real_get(name, *a, **k),
    )
    problems = check_drift()
    assert problems, "expected drift to be detected when a type is unregistered"
    assert any("not registered" in p for p in problems), problems
