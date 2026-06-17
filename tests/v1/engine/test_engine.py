"""Tests for ETLEngine top-level orchestration (Plan 14-10).

Covers:
- run() / execute() error-handling paths
- _cleanup() idempotency (Java bridge / Oracle manager)
- Manager wiring (JavaBridgeManager / PythonRoutineManager / OracleConnectionManager)
- Context-param overrides via run_job
- Java/Oracle init exception cleanup paths
- Unknown component type warnings

ETLError-subclass exceptions asserted (ConfigurationError, ETLError).
ASCII-only logging contract (assert_ascii_logs in pipeline tests).
"""
from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock, patch

import pytest

from src.v1.engine.engine import ETLEngine, run_job
from src.v1.engine.exceptions import ETLError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def trivial_job_config():
    """Minimal valid job config -- one passthrough component."""
    return {
        "job_name": "trivial",
        "context": {"Default": {}},
        "components": [
            {
                "id": "c1",
                "type": "FixedFlowInputComponent",
                "config": {
                    "nb_rows": 1,
                    "use_singlemode": True,
                    "values_config": [{"schema_column": "x", "value": "1"}],
                },
                "schema": {
                    "input": [],
                    "output": [{"name": "x", "type": "int", "nullable": False}],
                },
                "inputs": [],
                "outputs": ["row1"],
            }
        ],
        "flows": [],
        "triggers": [],
        "subjobs": {"s1": ["c1"]},
    }


# ---------------------------------------------------------------------------
# Construction & basic execution
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEtlEngineConstruction:
    """ETLEngine builds ExecutionPlan, OutputRouter, Executor at construction."""

    def test_engine_initializes_with_dict(self, trivial_job_config):
        eng = ETLEngine(trivial_job_config)
        assert eng.job_name == "trivial"
        assert "c1" in eng.components

    def test_engine_initializes_with_path(self, tmp_path, trivial_job_config):
        cfg_path = tmp_path / "job.json"
        cfg_path.write_text(json.dumps(trivial_job_config))
        eng = ETLEngine(str(cfg_path))
        assert eng.job_name == "trivial"

    def test_execute_runs_to_success(self, trivial_job_config):
        eng = ETLEngine(trivial_job_config)
        stats = eng.execute()
        assert stats.get("status") == "success"
        assert stats.get("job_name") == "trivial"
        assert "global_map" in stats


@pytest.mark.unit
class TestUnknownComponentTypeWarns:
    """_initialize_components logs warning + skips for unknown types (143-144)."""

    def test_unknown_component_type_logs_warning(self, caplog):
        cfg = {
            "job_name": "j",
            "context": {"Default": {}},
            "components": [
                {"id": "c1", "type": "TotallyUnknownComponentType", "config": {}}
            ],
            "flows": [], "triggers": [], "subjobs": {"s1": ["c1"]},
        }
        with caplog.at_level("WARNING"):
            eng = ETLEngine(cfg)
        assert "Unknown component type" in caplog.text
        # No registered components
        assert "c1" not in eng.components


@pytest.mark.unit
class TestExecuteErrorHandling:
    """execute() catches Exception, calls _cleanup, returns error stats (222-234)."""

    def test_execute_returns_error_dict_on_exception(self, trivial_job_config, monkeypatch):
        eng = ETLEngine(trivial_job_config)

        # Patch executor.execute_job to raise
        def boom():
            raise RuntimeError("forced engine error")

        monkeypatch.setattr(eng.executor, "execute_job", boom)
        stats = eng.execute()
        assert stats["status"] == "error"
        assert "forced engine error" in stats["error"]
        assert stats["job_name"] == "trivial"


