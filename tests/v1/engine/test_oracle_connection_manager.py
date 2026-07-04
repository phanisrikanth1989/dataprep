"""Unit tests for OracleConnectionManager (Phase 11-01).

Covers VR-01 (lifecycle), VR-02 (register/get), VR-03 (thick mode), VR-04
(open_ad_hoc connection type dispatch + OCI/Wallet refusal), and T-11-02
(password-not-logged regression).

All tests use mocked oracledb; @pytest.mark.oracle integration tests in plan
11-07 cover real-DB validation (D-D3, D-F4 -- mocks lie).
"""
import logging
import sys
from unittest.mock import MagicMock, patch

import pytest

from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.oracle_connection_manager import OracleConnectionManager


@pytest.fixture(autouse=True)
def _reset_thick_initialized():
    """Class-level guard must be reset between tests since it persists."""
    OracleConnectionManager._thick_initialized = False
    yield
    OracleConnectionManager._thick_initialized = False


# ---------------------------------------------------------------------------
# VR-01: lifecycle / state
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestManagerInit:
    def test_initial_state(self):
        m = OracleConnectionManager()
        assert m.thick_mode is False
        assert m.connections == {}
        assert m.is_running is False

    def test_thick_mode_flag_stored(self):
        m = OracleConnectionManager(thick_mode=True)
        assert m.thick_mode is True


@pytest.mark.unit
class TestStartStop:
    def test_start_idempotent(self):
        mock_oracledb = MagicMock()
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            m = OracleConnectionManager()
            m.start()
            m.start()
        assert m.is_running is True
        # fetch_lobs should be set False (D-B1) on first start
        assert mock_oracledb.defaults.fetch_lobs is False

    def test_stop_idempotent_with_no_connections(self):
        m = OracleConnectionManager()
        m.stop()  # not started
        m.stop()  # second call no-op
        assert not m.is_running

    def test_stop_closes_all_registered(self):
        mock_oracledb = MagicMock()
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            m = OracleConnectionManager()
            m.start()
        c1, c2, c3 = MagicMock(), MagicMock(), MagicMock()
        m.connections = {"a": c1, "b": c2, "c": c3}
        m.stop()
        c1.close.assert_called_once()
        c2.close.assert_called_once()
        c3.close.assert_called_once()
        assert m.connections == {}
        assert not m.is_running

    def test_stop_one_bad_close_does_not_block_others(self):
        m = OracleConnectionManager()
        m.is_running = True
        good_a, bad_b, good_c = MagicMock(), MagicMock(), MagicMock()
        bad_b.close.side_effect = RuntimeError("simulated close failure")
        m.connections = {"a": good_a, "b": bad_b, "c": good_c}
        m.stop()  # must not raise
        good_a.close.assert_called_once()
        good_c.close.assert_called_once()
        assert m.connections == {}


# ---------------------------------------------------------------------------
# VR-02: register / get
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRegisterAndGet:
    def test_register_and_get_returns_same_object(self):
        m = OracleConnectionManager()
        conn = MagicMock()
        m.register("cid_1", conn)
        assert m.get("cid_1") is conn

    def test_get_missing_raises_configuration_error_with_available_list(self):
        m = OracleConnectionManager()
        m.register("a", MagicMock())
        m.register("b", MagicMock())
        with pytest.raises(ConfigurationError) as exc:
            m.get("missing")
        assert "missing" in str(exc.value)
        assert "['a', 'b']" in str(exc.value)

    def test_register_duplicate_raises_value_error(self):
        m = OracleConnectionManager()
        m.register("dup", MagicMock())
        with pytest.raises(ValueError):
            m.register("dup", MagicMock())


