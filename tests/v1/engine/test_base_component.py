"""Tests for BaseComponent and BaseIterateComponent lifecycle.

Covers: ENG-03 (array resolution), ENG-07/20 (streaming reject), ENG-08 (validate_config),
ENG-09/21 (config immutability), ENG-16 (standardized template), ENG-17 (named flows),
ENG-19 (nullable logic), config snapshot/restore, reset for iterate, die_on_error
subclass accessibility.
"""
import copy

import pandas as pd
import pytest

from src.v1.engine.base_component import BaseComponent, ComponentStatus, ExecutionMode
from src.v1.engine.base_iterate_component import BaseIterateComponent
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import (
    ComponentExecutionError,
    ConfigurationError,
    DataValidationError,
)
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Test Subclasses (shared fixtures)
# ------------------------------------------------------------------


class ConcreteComponent(BaseComponent):
    """Minimal concrete component for testing BaseComponent lifecycle."""

    def _validate_config(self) -> None:
        if self.config.get("invalid"):
            raise ConfigurationError("Invalid config")

    def _process(self, input_data=None) -> dict:
        return {"main": input_data, "reject": None}


class RejectComponent(BaseComponent):
    """Component that produces reject output for streaming tests."""

    def _validate_config(self) -> None:
        pass

    def _process(self, input_data=None) -> dict:
        if input_data is not None and not input_data.empty:
            # Split: even rows -> main, odd rows -> reject
            main = input_data.iloc[::2].reset_index(drop=True)
            reject = input_data.iloc[1::2].reset_index(drop=True)
            return {"main": main, "reject": reject}
        return {"main": input_data, "reject": None}


class DieOnErrorAwareComponent(BaseComponent):
    """Component that reads die_on_error in _process() to decide error handling.

    Addresses Gemini review: verify die_on_error is accessible to subclasses.
    """

    def _validate_config(self) -> None:
        pass

    def _process(self, input_data=None) -> dict:
        # Subclass reads self.die_on_error to decide whether to swallow errors
        if not self.die_on_error:
            # In lenient mode, catch data errors and route to reject
            try:
                # Simulate a data-level error
                if self.config.get("force_error"):
                    raise ValueError("bad data")
            except ValueError:
                return {"main": pd.DataFrame(), "reject": input_data}
        else:
            if self.config.get("force_error"):
                raise ValueError("bad data")
        return {"main": input_data, "reject": None}


class ProcessErrorComponent(BaseComponent):
    """Component that always raises during _process."""

    def _validate_config(self) -> None:
        pass

    def _process(self, input_data=None) -> dict:
        raise RuntimeError("processing failed")


class ConfigMutatingComponent(BaseComponent):
    """Component that mutates self.config during _process."""

    def _validate_config(self) -> None:
        pass

    def _process(self, input_data=None) -> dict:
        # Mutate config during processing
        self.config["mutated_key"] = "mutated_value"
        if "nested" in self.config:
            self.config["nested"]["inner"] = "changed"
        return {"main": input_data, "reject": None}


class MultiOutputComponent(BaseComponent):
    """Component that produces named flow outputs (ENG-17)."""

    def _validate_config(self) -> None:
        pass

    def _process(self, input_data=None) -> dict:
        return {
            "main": pd.DataFrame({"a": [1]}),
            "reject": pd.DataFrame({"err": ["bad"]}),
            "lookup": pd.DataFrame({"b": [2]}),
        }


class ConcreteIterateComponent(BaseIterateComponent):
    """Minimal iterate component for testing."""

    def _validate_config(self) -> None:
        pass

    def prepare_iterations(self, input_data=None):
        return self.config.get("items", [1, 2, 3])

    def set_iteration_globalmap(self, item):
        if self.global_map:
            self.global_map.put(f"{self.id}_CURRENT", item)


# ------------------------------------------------------------------
# Tests: BaseComponent Abstract Interface
# ------------------------------------------------------------------


