"""Unit tests for BaseIterateComponent (Phase 10-01).

Covers ITER-11 (CURRENT_ITERATE -> CURRENT_ITERATION rename), 9-hook lifecycle,
iterator-based items, execute() override, _iterate_depth field.
"""
import copy
from collections.abc import Iterator
from typing import Any, Optional
from unittest import mock

import pandas as pd
import pytest

from src.v1.engine.base_iterate_component import BaseIterateComponent
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError, ComponentExecutionError
from src.v1.engine.global_map import GlobalMap


# ---------------------------------------------------------------------------
# Minimal concrete subclass for tests that need basic iteration
# ---------------------------------------------------------------------------

class _BoundedIterateStub(BaseIterateComponent):
    """Concrete subclass yielding a fixed list. Used in most unit tests."""

    def _validate_config(self) -> None:
        pass

    def prepare_iterations(self, input_data=None) -> Iterator[Any]:
        items = self.config.get("items", [])
        self.total_iterations = len(items)
        return iter(items)

    def set_iteration_globalmap(self, item: Any) -> None:
        if self.global_map:
            self.global_map.put(f"{self.id}_ITEM", item)


class _UnboundedIterateStub(BaseIterateComponent):
    """Concrete subclass with an unbounded generator. Used for infinite-iter tests."""

    def _validate_config(self) -> None:
        pass

    def prepare_iterations(self, input_data=None) -> Iterator[Any]:
        # total_iterations stays -1 (unbounded)
        def _gen():
            n = 0
            while True:
                yield n
                n += 1
        return _gen()

    def set_iteration_globalmap(self, item: Any) -> None:
        pass


class _ValidateFailStub(BaseIterateComponent):
    """Subclass whose _validate_config raises ConfigurationError."""

    def _validate_config(self) -> None:
        raise ConfigurationError(f"[{self.id}] forced validation error")

    def prepare_iterations(self, input_data=None) -> Iterator[Any]:
        return iter([])

    def set_iteration_globalmap(self, item: Any) -> None:
        pass


class _HookRecordingStub(BaseIterateComponent):
    """Subclass that records hook invocation order."""

    def _validate_config(self) -> None:
        pass

    def prepare_iterations(self, input_data=None) -> Iterator[Any]:
        items = self.config.get("items", [1, 2])
        self.total_iterations = len(items)
        self._hook_log = getattr(self, "_hook_log", [])
        self._hook_log.append("prepare_iterations")
        return iter(items)

    def prepare(self) -> None:
        self._hook_log = getattr(self, "_hook_log", [])
        self._hook_log.append("prepare")

    def set_iteration_globalmap(self, item: Any) -> None:
        pass


def _make_component(cls=_BoundedIterateStub, comp_id="iter_1", config=None):
    """Helper to build a test iterate component."""
    if config is None:
        config = {}
    gm = GlobalMap()
    cm = ContextManager(initial_context={"Default": {}})
    comp = cls(comp_id, config, gm, cm)
    # Simulate what execute() does: refresh config from _original_config
    comp.config = copy.deepcopy(comp._original_config)
    return comp, gm


# ===========================================================================
# TestCurrentIterationKeyRename
# ===========================================================================

class TestCurrentIterationKeyRename:
    """ITER-11: D-F7 fix -- _CURRENT_ITERATE renamed to _CURRENT_ITERATION."""

    def test_current_iteration_key_name(self):
        """get_next_iteration_context must write _CURRENT_ITERATION, not _CURRENT_ITERATE."""
        comp, gm = _make_component(config={"items": ["a", "b"]})
        comp.execute()
        ctx = comp.get_next_iteration_context()
        key_correct = f"{comp.id}_CURRENT_ITERATION"
        key_typo = f"{comp.id}_CURRENT_ITERATE"
        assert gm.get(key_correct) is not None, (
            f"Expected globalMap key '{key_correct}' to be set"
        )
        assert gm.get(key_typo) is None, (
            f"Old typo key '{key_typo}' must NOT be written"
        )

    def test_old_iterate_key_no_longer_written(self):
        """Confirm the legacy _CURRENT_ITERATE key is absent after a full iterate."""
        comp, gm = _make_component(config={"items": [10, 20, 30]})
        comp.execute()
        while comp.has_next_iteration():
            comp.get_next_iteration_context()
        for i in range(1, 4):
            assert gm.get(f"{comp.id}_CURRENT_ITERATE") is None