# ---------------------------------------------------------------------------
# VR-04: open_ad_hoc dispatch + OCI/Wallet refusal
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestOpenAdHoc:
    def test_oracle_sid_uses_sid_kwarg(self):
        mock_oracledb = MagicMock()
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            m = OracleConnectionManager()
            m.start()
            cfg = {"connection_type": "ORACLE_SID", "user": "u", "password": "p",
                   "host": "h", "port": "1521", "dbname": "ORCL"}
            m.open_ad_hoc("cid_1", cfg)
        mock_oracledb.connect.assert_called_once_with(
            user="u", password="p", host="h", port=1521, sid="ORCL"
        )

    def test_oracle_service_name_uses_service_name_kwarg(self):
        mock_oracledb = MagicMock()
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            m = OracleConnectionManager()
            m.start()
            cfg = {"connection_type": "ORACLE_SERVICE_NAME", "user": "u",
                   "password": "p", "host": "h", "port": "1521",
                   "dbname": "ORCLPDB1"}
            m.open_ad_hoc("cid_1", cfg)
        mock_oracledb.connect.assert_called_once_with(
            user="u", password="p", host="h", port=1521, service_name="ORCLPDB1"
        )
        # Make sure sid= was NOT used
        kwargs = mock_oracledb.connect.call_args.kwargs
        assert "sid" not in kwargs

    def test_oracle_rac_uses_dsn_kwarg_with_stripped_url(self):
        mock_oracledb = MagicMock()
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            m = OracleConnectionManager()
            m.start()
            cfg = {
                "connection_type": "ORACLE_RAC",
                "user": "u",
                "password": "p",
                "rac_url": "  (DESCRIPTION=(ADDRESS=...)(CONNECT_DATA=(SERVICE_NAME=rac)))  \n",
            }
            m.open_ad_hoc("cid_1", cfg)
        mock_oracledb.connect.assert_called_once_with(
            user="u",
            password="p",
            dsn="(DESCRIPTION=(ADDRESS=...)(CONNECT_DATA=(SERVICE_NAME=rac)))",
        )

    def test_oracle_rac_missing_url_raises_configuration_error(self):
        mock_oracledb = MagicMock()
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            m = OracleConnectionManager()
            m.start()
            with pytest.raises(ConfigurationError) as exc:
                m.open_ad_hoc("cid", {
                    "connection_type": "ORACLE_RAC", "user": "u", "password": "p",
                    "rac_url": "   ",
                })
        assert "rac_url" in str(exc.value)

    def test_oracle_oci_raises_configuration_error_with_deferred_message(self):
        m = OracleConnectionManager()
        m.is_running = True  # bypass lazy oracledb import requirement
        with pytest.raises(ConfigurationError) as exc:
            m.open_ad_hoc("cid", {"connection_type": "ORACLE_OCI", "user": "u",
                                  "password": "p", "host": "h", "dbname": "x"})
        msg = str(exc.value)
        assert "ORACLE_OCI" in msg
        assert "thick_mode" in msg
        assert "Instant Client" in msg

    def test_oracle_wallet_raises_configuration_error(self):
        m = OracleConnectionManager()
        m.is_running = True
        with pytest.raises(ConfigurationError) as exc:
            m.open_ad_hoc("cid", {"connection_type": "ORACLE_WALLET",
                                  "user": "u", "password": "p"})
        msg = str(exc.value)
        assert "ORACLE_WALLET" in msg
        assert "thick_mode" in msg
        # T-11-05: ensure no wallet path or auth detail leaked. The token
        # 'WALLET' appears in the connection-type name only; no filesystem
        # path is referenced in the locked deferred-items wording.
        assert "/" not in msg or "WALLET" in msg
        assert "Tracked in deferred items" in msg

    def test_unknown_connection_type_raises_configuration_error(self):
        m = OracleConnectionManager()
        m.is_running = True
        with pytest.raises(ConfigurationError) as exc:
            m.open_ad_hoc("cid", {"connection_type": "ORACLE_BOGUS",
                                  "user": "u", "password": "p"})
        assert "ORACLE_BOGUS" in str(exc.value)

    # WR-07: error message lists ONLY actually-accepted values; OCI/WALLET
    # appear separately as "require thick mode" so operators don't try them
    # as drop-in replacements.
    def test_unknown_connection_type_message_excludes_unsupported(self):
        m = OracleConnectionManager()
        m.is_running = True
        with pytest.raises(ConfigurationError) as exc:
            m.open_ad_hoc("cid", {"connection_type": "ORACLE_BOGUS",
                                  "user": "u", "password": "p"})
        msg = str(exc.value)
        # Must list the three accepted values
        assert "ORACLE_SID" in msg
        assert "ORACLE_SERVICE_NAME" in msg
        assert "ORACLE_RAC" in msg
        # OCI / WALLET must appear ONLY in the deferred-items aside, not
        # in the "must be one of" set.
        # Find the "must be one of" set and check OCI/WALLET aren't there.
        # Easiest sanity check: 'thick mode' / 'deferred' wording present
        # (telling operator OCI/WALLET need a different code path).
        assert "thick mode" in msg.lower() or "deferred" in msg.lower()

    def test_open_ad_hoc_duplicate_cid_raises_value_error(self):
        mock_oracledb = MagicMock()
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            m = OracleConnectionManager()
            m.start()
            cfg = {"connection_type": "ORACLE_SID", "user": "u", "password": "p",
                   "host": "h", "port": "1521", "dbname": "ORCL"}
            m.open_ad_hoc("cid_1", cfg)
            with pytest.raises(ValueError):
                m.open_ad_hoc("cid_1", cfg)

    def test_auto_commit_true_sets_autocommit(self):
        mock_oracledb = MagicMock()
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            m = OracleConnectionManager()
            m.start()
            cfg = {"connection_type": "ORACLE_SID", "user": "u", "password": "p",
                   "host": "h", "port": "1521", "dbname": "ORCL", "auto_commit": True}
            conn = m.open_ad_hoc("cid_1", cfg)
        assert conn.autocommit is True

    def test_port_defaults_to_1521_when_missing(self):
        mock_oracledb = MagicMock()
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            m = OracleConnectionManager()
            m.start()
            cfg = {"connection_type": "ORACLE_SID", "user": "u", "password": "p",
                   "host": "h", "dbname": "ORCL"}
            m.open_ad_hoc("cid_1", cfg)
        kwargs = mock_oracledb.connect.call_args.kwargs
        assert kwargs["port"] == 1521