@pytest.mark.unit
class TestBaseComponentAbstract:
    """BaseComponent cannot be instantiated without implementing abstract methods."""

    def test_cannot_instantiate_base_component(self):
        """BaseComponent raises TypeError when instantiated directly."""
        with pytest.raises(TypeError):
            BaseComponent("c1", {})

    def test_missing_validate_config_raises_type_error(self):
        """A subclass missing _validate_config cannot be instantiated."""

        class MissingValidate(BaseComponent):
            def _process(self, input_data=None):
                return {"main": None, "reject": None}

        with pytest.raises(TypeError):
            MissingValidate("c1", {})

    def test_missing_process_raises_type_error(self):
        """A subclass missing _process cannot be instantiated."""

        class MissingProcess(BaseComponent):
            def _validate_config(self):
                pass

        with pytest.raises(TypeError):
            MissingProcess("c1", {})

    def test_concrete_component_can_be_instantiated(self):
        """A fully implemented subclass can be instantiated."""
        comp = ConcreteComponent("c1", {})
        assert comp.id == "c1"


# ------------------------------------------------------------------
# Tests: BaseComponent Lifecycle
# ------------------------------------------------------------------


@pytest.mark.unit
class TestBaseComponentLifecycle:
    """execute() follows the template method lifecycle."""

    def test_execute_calls_validate_before_process(self):
        """execute() calls _validate_config before _process."""
        call_order = []

        class OrderTracker(BaseComponent):
            def _validate_config(self):
                call_order.append("validate")

            def _process(self, input_data=None):
                call_order.append("process")
                return {"main": None, "reject": None}

        comp = OrderTracker("c1", {})
        comp.execute()
        assert call_order.index("validate") < call_order.index("process")

    def test_execute_sets_status_running_then_success(self):
        """execute() transitions from RUNNING to SUCCESS."""
        statuses = []

        class StatusTracker(BaseComponent):
            def _validate_config(self):
                statuses.append(self.status)

            def _process(self, input_data=None):
                statuses.append(self.status)
                return {"main": None, "reject": None}

        comp = StatusTracker("c1", {})
        comp.execute()
        assert statuses[0] == ComponentStatus.RUNNING
        assert statuses[1] == ComponentStatus.RUNNING
        assert comp.status == ComponentStatus.SUCCESS

    def test_execute_config_error_sets_status_error(self):
        """ConfigurationError in _validate_config sets status to ERROR."""
        comp = ConcreteComponent("c1", {"invalid": True})
        with pytest.raises(ConfigurationError):
            comp.execute()
        assert comp.status == ComponentStatus.ERROR

    def test_execute_process_exception_wraps_in_component_execution_error(self):
        """Exception in _process() is wrapped in ComponentExecutionError."""
        comp = ProcessErrorComponent("c1", {})
        with pytest.raises(ComponentExecutionError) as exc_info:
            comp.execute()
        assert exc_info.value.component_id == "c1"
        assert comp.status == ComponentStatus.ERROR

    def test_execute_returns_process_result(self):
        """execute() returns the dict from _process() with stats added."""
        df = pd.DataFrame({"x": [1, 2, 3]})
        comp = ConcreteComponent("c1", {})
        result = comp.execute(df)
        assert "main" in result
        assert result["main"] is not None
        assert len(result["main"]) == 3

    def test_execute_populates_config_from_original(self):
        """execute() populates self.config from _original_config before validation."""
        configs_seen = []

        class ConfigChecker(BaseComponent):
            def _validate_config(self):
                configs_seen.append(dict(self.config))

            def _process(self, input_data=None):
                return {"main": None, "reject": None}

        comp = ConfigChecker("c1", {"key1": "value1"})
        # Before execute, config should be empty
        assert comp.config == {}
        comp.execute()
        # During execute, config should have been populated
        assert configs_seen[0] == {"key1": "value1"}

    def test_execute_result_has_stats_key(self):
        """execute() attaches stats dict to the result."""
        comp = ConcreteComponent("c1", {})
        result = comp.execute()
        assert "stats" in result
        assert "NB_LINE" in result["stats"]


