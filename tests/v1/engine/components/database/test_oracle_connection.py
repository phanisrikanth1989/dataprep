"""Unit tests for OracleConnection engine component (Phase 11-02).

Mock-based tests cover registration, structural validation, content checks
(OCI / Wallet refusal), AUTO_COMMIT, globalMap metadata strings, and the
T-11-02 password-not-logged regression.

Real-DB validation lives in plan 11-07's @pytest.mark.oracle integration tests
(D-D3, D-F4 -- mocks lie).
"""
import logging
import sys
from unittest.mock import MagicMock, patch

import pytest

from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


def _make_component(config, oracle_manager=None, global_map=None):
    """Build an OracleConnection with config already populated as the
    working ``self.config`` (skipping the BaseComponent execute() lifecycle).

    The plan's tests call ``_validate_config`` and ``_process`` directly, so
    we mirror BaseComponent.execute()'s side-effect of seeding ``self.config``
    from ``_original_config``.
    """
    from src.v1.engine.components.database.oracle_connection import OracleConnection

    gm = global_map if global_map is not None else GlobalMap()
    comp = OracleConnection(
        component_id="tOracleConnection_1",
        config=config,
        global_map=gm,
        context_manager=ContextManager(),
    )
    # BaseComponent.execute() repopulates self.config; in unit tests we skip
    # execute() and seed it directly.
    comp.config = dict(config)
    comp.oracle_manager = (
        oracle_manager if oracle_manager is not None else MagicMock()
    )
    return comp


def _valid_sid_config(**overrides):
    cfg = {
        "connection_type": "ORACLE_SID",
        "host": "h",
        "port": "1521",
        "dbname": "ORCL",
        "user": "u",
        "password": "secret_hunter2",
        "schema_db": "HR",
    }
    cfg.update(overrides)
    return cfg


@pytest.mark.unit
class TestRegistration:
    def test_all_three_aliases_resolve_to_oracle_connection(self):
        from src.v1.engine.components import database  # noqa: F401 -- triggers registration
        from src.v1.engine.component_registry import REGISTRY
        from src.v1.engine.components.database.oracle_connection import OracleConnection

        assert REGISTRY.get("OracleConnection") is OracleConnection
        assert REGISTRY.get("tOracleConnection") is OracleConnection
        assert REGISTRY.get("tDBConnection") is OracleConnection


@pytest.mark.unit
class TestValidateConfig:
    def test_invalid_connection_type_raises(self):
        comp = _make_component(_valid_sid_config(connection_type="ORACLE_BOGUS"))
        with pytest.raises(ConfigurationError) as exc:
            comp._validate_config()
        assert "ORACLE_BOGUS" in str(exc.value)

    def test_missing_user_raises(self):
        cfg = _valid_sid_config()
        del cfg["user"]
        comp = _make_component(cfg)
        with pytest.raises(ConfigurationError) as exc:
            comp._validate_config()
        assert "user" in str(exc.value)

    def test_missing_password_raises(self):
        cfg = _valid_sid_config()
        del cfg["password"]
        comp = _make_component(cfg)
        with pytest.raises(ConfigurationError):
            comp._validate_config()

    def test_oci_passes_validate_config(self):
        """OCI is a CONTENT check (lives in _process), not a structural one (Rule 12)."""
        comp = _make_component(_valid_sid_config(connection_type="ORACLE_OCI"))
        comp._validate_config()  # must NOT raise


@pytest.mark.unit
class TestProcessOracleSid:
    def test_calls_oracledb_connect_with_sid_kwargs(self):
        mock_oracledb = MagicMock()
        mock_conn = MagicMock(autocommit=False)
        mock_oracledb.connect.return_value = mock_conn
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            comp = _make_component(_valid_sid_config())
            comp._process(None)
        mock_oracledb.connect.assert_called_once_with(
            user="u",
            password="secret_hunter2",
            host="h",
            port=1521,
            sid="ORCL",
        )

    def test_registers_connection_with_manager(self):
        mock_oracledb = MagicMock()
        mock_conn = MagicMock(autocommit=False)
        mock_oracledb.connect.return_value = mock_conn
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            comp = _make_component(_valid_sid_config())
            comp._process(None)
        comp.oracle_manager.register.assert_called_once_with(
            "tOracleConnection_1", mock_conn
        )

    def test_returns_orchestration_shape(self):
        mock_oracledb = MagicMock()
        mock_oracledb.connect.return_value = MagicMock(autocommit=False)
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            comp = _make_component(_valid_sid_config())
            result = comp._process(None)
        assert result == {"main": None, "reject": None}


@pytest.mark.unit
class TestProcessOracleServiceName:
    def test_uses_service_name_kwarg(self):
        mock_oracledb = MagicMock()
        mock_oracledb.connect.return_value = MagicMock(autocommit=False)
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            comp = _make_component(
                _valid_sid_config(connection_type="ORACLE_SERVICE_NAME")
            )
            comp._process(None)
        call_kwargs = mock_oracledb.connect.call_args.kwargs
        assert "service_name" in call_kwargs
        assert "sid" not in call_kwargs


@pytest.mark.unit
class TestProcessOracleRac:
    def test_uses_dsn_kwarg_with_stripped_url(self):
        mock_oracledb = MagicMock()
        mock_oracledb.connect.return_value = MagicMock(autocommit=False)
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            cfg = _valid_sid_config(
                connection_type="ORACLE_RAC", rac_url="\n  (DESCRIPTION=...)  \n"
            )
            comp = _make_component(cfg)
            comp._process(None)
        call_kwargs = mock_oracledb.connect.call_args.kwargs
        assert call_kwargs["dsn"] == "(DESCRIPTION=...)"

    def test_empty_rac_url_raises_configuration_error(self):
        comp = _make_component(
            _valid_sid_config(connection_type="ORACLE_RAC", rac_url="")
        )
        with pytest.raises(ConfigurationError) as exc:
            comp._process(None)
        assert "rac_url" in str(exc.value)