# ===========================================================================
# TestPrepareIterationsIteratorContract
# ===========================================================================

class TestPrepareIterationsIteratorContract:
    """D-A3: prepare_iterations returns Iterator[Any]."""

    def test_returns_iterator_not_list(self):
        """iteration_iter on the component is an Iterator after execute()."""
        comp, _ = _make_component(config={"items": [1, 2, 3]})
        comp.execute()
        # Iterator protocol: iter(it) is it
        assert iter(comp.iteration_iter) is comp.iteration_iter, (
            "iteration_iter must satisfy the Iterator protocol"
        )

    def test_bounded_yields_all_items(self):
        """Bounded iterator produces exactly the configured items."""
        comp, _ = _make_component(config={"items": [1, 2, 3]})
        comp.execute()
        # Use has_next + get_next to consume
        collected = []
        while comp.has_next_iteration():
            ctx = comp.get_next_iteration_context()
            collected.append(ctx["item"])
        assert collected == [1, 2, 3]

    def test_unbounded_iterator_supported(self):
        """An unbounded generator stays usable; total_iterations is -1."""
        comp, _ = _make_component(cls=_UnboundedIterateStub)
        comp.execute()
        assert comp.total_iterations == -1
        # Consume 6 items manually via the iterator directly
        items = [next(comp.iteration_iter) for _ in range(6)]
        assert items == [0, 1, 2, 3, 4, 5]

    def test_total_iterations_set_for_bounded(self):
        """total_iterations reflects item count for bounded iterators."""
        comp, _ = _make_component(config={"items": ["x", "y", "z"]})
        comp.execute()
        assert comp.total_iterations == 3

    def test_total_iterations_stays_negative_one_for_unbounded(self):
        """total_iterations is -1 for unbounded iterators."""
        comp, _ = _make_component(cls=_UnboundedIterateStub)
        comp.execute()
        assert comp.total_iterations == -1


# ===========================================================================
# TestExecuteOverride
# ===========================================================================