# ------------------------------------------------------------------
# Tests: Config Immutability (ENG-09/ENG-21)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestBaseComponentConfigImmutability:
    """_original_config is never mutated; config is fresh each execute()."""

    def test_original_config_unchanged_after_execute(self):
        """_original_config unchanged after execute()."""
        original = {"key": "value", "nested": {"inner": "deep"}}
        comp = ConfigMutatingComponent("c1", original)
        original_snapshot = copy.deepcopy(comp._original_config)
        comp.execute()
        assert comp._original_config == original_snapshot

    def test_config_is_fresh_copy_each_execute(self):
        """config is a fresh copy each execute() (not stale from previous)."""
        comp = ConfigMutatingComponent("c1", {"key": "original"})
        comp.execute()
        # First execute mutated self.config
        assert comp.config.get("mutated_key") == "mutated_value"

        # Second execute should get a fresh config
        comp.execute()
        # The mutated_key is added again from _process, but the initial
        # state was fresh -- key should be 'original' not something stale
        assert comp._original_config.get("key") == "original"
        assert "mutated_key" not in comp._original_config

    def test_second_execute_gets_fresh_config(self):
        """Execute twice: second call gets fresh config (ENG-09 regression)."""
        call_configs = []

        class ConfigRecorder(BaseComponent):
            def _validate_config(self):
                call_configs.append(dict(self.config))

            def _process(self, input_data=None):
                self.config["added_in_process"] = True
                return {"main": None, "reject": None}

        comp = ConfigRecorder("c1", {"original_key": "yes"})
        comp.execute()
        comp.execute()
        # Both calls should see the original config without mutations from previous
        assert call_configs[0] == {"original_key": "yes"}
        assert call_configs[1] == {"original_key": "yes"}

    def test_modifying_config_in_process_does_not_affect_original(self):
        """modifying self.config in _process does not affect _original_config."""
        original = {"key": "value"}
        comp = ConfigMutatingComponent("c1", original)
        original_before = copy.deepcopy(comp._original_config)
        comp.execute()
        assert comp._original_config == original_before

    def test_deep_nested_config_preserved_across_executions(self):
        """Deep nested config values preserved across executions."""
        nested = {
            "level1": {
                "level2": {"level3": [1, 2, 3]},
            },
            "list_of_dicts": [{"a": 1}, {"b": 2}],
        }
        comp = ConcreteComponent("c1", nested)
        original_snapshot = copy.deepcopy(comp._original_config)
        comp.execute()
        comp.execute()
        assert comp._original_config == original_snapshot


# ------------------------------------------------------------------
# Tests: Config with Context Resolution
# ------------------------------------------------------------------


@pytest.mark.unit
class TestBaseComponentConfigWithContext:
    """Context variables are resolved in config during execute()."""

    def test_context_resolves_dollar_brace(self):
        """ContextManager resolves ${context.var} in config."""
        cm = ContextManager()
        cm.set("db_host", "localhost")
        comp = ConcreteComponent(
            "c1", {"host": "${context.db_host}"}, context_manager=cm
        )
        comp.execute()
        assert comp.config["host"] == "localhost"

    def test_python_code_not_resolved(self):
        """python_code field NOT resolved (ENG-18 via ContextManager)."""
        cm = ContextManager()
        cm.set("var", "resolved_value")
        comp = ConcreteComponent(
            "c1",
            {"python_code": "context.var + '_suffix'", "normal": "${context.var}"},
            context_manager=cm,
        )
        comp.execute()
        # python_code should be unchanged
        assert comp.config["python_code"] == "context.var + '_suffix'"
        # normal field should be resolved
        assert comp.config["normal"] == "resolved_value"

    def test_second_execute_re_resolves_from_original(self):
        """Second execute() re-resolves from original (not double-resolved)."""
        cm = ContextManager()
        cm.set("val", "first")
        comp = ConcreteComponent(
            "c1", {"field": "${context.val}"}, context_manager=cm
        )
        comp.execute()
        assert comp.config["field"] == "first"

        cm.set("val", "second")
        comp.execute()
        assert comp.config["field"] == "second"

    def test_nested_dict_in_list_resolved(self):
        """Nested dict in list resolved (NEW-02 via ContextManager)."""
        cm = ContextManager()
        cm.set("col", "id")
        comp = ConcreteComponent(
            "c1",
            {"columns": [{"name": "${context.col}"}, {"name": "static"}]},
            context_manager=cm,
        )
        comp.execute()
        assert comp.config["columns"][0]["name"] == "id"
        assert comp.config["columns"][1]["name"] == "static"