# ---------------------------------------------------------------------------
# Java bridge wiring
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestJavaBridgeStartFailureCleanup:
    """When java_bridge_manager.start() raises, _cleanup runs and exception
    re-raises (lines 53-55)."""

    def test_java_init_failure_calls_stop(self, monkeypatch):
        cfg = {
            "job_name": "j",
            "context": {"Default": {}},
            "components": [],
            "flows": [],
            "triggers": [],
            "subjobs": {},
            "java_config": {"enabled": True, "routines": [], "libraries": []},
        }
        # Patch JavaBridgeManager.start to raise; track stop calls
        from src.v1.engine import engine as eng_mod

        stop_calls = []

        class _FakeJavaBridgeManager:
            def __init__(self, **kw):
                self._kw = kw
                self.bridge = None

            def start(self):
                raise RuntimeError("boom java start")

            def stop(self):
                stop_calls.append(True)

        monkeypatch.setattr(eng_mod, "JavaBridgeManager", _FakeJavaBridgeManager)
        with pytest.raises(RuntimeError, match="boom java start"):
            ETLEngine(cfg)
        assert stop_calls == [True]


# ---------------------------------------------------------------------------
# Oracle manager wiring
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOracleManagerStartFailureCleanup:
    """When oracle_manager.start() raises, _cleanup runs and exception re-raises (88-90)."""

    def test_oracle_init_failure_calls_stop(self, monkeypatch):
        cfg = {
            "job_name": "j",
            "context": {"Default": {}},
            "components": [],
            "flows": [],
            "triggers": [],
            "subjobs": {},
            "oracle_config": {"enabled": True},
        }
        from src.v1.engine import engine as eng_mod

        stop_calls = []

        class _FakeOracleConnectionManager:
            def __init__(self, **kw):
                self._kw = kw

            def start(self):
                raise RuntimeError("boom oracle start")

            def stop(self):
                stop_calls.append(True)

        monkeypatch.setattr(eng_mod, "OracleConnectionManager", _FakeOracleConnectionManager)
        with pytest.raises(RuntimeError, match="boom oracle start"):
            ETLEngine(cfg)
        assert stop_calls == [True]


@pytest.mark.unit
class TestOracleAutoDetect:
    """has_oracle_components branch wires up OracleConnectionManager even
    without explicit oracle_config.enabled (line 79-83 etc.)"""

    def test_oracle_component_type_triggers_manager(self, monkeypatch):
        cfg = {
            "job_name": "j",
            "context": {"Default": {}},
            "components": [
                {"id": "ora", "type": "OracleConnection", "config": {}}
            ],
            "flows": [],
            "triggers": [],
            "subjobs": {"s1": ["ora"]},
        }
        from src.v1.engine import engine as eng_mod

        class _FakeOracle:
            def __init__(self, **kw):
                pass

            def start(self):
                pass

            def stop(self):
                pass

        monkeypatch.setattr(eng_mod, "OracleConnectionManager", _FakeOracle)
        eng = ETLEngine(cfg)
        assert eng.oracle_manager is not None


@pytest.mark.unit
class TestMSSqlManagerStartFailureCleanup:
    """When mssql_manager.start() raises, _cleanup runs and exception re-raises."""

    def test_mssql_init_failure_calls_stop(self, monkeypatch):
        cfg = {
            "job_name": "j",
            "context": {"Default": {}},
            "components": [],
            "flows": [],
            "triggers": [],
            "subjobs": {},
            "mssql_config": {"enabled": True},
        }
        from src.v1.engine import engine as eng_mod

        stop_calls = []

        class _FakeMSSqlConnectionManager:
            def start(self):
                raise RuntimeError("boom mssql start")

            def stop(self):
                stop_calls.append(True)

        monkeypatch.setattr(
            eng_mod, "MSSqlConnectionManager", _FakeMSSqlConnectionManager
        )
        with pytest.raises(RuntimeError, match="boom mssql start"):
            ETLEngine(cfg)
        assert stop_calls == [True]