@pytest.mark.unit
class TestProcessUnsupportedTypes:
    def test_oci_raises_with_d_a3_message(self):
        comp = _make_component(_valid_sid_config(connection_type="ORACLE_OCI"))
        with pytest.raises(ConfigurationError) as exc:
            comp._process(None)
        msg = str(exc.value)
        assert "ORACLE_OCI" in msg
        assert "thick_mode" in msg
        assert "Instant Client" in msg
        # T-11-05: error text must NOT leak any wallet path or auth info
        assert "secret_hunter2" not in msg  # never leak credential

    def test_wallet_raises_with_d_a3_message(self):
        comp = _make_component(_valid_sid_config(connection_type="ORACLE_WALLET"))
        with pytest.raises(ConfigurationError) as exc:
            comp._process(None)
        msg = str(exc.value)
        assert "ORACLE_WALLET" in msg
        assert "thick_mode" in msg


@pytest.mark.unit
class TestAutoCommit:
    def test_auto_commit_true_sets_autocommit(self):
        mock_oracledb = MagicMock()
        mock_conn = MagicMock(autocommit=False)
        mock_oracledb.connect.return_value = mock_conn
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            comp = _make_component(_valid_sid_config(auto_commit=True))
            comp._process(None)
        assert mock_conn.autocommit is True

    def test_auto_commit_default_false_unchanged(self):
        mock_oracledb = MagicMock()
        mock_conn = MagicMock()
        mock_conn.autocommit = False  # initial state
        mock_oracledb.connect.return_value = mock_conn
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            comp = _make_component(_valid_sid_config())
            comp._process(None)
        assert mock_conn.autocommit is False  # NOT changed


@pytest.mark.unit
class TestGlobalMapMetadata:
    def test_writes_connection_type_dbschema_username(self):
        mock_oracledb = MagicMock()
        mock_oracledb.connect.return_value = MagicMock(autocommit=False)
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            gm = GlobalMap()
            comp = _make_component(_valid_sid_config(), global_map=gm)
            comp._process(None)
        assert gm.get("connectionType_tOracleConnection_1") == "ORACLE_SID"
        assert gm.get("dbschema_tOracleConnection_1") == "HR"
        assert gm.get("username_tOracleConnection_1") == "u"

    def test_never_writes_password_to_globalmap(self):
        mock_oracledb = MagicMock()
        mock_oracledb.connect.return_value = MagicMock(autocommit=False)
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            gm = GlobalMap()
            comp = _make_component(_valid_sid_config(), global_map=gm)
            comp._process(None)
        for key, value in gm.get_all().items():
            assert "password" not in key.lower()
            assert "secret_hunter2" not in str(value)

    def test_never_pushes_live_connection_to_globalmap(self):
        """D-A1: live oracledb.Connection MUST NOT enter globalMap."""
        mock_oracledb = MagicMock()
        mock_conn = MagicMock(autocommit=False)
        mock_oracledb.connect.return_value = mock_conn
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            gm = GlobalMap()
            comp = _make_component(_valid_sid_config(), global_map=gm)
            comp._process(None)
        data = gm.get_all()
        for value in data.values():
            # All globalMap values must be JSON-friendly primitives
            assert not callable(value), f"globalMap holds callable {value!r}"
            # Live Connection mock would equal mock_conn; assert never stored
            assert value is not mock_conn


@pytest.mark.unit
class TestPasswordNotLogged:
    """T-11-02 regression: PASSWORD never appears in any log record."""

    def test_full_process_does_not_log_password(self, caplog):
        mock_oracledb = MagicMock()
        mock_oracledb.connect.return_value = MagicMock(autocommit=False)
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            comp = _make_component(_valid_sid_config())
            with caplog.at_level(logging.DEBUG):
                comp._process(None)
        for record in caplog.records:
            assert "secret_hunter2" not in record.getMessage()

    def test_password_not_in_oci_error_text(self):
        """T-11-05 + T-11-02 cross-cut: OCI refusal must not leak credential."""
        comp = _make_component(
            _valid_sid_config(connection_type="ORACLE_OCI")
        )
        with pytest.raises(ConfigurationError) as exc:
            comp._process(None)
        assert "secret_hunter2" not in str(exc.value)


@pytest.mark.unit
class TestManagerWiring:
    def test_process_raises_when_oracle_manager_none(self):
        comp = _make_component(_valid_sid_config(), oracle_manager=None)
        comp.oracle_manager = None  # explicit
        with pytest.raises(ConfigurationError) as exc:
            comp._process(None)
        assert "OracleConnectionManager" in str(exc.value)


@pytest.mark.unit
class TestPortCoercion:
    def test_string_port_coerced_to_int(self):
        mock_oracledb = MagicMock()
        mock_oracledb.connect.return_value = MagicMock(autocommit=False)
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            comp = _make_component(_valid_sid_config(port="1521"))
            comp._process(None)
        call_kwargs = mock_oracledb.connect.call_args.kwargs
        assert call_kwargs["port"] == 1521
        assert isinstance(call_kwargs["port"], int)

    def test_missing_port_defaults_to_1521(self):
        mock_oracledb = MagicMock()
        mock_oracledb.connect.return_value = MagicMock(autocommit=False)
        with patch.dict(sys.modules, {"oracledb": mock_oracledb}):
            cfg = _valid_sid_config()
            del cfg["port"]
            comp = _make_component(cfg)
            comp._process(None)
        assert mock_oracledb.connect.call_args.kwargs["port"] == 1521