# ------------------------------------------------------------------
# Tests: Streaming Mode with Reject (ENG-07/ENG-20)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestBaseComponentStreamingReject:
    """Streaming mode collects BOTH main AND reject data."""

    def test_streaming_collects_main_chunks(self):
        """Streaming mode collects main chunks."""
        df = pd.DataFrame({"x": range(20)})
        comp = RejectComponent(
            "c1", {"execution_mode": "streaming", "chunk_size": 5}
        )
        result = comp.execute(df)
        assert result["main"] is not None
        # Per chunk of 5: even indices 0,2,4 -> 3 main; 4 chunks -> 12 main
        assert len(result["main"]) == 12

    def test_streaming_collects_reject_chunks(self):
        """Streaming mode collects reject chunks (ENG-07/20 regression)."""
        df = pd.DataFrame({"x": range(20)})
        comp = RejectComponent(
            "c1", {"execution_mode": "streaming", "chunk_size": 5}
        )
        result = comp.execute(df)
        assert result["reject"] is not None
        # Per chunk of 5: odd indices 1,3 -> 2 reject; 4 chunks -> 8 reject
        assert len(result["reject"]) == 8

    def test_empty_reject_results_in_none(self):
        """Empty reject chunks result in None (not empty DataFrame)."""
        df = pd.DataFrame({"x": [1, 2, 3]})
        comp = ConcreteComponent(
            "c1", {"execution_mode": "streaming", "chunk_size": 10}
        )
        result = comp.execute(df)
        # ConcreteComponent returns reject=None, so streaming should have reject=None
        assert result["reject"] is None

    def test_streaming_mixed_chunks(self):
        """Mixed chunks: some with reject, some without."""
        # Create a component that only rejects when input has > 2 rows per chunk
        class ConditionalReject(BaseComponent):
            def _validate_config(self):
                pass

            def _process(self, input_data=None):
                if input_data is not None and len(input_data) > 2:
                    return {
                        "main": input_data.head(2),
                        "reject": input_data.tail(len(input_data) - 2),
                    }
                return {"main": input_data, "reject": None}

        df = pd.DataFrame({"x": range(10)})
        comp = ConditionalReject(
            "c1", {"execution_mode": "streaming", "chunk_size": 3}
        )
        result = comp.execute(df)
        # Chunks of 3: [0,1,2], [3,4,5], [6,7,8], [9]
        # First 3 chunks have 3 rows -> 2 main + 1 reject each
        # Last chunk has 1 row -> 1 main + 0 reject
        assert result["main"] is not None
        assert result["reject"] is not None
        assert len(result["main"]) == 7  # 2+2+2+1
        assert len(result["reject"]) == 3  # 1+1+1