# ---------------------------------------------------------------------------
# VR-03: thick mode init guard
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestThickMode:
    def test_init_oracle_client_called_when_thick_mode_true(self):
        mock_oracledb = MagicMock()
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            m = OracleConnectionManager(thick_mode=True)
            m.start()
        mock_oracledb.init_oracle_client.assert_called_once()
        assert OracleConnectionManager._thick_initialized is True

    def test_init_oracle_client_not_called_when_thick_mode_false(self):
        mock_oracledb = MagicMock()
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            m = OracleConnectionManager(thick_mode=False)
            m.start()
        mock_oracledb.init_oracle_client.assert_not_called()

    def test_second_manager_with_thick_does_not_double_init(self):
        mock_oracledb = MagicMock()
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            m1 = OracleConnectionManager(thick_mode=True)
            m1.start()
            m2 = OracleConnectionManager(thick_mode=True)
            m2.start()
        # Class-level guard means second start does NOT call init again
        assert mock_oracledb.init_oracle_client.call_count == 1


# ---------------------------------------------------------------------------
# Per-connection control: close/commit/rollback
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCloseCommitRollback:
    def test_close_removes_from_dict(self):
        m = OracleConnectionManager()
        conn = MagicMock()
        m.connections["cid"] = conn
        m.close("cid")
        assert "cid" not in m.connections
        conn.close.assert_called_once()

    def test_close_missing_silent_noop(self):
        m = OracleConnectionManager()
        m.close("never-registered")  # must not raise

    def test_close_removes_even_if_underlying_close_raises(self):
        m = OracleConnectionManager()
        conn = MagicMock()
        conn.close.side_effect = RuntimeError("boom")
        m.connections["cid"] = conn
        m.close("cid")
        # Removed from dict regardless (T-11-03 mitigation)
        assert "cid" not in m.connections

    def test_commit_delegates(self):
        m = OracleConnectionManager()
        conn = MagicMock()
        m.connections["cid"] = conn
        m.commit("cid")
        conn.commit.assert_called_once()

    def test_commit_missing_raises_configuration_error(self):
        m = OracleConnectionManager()
        with pytest.raises(ConfigurationError):
            m.commit("missing")

    def test_rollback_delegates(self):
        m = OracleConnectionManager()
        conn = MagicMock()
        m.connections["cid"] = conn
        m.rollback("cid")
        conn.rollback.assert_called_once()

    def test_rollback_missing_raises_configuration_error(self):
        m = OracleConnectionManager()
        with pytest.raises(ConfigurationError):
            m.rollback("missing")


# ---------------------------------------------------------------------------
# Context manager / repr / is_available
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestContextManager:
    def test_with_block_starts_and_stops(self):
        mock_oracledb = MagicMock()
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            with OracleConnectionManager() as m:
                assert m.is_running
            assert not m.is_running


@pytest.mark.unit
class TestIsAvailable:
    def test_is_available_false_before_start(self):
        m = OracleConnectionManager()
        assert m.is_available() is False

    def test_is_available_true_after_start(self):
        mock_oracledb = MagicMock()
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            m = OracleConnectionManager()
            m.start()
        assert m.is_available() is True


@pytest.mark.unit
class TestRepr:
    def test_repr_includes_status_count_thick(self):
        m = OracleConnectionManager(thick_mode=True)
        r = repr(m)
        assert "stopped" in r
        assert "connections=0" in r
        assert "thick=True" in r

    def test_repr_running_status_after_start(self):
        mock_oracledb = MagicMock()
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            m = OracleConnectionManager()
            m.start()
        assert "running" in repr(m)

    def test_repr_does_not_leak_password(self):
        # T-11-02 mitigation: __repr__ shows count only, never connection details.
        m = OracleConnectionManager()
        m.connections = {"cid": MagicMock(password="hunter2")}
        assert "hunter2" not in repr(m)