class TestExecuteOverride:
    """D-A2: execute() skips data-pipeline lifecycle steps."""

    def test_execute_skips_select_mode(self, monkeypatch):
        """execute() must NOT call _select_mode, _execute_batch, _execute_streaming."""
        comp, _ = _make_component(config={"items": [1]})
        select_mode_calls = []
        execute_batch_calls = []
        execute_streaming_calls = []

        monkeypatch.setattr(comp, "_select_mode", lambda *a, **kw: select_mode_calls.append(1))
        monkeypatch.setattr(comp, "_execute_batch", lambda *a, **kw: execute_batch_calls.append(1))
        monkeypatch.setattr(comp, "_execute_streaming", lambda *a, **kw: execute_streaming_calls.append(1))

        comp.execute()

        assert len(select_mode_calls) == 0, "_select_mode must not be called"
        assert len(execute_batch_calls) == 0, "_execute_batch must not be called"
        assert len(execute_streaming_calls) == 0, "_execute_streaming must not be called"

    def test_execute_runs_validate_then_prepare(self):
        """Hook ordering: prepare() called after _validate_config and _resolve_expressions."""
        comp, _ = _make_component(cls=_HookRecordingStub, config={"items": [1, 2]})
        comp._hook_log = []
        comp.execute()
        # prepare must appear in log before prepare_iterations
        assert "prepare" in comp._hook_log
        assert "prepare_iterations" in comp._hook_log
        assert comp._hook_log.index("prepare") < comp._hook_log.index("prepare_iterations")

    def test_execute_returns_dict_with_main_and_reject_none(self):
        """execute() returns dict with main=None and reject=None."""
        comp, _ = _make_component(config={"items": [1]})
        result = comp.execute()
        assert isinstance(result, dict)
        assert result.get("main") is None
        assert result.get("reject") is None

    def test_validate_config_failure_propagates_as_configuration_error(self):
        """ConfigurationError from _validate_config propagates unchanged."""
        comp, _ = _make_component(cls=_ValidateFailStub)
        with pytest.raises(ConfigurationError):
            comp.execute()

    def test_execute_sets_iteration_iter_from_prepare_iterations(self):
        """After execute(), iteration_iter is the iterator from prepare_iterations()."""
        comp, _ = _make_component(config={"items": [10, 20]})
        comp.execute()
        # iteration_iter should yield the items
        assert next(comp.iteration_iter) == 10

    def test_is_iterate_component_true(self):
        """is_iterate_component class-level / instance attribute must be True."""
        comp, _ = _make_component()
        assert comp.is_iterate_component is True

    def test_execute_count_input_rows_not_called(self, monkeypatch):
        """execute() must NOT call _count_input_rows."""
        comp, _ = _make_component(config={"items": [1]})
        count_calls = []
        monkeypatch.setattr(comp, "_count_input_rows", lambda *a: count_calls.append(1) or 0)
        comp.execute()
        assert len(count_calls) == 0, "_count_input_rows must not be called by iterate execute()"


# ===========================================================================
# TestLifecycleHooks
# ===========================================================================

class TestLifecycleHooks:
    """D-A5: 9 hooks exist with correct defaults."""

    def test_all_nine_hooks_callable(self):
        """All 9 lifecycle hook methods must exist and be callable."""
        comp, _ = _make_component()
        hooks = [
            "prepare",
            "prepare_iterations",
            "should_stop",
            "before_iteration",
            "set_iteration_globalmap",
            "after_iteration",
            "on_iteration_error",
            "finalize",
            "finalize_iterations",
        ]
        for h in hooks:
            assert callable(getattr(comp, h, None)), f"Hook '{h}' must be callable"

    def test_should_stop_default_false(self):
        """should_stop() default implementation returns False."""
        comp, _ = _make_component()
        assert comp.should_stop("item", 0) is False
        assert comp.should_stop("item", 100) is False

    def test_on_iteration_error_default_false(self):
        """on_iteration_error() default implementation returns False (re-raise)."""
        comp, _ = _make_component()
        exc = RuntimeError("test error")
        result = comp.on_iteration_error("item", 0, exc)
        assert result is False

    def test_prepare_default_no_op(self):
        """prepare() default does not raise."""
        comp, _ = _make_component()
        comp.prepare()  # Must not raise

    def test_before_iteration_default_no_op(self):
        """before_iteration() default does not raise."""
        comp, _ = _make_component()
        comp.before_iteration("item", 0)  # Must not raise

    def test_after_iteration_default_no_op(self):
        """after_iteration() default does not raise."""
        comp, _ = _make_component()
        comp.after_iteration("item", 0)  # Must not raise

    def test_finalize_default_no_op(self):
        """finalize() default does not raise."""
        comp, _ = _make_component()
        comp.finalize()  # Must not raise

    def test_set_iteration_globalmap_abstract_raises(self):
        """Calling the abstract set_iteration_globalmap on base raises NotImplementedError."""
        # We call it directly on the class-level abstract (not a subclass override)
        # The easiest way is to bypass the subclass override
        gm = GlobalMap()
        cm = ContextManager(initial_context={"Default": {}})

        # Create a subclass that does NOT override set_iteration_globalmap
        class _NoGlobalMapOverride(BaseIterateComponent):
            def _validate_config(self):
                pass
            def prepare_iterations(self, input_data=None):
                return iter([])

        with pytest.raises((NotImplementedError, TypeError)):
            _NoGlobalMapOverride("x", {}, gm, cm).set_iteration_globalmap("item")

    def test_prepare_iterations_abstract_raises_when_not_overridden(self):
        """prepare_iterations on a non-overriding subclass raises NotImplementedError."""
        gm = GlobalMap()
        cm = ContextManager(initial_context={"Default": {}})

        class _NoPrepareOverride(BaseIterateComponent):
            def _validate_config(self):
                pass
            def set_iteration_globalmap(self, item):
                pass

        with pytest.raises((NotImplementedError, TypeError)):
            _NoPrepareOverride("x", {}, gm, cm).prepare_iterations()