# ------------------------------------------------------------------
# Tests: Schema Validation (ENG-19)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestBaseComponentValidateSchema:
    """validate_schema handles nullable, type coercion correctly."""

    def test_nullable_true_allows_nan(self):
        """nullable=True allows NaN in column (ENG-19 regression)."""
        df = pd.DataFrame({"val": [1.0, None, 3.0]})
        schema = [{"name": "val", "type": "int", "nullable": True}]
        comp = ConcreteComponent("c1", {})
        result = comp.validate_schema(df, schema)
        assert result["val"].isna().sum() == 1  # NaN preserved

    def test_nullable_false_rejects_nan(self):
        """nullable=False with NaN raises DataValidationError."""
        df = pd.DataFrame({"val": [1.0, None, 3.0]})
        schema = [{"name": "val", "type": "int", "nullable": False}]
        comp = ConcreteComponent("c1", {})
        with pytest.raises(DataValidationError, match="not nullable"):
            comp.validate_schema(df, schema)

    def test_integer_type_coercion(self):
        """Integer type coercion works."""
        df = pd.DataFrame({"val": ["1", "2", "3"]})
        schema = [{"name": "val", "type": "int", "nullable": False}]
        comp = ConcreteComponent("c1", {})
        result = comp.validate_schema(df, schema)
        assert result["val"].dtype == "int64"

    def test_string_type_passthrough(self):
        """String type passes through (object or string dtype)."""
        df = pd.DataFrame({"val": ["hello", "world"]})
        schema = [{"name": "val", "type": "str", "nullable": True}]
        comp = ConcreteComponent("c1", {})
        result = comp.validate_schema(df, schema)
        # pandas 2.x may use StringDtype; both object and string are valid
        assert str(result["val"].dtype) in ("object", "string", "str")

    def test_empty_dataframe_returns_empty(self):
        """Empty DataFrame returns empty DataFrame."""
        df = pd.DataFrame()
        schema = [{"name": "val", "type": "int", "nullable": True}]
        comp = ConcreteComponent("c1", {})
        result = comp.validate_schema(df, schema)
        assert result.empty

    def test_missing_column_in_schema_ignored(self):
        """Missing column in schema is ignored (not errored)."""
        df = pd.DataFrame({"existing": [1, 2]})
        schema = [
            {"name": "existing", "type": "int", "nullable": False},
            {"name": "missing", "type": "str", "nullable": True},
        ]
        comp = ConcreteComponent("c1", {})
        result = comp.validate_schema(df, schema)
        assert "existing" in result.columns
        assert "missing" not in result.columns

    def test_nullable_true_integer_uses_nullable_dtype(self):
        """nullable=True integer with NaN uses pd.Int64Dtype (nullable int)."""
        df = pd.DataFrame({"val": [1.0, None, 3.0]})
        schema = [{"name": "val", "type": "int", "nullable": True}]
        comp = ConcreteComponent("c1", {})
        result = comp.validate_schema(df, schema)
        assert result["val"].dtype == pd.Int64Dtype()


# ------------------------------------------------------------------
# Tests: Stats
# ------------------------------------------------------------------


@pytest.mark.unit
class TestBaseComponentStats:
    """Stats accumulate correctly and push to GlobalMap."""

    def test_stats_accumulate_after_execute(self):
        """Stats accumulate after execute()."""
        df = pd.DataFrame({"x": [1, 2, 3]})
        comp = ConcreteComponent("c1", {})
        comp.execute(df)
        stats = comp.get_stats()
        assert stats["NB_LINE"] == 3
        assert stats["NB_LINE_OK"] == 3
        assert stats["NB_LINE_REJECT"] == 0

    def test_stats_pushed_to_global_map(self):
        """Stats pushed to GlobalMap via _update_global_map."""
        gm = GlobalMap()
        df = pd.DataFrame({"x": [1, 2]})
        comp = ConcreteComponent("c1", {}, global_map=gm)
        comp.execute(df)
        assert gm.get_component_stat("c1", "NB_LINE") == 2
        assert gm.get_component_stat("c1", "NB_LINE_OK") == 2

    def test_stats_correct_for_main_plus_reject(self):
        """Stats correct for main + reject counts."""
        df = pd.DataFrame({"x": range(10)})
        gm = GlobalMap()
        comp = RejectComponent("c1", {}, global_map=gm)
        comp.execute(df)
        stats = comp.get_stats()
        assert stats["NB_LINE"] == 10  # 5 main + 5 reject
        assert stats["NB_LINE_OK"] == 5
        assert stats["NB_LINE_REJECT"] == 5

    def test_stats_reset_to_zero_after_reset(self):
        """Stats reset to 0 after reset()."""
        df = pd.DataFrame({"x": [1, 2]})
        comp = ConcreteComponent("c1", {})
        comp.execute(df)
        assert comp.stats["NB_LINE"] == 2
        comp.reset()
        assert comp.stats["NB_LINE"] == 0
        assert comp.stats["NB_LINE_OK"] == 0
        assert comp.stats["NB_LINE_REJECT"] == 0