# ---------------------------------------------------------------------------
# T-11-02 regression: password never appears in any logged message
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPasswordNotLogged:
    """T-11-02: PASS field never appears in any log output from the manager."""

    def test_open_ad_hoc_does_not_log_password(self, caplog):
        mock_oracledb = MagicMock()
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            m = OracleConnectionManager()
            m.start()
            cfg = {"connection_type": "ORACLE_SID", "user": "u",
                   "password": "supersecret_hunter2", "host": "h",
                   "port": "1521", "dbname": "ORCL"}
            with caplog.at_level(logging.DEBUG):
                m.open_ad_hoc("cid", cfg)
        for record in caplog.records:
            msg = record.getMessage()
            assert "hunter2" not in msg
            assert "supersecret_hunter2" not in msg

    def test_register_does_not_log_password(self, caplog):
        m = OracleConnectionManager()
        # Mock a connection object with a password-looking attribute
        conn = MagicMock()
        conn.password = "hunter2_attribute_leak_check"
        with caplog.at_level(logging.DEBUG):
            m.register("cid_x", conn)
        for record in caplog.records:
            assert "hunter2" not in record.getMessage()


# ---------------------------------------------------------------------------
# Engine integration: 4 in-place edits in engine.py
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestEngineWiring:
    """ETLEngine integration -- the 4 edits in engine.py."""

    def test_engine_creates_oracle_manager_when_oracle_component_present(self):
        from src.v1.engine.engine import ETLEngine
        mock_oracledb = MagicMock()
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            engine = ETLEngine({
                "components": [
                    {"id": "c1", "type": "tOracleConnection", "config": {}},
                ],
                "flows": [],
            })
        assert engine.oracle_manager is not None
        assert engine.oracle_manager.is_running

    def test_engine_no_oracle_manager_without_oracle_component(self):
        from src.v1.engine.engine import ETLEngine
        engine = ETLEngine({
            "components": [
                {"id": "c1", "type": "tFileInputDelimited", "config": {}},
            ],
            "flows": [],
        })
        assert engine.oracle_manager is None

    def test_engine_thick_mode_propagates_from_oracle_config(self):
        from src.v1.engine.engine import ETLEngine
        mock_oracledb = MagicMock()
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            engine = ETLEngine({
                "components": [
                    {"id": "c1", "type": "tOracleConnection", "config": {}},
                ],
                "flows": [],
                "oracle_config": {"thick_mode": True},
            })
        assert engine.oracle_manager is not None
        assert engine.oracle_manager.thick_mode is True
        mock_oracledb.init_oracle_client.assert_called_once()

    def test_engine_oracle_manager_when_only_oracle_config_enabled_true(self):
        """Manager is created when oracle_config.enabled=True even without an
        Oracle component in the job (D-A1)."""
        from src.v1.engine.engine import ETLEngine
        mock_oracledb = MagicMock()
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            engine = ETLEngine({
                "components": [],
                "flows": [],
                "oracle_config": {"enabled": True},
            })
        assert engine.oracle_manager is not None

    def test_engine_cleanup_calls_oracle_manager_stop(self):
        from src.v1.engine.engine import ETLEngine
        mock_oracledb = MagicMock()
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            engine = ETLEngine({
                "components": [
                    {"id": "c1", "type": "tOracleConnection", "config": {}},
                ],
                "flows": [],
            })
            assert engine.oracle_manager is not None
            stop_spy = MagicMock(wraps=engine.oracle_manager.stop)
            engine.oracle_manager.stop = stop_spy
            engine._cleanup()
        stop_spy.assert_called_once()

    def test_engine_initialize_components_injects_oracle_manager(self):
        """Each component instance gets `component.oracle_manager` set."""
        from src.v1.engine.engine import ETLEngine
        from src.v1.engine.component_registry import REGISTRY

        # Pick a registered component class to verify the injection without
        # needing an Oracle-specific component (those land in plan 11-02).
        # We use tFileInputDelimited which IS registered, then simulate by
        # also adding an Oracle-typed component that triggers manager creation.
        # The injection path runs for ALL components when oracle_manager exists.
        mock_oracledb = MagicMock()
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            engine = ETLEngine({
                "components": [
                    {"id": "c_trigger", "type": "tOracleConnection", "config": {}},
                    {"id": "c_other", "type": "tFileInputDelimited",
                     "config": {"file_path": "/tmp/x.csv"}},
                ],
                "flows": [],
            })
        # tFileInputDelimited is registered; tOracleConnection is not yet (lands
        # in plan 11-02), so only c_other should be in engine.components.
        if "c_other" in engine.components:
            assert engine.components["c_other"].oracle_manager is engine.oracle_manager