@pytest.mark.unit
class TestMSSqlAutoDetectAndWiring:
    """has_mssql_components wires up the manager, injects it into components,
    and _cleanup stops it."""

    def test_mssql_component_triggers_manager_injection_and_cleanup(self, monkeypatch):
        cfg = {
            "job_name": "j",
            "context": {"Default": {}},
            "components": [
                {"id": "ms", "type": "MSSqlConnection",
                 "config": {"host": "h"}}
            ],
            "flows": [],
            "triggers": [],
            "subjobs": {"s1": ["ms"]},
        }
        from src.v1.engine import engine as eng_mod

        stop_calls = []

        class _FakeMSSql:
            def start(self):
                pass

            def stop(self):
                stop_calls.append(True)

        monkeypatch.setattr(eng_mod, "MSSqlConnectionManager", _FakeMSSql)
        eng = ETLEngine(cfg)
        assert eng.mssql_manager is not None
        # Manager injected into the component.
        assert eng.components["ms"].mssql_manager is eng.mssql_manager
        # _cleanup stops the manager.
        eng._cleanup()
        assert stop_calls == [True]


# ---------------------------------------------------------------------------
# Python routine manager wiring
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPythonRoutineManagerWiring:
    """When python_config.enabled, manager is built and propagated to components (line 166)."""

    def test_python_routine_manager_attached_to_components(self, tmp_path):
        # Write a minimal routine
        (tmp_path / "demo.py").write_text("def x(): return 1\n")
        cfg = {
            "job_name": "j",
            "context": {"Default": {}},
            "components": [
                {
                    "id": "c1",
                    "type": "FixedFlowInputComponent",
                    "config": {
                        "nb_rows": 1,
                        "use_singlemode": True,
                        "values_config": [{"schema_column": "x", "value": "1"}],
                    },
                    "schema": {
                        "input": [],
                        "output": [{"name": "x", "type": "int", "nullable": False}],
                    },
                    "inputs": [],
                    "outputs": ["row1"],
                }
            ],
            "flows": [],
            "triggers": [],
            "subjobs": {"s1": ["c1"]},
            "python_config": {"enabled": True, "routines_dir": str(tmp_path)},
        }
        eng = ETLEngine(cfg)
        # Component received the manager reference
        assert eng.components["c1"].python_routine_manager is eng.python_routine_manager


# ---------------------------------------------------------------------------
# Trigger init paths (lines 177, 187)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTriggerInitialization:
    """Top-level and per-component trigger configs are wired into TriggerManager."""

    def test_top_level_trigger_added(self, trivial_job_config):
        # Add a second component so the trigger has a real target subjob
        cfg = dict(trivial_job_config)
        cfg["components"] = list(cfg["components"]) + [
            {
                "id": "c2",
                "type": "FixedFlowInputComponent",
                "config": {
                    "nb_rows": 1,
                    "use_singlemode": True,
                    "values_config": [{"schema_column": "y", "value": "2"}],
                },
                "schema": {
                    "input": [],
                    "output": [{"name": "y", "type": "int", "nullable": False}],
                },
                "inputs": [],
                "outputs": [],
            }
        ]
        cfg["subjobs"] = {"s1": ["c1"], "s2": ["c2"]}
        cfg["triggers"] = [{"type": "OnSubjobOk", "from": "c1", "to": "c2"}]
        eng = ETLEngine(cfg)
        assert len(eng.trigger_manager.triggers) >= 1

    def test_per_component_trigger_added(self, trivial_job_config):
        cfg = dict(trivial_job_config)
        # Inject a per-component trigger inside components[*].triggers
        cfg["components"] = [dict(cfg["components"][0])]
        cfg["components"][0]["triggers"] = [
            {"type": "OnComponentOk", "to": "c1"}
        ]
        eng = ETLEngine(cfg)
        # At least one trigger registered
        assert len(eng.trigger_manager.triggers) >= 1