# ------------------------------------------------------------------
# Tests: Reset (Iterate Support)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestBaseComponentReset:
    """reset() clears stats, resets status, globalMap."""

    def test_reset_sets_status_to_pending(self):
        """reset() sets status to PENDING."""
        comp = ConcreteComponent("c1", {})
        comp.execute()
        assert comp.status == ComponentStatus.SUCCESS
        comp.reset()
        assert comp.status == ComponentStatus.PENDING

    def test_reset_zeros_stats(self):
        """reset() zeros stats."""
        df = pd.DataFrame({"x": [1, 2]})
        comp = ConcreteComponent("c1", {})
        comp.execute(df)
        comp.reset()
        assert comp.stats == {"NB_LINE": 0, "NB_LINE_OK": 0, "NB_LINE_REJECT": 0}

    def test_reset_calls_global_map_reset_component(self):
        """reset() calls globalMap.reset_component."""
        gm = GlobalMap()
        df = pd.DataFrame({"x": [1, 2]})
        comp = ConcreteComponent("c1", {}, global_map=gm)
        comp.execute(df)
        assert gm.get_component_stat("c1", "NB_LINE") == 2
        comp.reset()
        assert gm.get_component_stat("c1", "NB_LINE") == 0

    def test_execute_after_reset_works(self):
        """execute() after reset() works correctly (full lifecycle)."""
        df = pd.DataFrame({"x": [1, 2, 3]})
        comp = ConcreteComponent("c1", {})
        comp.execute(df)
        comp.reset()
        result = comp.execute(df)
        assert comp.status == ComponentStatus.SUCCESS
        assert result["main"] is not None
        assert comp.stats["NB_LINE"] == 3


# ------------------------------------------------------------------
# Tests: die_on_error subclass accessibility (Gemini review)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestBaseComponentDieOnError:
    """die_on_error must be accessible to subclasses for conditional error handling.

    Addresses Gemini review: verify die_on_error property is accessible to subclasses
    so they can decide whether to catch and swallow data-level exceptions before
    the template method execute() catches the Exception.
    """

    def test_die_on_error_defaults_to_true(self):
        """die_on_error defaults to True when not in config."""
        comp = ConcreteComponent("c1", {})
        comp.execute()
        assert comp.die_on_error is True

    def test_die_on_error_reads_from_config(self):
        """die_on_error reads from config when present."""
        comp = ConcreteComponent("c1", {"die_on_error": False})
        comp.execute()
        assert comp.die_on_error is False

    def test_subclass_accesses_die_on_error_in_process_lenient(self):
        """Subclass reads self.die_on_error=False in _process() and routes errors to reject."""
        gm = GlobalMap()
        comp = DieOnErrorAwareComponent(
            "c1", {"die_on_error": False, "force_error": True}, global_map=gm
        )
        result = comp.execute(pd.DataFrame({"x": [1]}))
        # In lenient mode, error is caught in _process, data routed to reject
        assert result["reject"] is not None
        assert comp.status == ComponentStatus.SUCCESS

    def test_subclass_accesses_die_on_error_in_process_strict(self):
        """Subclass reads self.die_on_error=True in _process() and lets error propagate."""
        comp = DieOnErrorAwareComponent(
            "c1", {"die_on_error": True, "force_error": True}
        )
        with pytest.raises(ComponentExecutionError):
            comp.execute(pd.DataFrame({"x": [1]}))
        assert comp.status == ComponentStatus.ERROR


# ------------------------------------------------------------------
# Tests: __repr__ (NEW-03)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestBaseComponentRepr:
    """__repr__ is correctly formatted."""

    def test_repr_includes_type_and_id(self):
        """__repr__ includes component type and id."""
        comp = ConcreteComponent("c1", {"component_type": "MyType"})
        r = repr(comp)
        assert "MyType" in r
        assert "c1" in r

    def test_repr_has_balanced_parentheses(self):
        """__repr__ has balanced parentheses (NEW-03 regression)."""
        comp = ConcreteComponent("c1", {})
        r = repr(comp)
        assert r.count("(") == r.count(")")

    def test_repr_includes_status(self):
        """__repr__ includes status."""
        comp = ConcreteComponent("c1", {})
        r = repr(comp)
        assert "pending" in r


