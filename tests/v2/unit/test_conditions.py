"""RunIf conditions: v2 reads them exactly as v1 does, Java left-overs included."""
import datetime
from decimal import Decimal

import pytest

from src.v2.engine.conditions import evaluate
from src.v2.errors import ConfigurationError

CONTEXT = {"n": 100, "flag": "Y", "name": "beta", "on": True, "rate": Decimal("1.10"), "none": None}
GLOBAL_MAP = {
    "should_run": "1",
    "count": 7,
    "f": "false",
    "status": "OK",
    "tFileList_1_CURRENT_FILE": "Customer_2024.csv",
    "exists": True,
    "zero": 0,
}

CONDITIONS = [
    '((Integer)globalMap.get("should_run")) == 1',
    "globalMap.get('exists') == True",
    '"Customer" in globalMap.get("tFileList_1_CURRENT_FILE")',
    '(globalMap.get(\'status\')) == "OK"',
    '"Y" == ${context.flag}',
    '"N" == ${context.flag}',
    "context.n > 50",
    "context.n > 50 && context.flag == \"Y\"",
    "context.n < 50 || context.flag == \"Y\"",
    "!(context.n > 50)",
    "context.n != 100",
    '((Integer)globalMap.get("missing")) == 0',
    '((Boolean)globalMap.get("f"))',
    '((Boolean)globalMap.get("missing"))',
    '((String)globalMap.get("missing")) == null',
    '((String)globalMap.get("status")) == "OK"',
    '((Long)globalMap.get("count")) >= 7',
    '((Double)globalMap.get("count")) / 2 == 3.5',
    'globalMap.get("should_run") == 1',
    'globalMap.get("missing") == null',
    "true",
    "false",
    "context.on == true",
    "((Integer)globalMap.get(\"zero\")) > 0",
    "context.name == 'beta'",
    "int(globalMap.get('should_run')) + context.n == 101",
]


def v1_evaluate(condition):
    from src.v1.engine.context_manager import ContextManager
    from src.v1.engine.global_map import GlobalMap
    from src.v1.engine.trigger_manager import TriggerManager

    global_map = GlobalMap()
    for key, value in GLOBAL_MAP.items():
        global_map.put(key, value)
    context = ContextManager()
    for key, value in CONTEXT.items():
        context.set(key, value)
    return TriggerManager(global_map, context)._evaluate_condition(condition)


@pytest.mark.parametrize("condition", CONDITIONS)
def test_condition_gives_what_v1_gives(condition):
    assert evaluate(condition, CONTEXT, GLOBAL_MAP) is v1_evaluate(condition)


def test_empty_condition_is_true():
    assert evaluate("", CONTEXT, GLOBAL_MAP) is True
    assert evaluate(None, CONTEXT, GLOBAL_MAP) is True


def test_condition_needs_nothing_in_the_global_map():
    assert evaluate("context.n > 500", CONTEXT, {}) is False


@pytest.mark.parametrize(
    "condition",
    [
        'context.flag.equals("Y")',
        "context.unknown == 1",
        "len(context.name) > 2",
        "context.n >",
        "__import__('os').system('true')",
    ],
)
def test_condition_that_cannot_be_read_says_so(condition):
    with pytest.raises(ConfigurationError) as caught:
        evaluate(condition, CONTEXT, GLOBAL_MAP)
    assert condition in str(caught.value)


def test_datetime_context_value_cannot_be_compared_in_a_condition():
    with pytest.raises(ConfigurationError):
        evaluate("context.day == 1", {"day": datetime.datetime(2024, 1, 31)}, GLOBAL_MAP)


def test_numbers_numpy_hands_out_are_read_as_python_numbers():
    import numpy as np

    global_map = {"total": np.int64(7), "ratio": np.float64(0.5), "flag": np.bool_(True)}
    assert evaluate('globalMap.get("total") == 7 && globalMap.get("ratio") < 1', {}, global_map) is True
    assert evaluate('((Integer)globalMap.get("total")) > 6 && globalMap.get("flag")', {}, global_map) is True
    assert evaluate("context.n == 7", {"n": np.int64(7)}, {}) is True
