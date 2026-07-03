from agents.tools.check_schema_drift import check_drift


def test_no_schema_drift():
    problems = check_drift()
    assert problems == [], "schema drift / fixture inconsistency:\n" + "\n".join(problems)