# ------------------------------------------------------------------
# Tests: Execution Mode Selection
# ------------------------------------------------------------------


@pytest.mark.unit
class TestBaseComponentExecutionMode:
    """Execution mode is auto-selected or forced."""

    def test_default_mode_is_batch(self):
        """Default execution mode is BATCH."""
        comp = ConcreteComponent("c1", {})
        assert comp.execution_mode == ExecutionMode.BATCH

    def test_explicit_batch_mode(self):
        """Explicit batch mode in config."""
        comp = ConcreteComponent("c1", {"execution_mode": "batch"})
        comp.execute(pd.DataFrame({"x": [1]}))
        assert comp.status == ComponentStatus.SUCCESS

    def test_explicit_streaming_mode(self):
        """Explicit streaming mode in config."""
        df = pd.DataFrame({"x": range(10)})
        comp = ConcreteComponent(
            "c1", {"execution_mode": "streaming", "chunk_size": 3}
        )
        comp.execute(df)
        assert comp.status == ComponentStatus.SUCCESS

    def test_none_input_defaults_to_batch(self):
        """None input with hybrid mode defaults to batch."""
        comp = ConcreteComponent("c1", {"execution_mode": "hybrid"})
        comp.execute(None)
        assert comp.status == ComponentStatus.SUCCESS


# ------------------------------------------------------------------
# Tests: Named Flow Outputs (ENG-17)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestBaseComponentNamedFlows:
    """Components can return multiple named flow outputs."""

    def test_multi_output_returns_all_keys(self):
        """Multi-output component returns all named flow keys."""
        comp = MultiOutputComponent("c1", {})
        result = comp.execute()
        assert "main" in result
        assert "reject" in result
        assert "lookup" in result

    def test_multi_output_stats_include_all_flows(self):
        """Stats count both main and reject."""
        comp = MultiOutputComponent("c1", {})
        result = comp.execute()
        assert result["stats"]["NB_LINE_OK"] == 1  # main
        assert result["stats"]["NB_LINE_REJECT"] == 1  # reject


# ------------------------------------------------------------------
# Tests: BaseIterateComponent Lifecycle
# ------------------------------------------------------------------


@pytest.mark.unit
class TestBaseIterateComponentLifecycle:
    """Iterate component lifecycle: prepare, iterate, finalize."""

    def test_execute_calls_prepare_iterations(self):
        """execute() calls prepare_iterations."""
        gm = GlobalMap()
        comp = ConcreteIterateComponent("iter1", {"items": [10, 20]}, global_map=gm)
        comp.execute()
        assert comp.total_iterations == 2

    def test_has_next_iteration_true_when_items_remain(self):
        """has_next_iteration returns True when items remain."""
        gm = GlobalMap()
        comp = ConcreteIterateComponent("iter1", {"items": [1, 2]}, global_map=gm)
        comp.execute()
        assert comp.has_next_iteration() is True

    def test_get_next_iteration_context_advances(self):
        """get_next_iteration_context advances index and sets globalMap."""
        gm = GlobalMap()
        comp = ConcreteIterateComponent("iter1", {"items": ["a", "b"]}, global_map=gm)
        comp.execute()

        ctx1 = comp.get_next_iteration_context()
        assert ctx1["item"] == "a"
        assert ctx1["index"] == 1
        assert gm.get("iter1_CURRENT") == "a"

        ctx2 = comp.get_next_iteration_context()
        assert ctx2["item"] == "b"
        assert ctx2["index"] == 2
        assert gm.get("iter1_CURRENT") == "b"

    def test_has_next_iteration_false_after_all_consumed(self):
        """has_next_iteration returns False after all consumed."""
        gm = GlobalMap()
        comp = ConcreteIterateComponent("iter1", {"items": [1]}, global_map=gm)
        comp.execute()
        comp.get_next_iteration_context()
        assert comp.has_next_iteration() is False

    def test_finalize_iterations_updates_stats(self):
        """finalize_iterations updates stats."""
        gm = GlobalMap()
        comp = ConcreteIterateComponent("iter1", {"items": [1, 2, 3]}, global_map=gm)
        comp.execute()
        # Consume all iterations
        while comp.has_next_iteration():
            comp.get_next_iteration_context()
        comp.finalize_iterations()
        assert comp.stats["NB_LINE"] == 3
        assert comp.stats["NB_LINE_OK"] == 3

    def test_get_next_iteration_context_returns_empty_when_exhausted(self):
        """get_next_iteration_context returns empty dict when no more items."""
        gm = GlobalMap()
        comp = ConcreteIterateComponent("iter1", {"items": [1]}, global_map=gm)
        comp.execute()
        comp.get_next_iteration_context()  # consume the only item
        result = comp.get_next_iteration_context()
        assert result == {}

    def test_is_iterate_component_flag(self):
        """Iterate components have is_iterate_component=True."""
        comp = ConcreteIterateComponent("iter1", {})
        assert comp.is_iterate_component is True