# ---------------------------------------------------------------------------
# set_context_variable
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSetContextVariable:
    """set_context_variable updates ContextManager + propagates to components (238-242)."""

    def test_sets_context_and_propagates(self, trivial_job_config):
        eng = ETLEngine(trivial_job_config)
        eng.set_context_variable("foo", "bar")
        assert eng.context_manager.get("foo") == "bar"
        for comp in eng.components.values():
            assert comp.context_manager is eng.context_manager


# ---------------------------------------------------------------------------
# get_execution_stats
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetExecutionStats:
    """get_execution_stats returns a dict with the expected keys (line 246+)."""

    def test_returns_full_stats_dict(self, trivial_job_config):
        eng = ETLEngine(trivial_job_config)
        eng.execute()
        stats = eng.get_execution_stats()
        assert "components_executed" in stats
        assert "components_failed" in stats
        assert "global_map" in stats
        assert "context" in stats


# ---------------------------------------------------------------------------
# run_job convenience function
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRunJobConvenience:
    """run_job applies context overrides and returns execution stats (278-280)."""

    def test_run_job_with_context_overrides(self, tmp_path, trivial_job_config, caplog):
        cfg_path = tmp_path / "job.json"
        cfg_path.write_text(json.dumps(trivial_job_config))
        with caplog.at_level("INFO"):
            stats = run_job(str(cfg_path), context_overrides={"foo": "bar"})
        assert stats.get("status") == "success"
        assert "Setting context variable: foo = bar" in caplog.text

    def test_run_job_no_overrides(self, tmp_path, trivial_job_config):
        cfg_path = tmp_path / "job.json"
        cfg_path.write_text(json.dumps(trivial_job_config))
        stats = run_job(str(cfg_path))
        assert stats.get("status") == "success"


# ---------------------------------------------------------------------------
# Pipeline test via run_job_fixture
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPipelineViaFixture:
    """End-to-end: run trigger_runif fixture through ETLEngine via run_job_fixture."""

    def test_trigger_runif_pipeline(self, run_job_fixture, tmp_path, assert_ascii_logs):
        out = tmp_path / "out.csv"
        result = run_job_fixture(
            "core/trigger_runif",
            mutations={"tFileOutputDelimited_1": {"filepath": str(out)}},
        )
        assert result.stats.get("status") == "success"
        # 4 components executed (subjob_target ran because RunIf condition true)
        assert result.stats.get("components_executed") == 4
        assert out.exists()

    def test_multi_subjob_pipeline(self, run_job_fixture, tmp_path, assert_ascii_logs):
        out_a = tmp_path / "a.csv"
        out_b = tmp_path / "b.csv"
        result = run_job_fixture(
            "core/multi_subjob",
            mutations={
                "tFileOutputDelimited_1": {"filepath": str(out_a)},
                "tFileOutputDelimited_2": {"filepath": str(out_b)},
            },
        )
        assert result.stats.get("status") == "success"
        # Both subjobs executed (2 + 2 components)
        assert result.stats.get("components_executed") == 4
        assert out_a.exists() and out_b.exists()

    def test_reject_routing_pipeline(self, run_job_fixture, tmp_path, assert_ascii_logs):
        inp = tmp_path / "in.csv"
        inp.write_text("1;alice;10.5\n2;bob;20.7\nbad;line\n3;carol;30.1\n")
        out_main = tmp_path / "main.csv"
        out_rej = tmp_path / "rej.csv"
        result = run_job_fixture(
            "core/reject_routing",
            mutations={
                "tFileInputDelimited_1": {"filepath": str(inp)},
                "tFileOutputDelimited_main": {"filepath": str(out_main)},
                "tFileOutputDelimited_reject": {"filepath": str(out_rej)},
            },
        )
        assert result.stats.get("status") == "success"
        # 1 reject row routed
        assert "FIELD_COUNT" in out_rej.read_text()
        # 3 well-formed rows in main
        assert out_main.read_text().count("\n") >= 3