# ===========================================================================
# TestIterateDepthField
# ===========================================================================

class TestIterateDepthField:
    """D-A6: _iterate_depth scope field."""

    def test_default_is_zero(self):
        """_iterate_depth defaults to 0."""
        comp, _ = _make_component()
        assert comp._iterate_depth == 0

    def test_settable(self):
        """_iterate_depth can be set to any integer."""
        comp, _ = _make_component()
        comp._iterate_depth = 1
        assert comp._iterate_depth == 1
        comp._iterate_depth = 3
        assert comp._iterate_depth == 3

    def test_type_is_int(self):
        """_iterate_depth initial value is an int."""
        comp, _ = _make_component()
        assert isinstance(comp._iterate_depth, int)


# ===========================================================================
# TestIterateStubComponentFixture
# ===========================================================================

class TestIterateStubComponentFixture:
    """Validates the IterateStubComponent fixture for downstream plans."""

    def test_yields_configured_items(self):
        """IterateStubComponent yields configured items in order."""
        from tests.v1.engine.conftest import IterateStubComponent
        gm = GlobalMap()
        cm = ContextManager(initial_context={"Default": {}})
        comp = IterateStubComponent("stub_1", {"items": [1, 2, 3]}, gm, cm)
        comp.config = copy.deepcopy(comp._original_config)
        comp.execute()
        assert comp.total_iterations == 3
        collected = []
        while comp.has_next_iteration():
            ctx = comp.get_next_iteration_context()
            collected.append(ctx["item"])
        assert collected == [1, 2, 3]

    def test_set_iteration_globalmap_writes_keys(self):
        """IterateStubComponent.set_iteration_globalmap writes globalmap_key_prefix-prefixed keys."""
        from tests.v1.engine.conftest import IterateStubComponent
        gm = GlobalMap()
        cm = ContextManager(initial_context={"Default": {}})
        cfg = {"items": ["a", "b"], "globalmap_key_prefix": "MY_"}
        comp = IterateStubComponent("stub_2", cfg, gm, cm)
        comp.config = copy.deepcopy(comp._original_config)
        comp.execute()
        # Call set_iteration_globalmap directly with raw items
        comp.set_iteration_globalmap("a")
        comp.set_iteration_globalmap("b")
        # At least one MY_-prefixed key should exist
        # The stub uses a counter; MY_1 should hold "a", MY_2 "b"
        assert gm.get("MY_1") == "a"
        assert gm.get("MY_2") == "b"

    def test_make_iterate_job_config_callable(self):
        """make_iterate_job_config helper from conftest returns a valid job config dict."""
        from tests.v1.engine.conftest import make_iterate_job_config
        cfg = make_iterate_job_config(
            iter_id="iter_1",
            body_components=[{"id": "body_1", "component_type": "StubComponent"}],
            items=[1, 2, 3],
        )
        assert "job" in cfg
        assert "components" in cfg
        assert "flows" in cfg
        # Must have an iterate source component
        comp_ids = [c["id"] for c in cfg["components"]]
        assert "iter_1" in comp_ids