# ------------------------------------------------------------------
# Tests: BaseIterateComponent Reset
# ------------------------------------------------------------------


@pytest.mark.unit
class TestBaseIterateComponentReset:
    """reset() clears iterate-specific state."""

    def test_reset_clears_iteration_items(self):
        """reset() clears iteration_items."""
        gm = GlobalMap()
        comp = ConcreteIterateComponent("iter1", {"items": [1, 2]}, global_map=gm)
        comp.execute()
        assert len(comp.iteration_items) == 2
        comp.reset()
        assert comp.iteration_items == []

    def test_reset_resets_current_index_to_zero(self):
        """reset() resets current_iteration_index to 0."""
        gm = GlobalMap()
        comp = ConcreteIterateComponent("iter1", {"items": [1, 2]}, global_map=gm)
        comp.execute()
        comp.get_next_iteration_context()
        assert comp.current_iteration_index == 1
        comp.reset()
        assert comp.current_iteration_index == 0

    def test_reset_resets_total_iterations_to_zero(self):
        """reset() resets total_iterations to 0."""
        gm = GlobalMap()
        comp = ConcreteIterateComponent("iter1", {"items": [1, 2]}, global_map=gm)
        comp.execute()
        assert comp.total_iterations == 2
        comp.reset()
        assert comp.total_iterations == 0

    def test_can_prepare_iterations_again_after_reset(self):
        """After reset, can prepare_iterations again."""
        gm = GlobalMap()
        comp = ConcreteIterateComponent("iter1", {"items": [1, 2]}, global_map=gm)
        comp.execute()
        comp.reset()
        comp.execute()
        assert comp.total_iterations == 2
        assert comp.has_next_iteration() is True

    def test_reset_clears_base_stats_too(self):
        """reset() clears both iterate-specific and base component state."""
        gm = GlobalMap()
        comp = ConcreteIterateComponent("iter1", {"items": [1, 2, 3]}, global_map=gm)
        comp.execute()
        comp.finalize_iterations()
        assert comp.stats["NB_LINE"] == 3
        comp.reset()
        assert comp.stats["NB_LINE"] == 0
        assert comp.status == ComponentStatus.PENDING


# ------------------------------------------------------------------
# Tests: Component Initialization
# ------------------------------------------------------------------


@pytest.mark.unit
class TestBaseComponentInit:
    """Component initialization edge cases."""

    def test_component_type_from_config(self):
        """component_type reads from config if present."""
        comp = ConcreteComponent("c1", {"component_type": "tMap"})
        assert comp.component_type == "tMap"

    def test_component_type_defaults_to_class_name(self):
        """component_type defaults to class name if not in config."""
        comp = ConcreteComponent("c1", {})
        assert comp.component_type == "ConcreteComponent"

    def test_initial_status_is_pending(self):
        """Initial status is PENDING."""
        comp = ConcreteComponent("c1", {})
        assert comp.status == ComponentStatus.PENDING

    def test_initial_stats_are_zero(self):
        """Initial stats are all zero."""
        comp = ConcreteComponent("c1", {})
        assert comp.stats == {"NB_LINE": 0, "NB_LINE_OK": 0, "NB_LINE_REJECT": 0}
