"""Unit tests for OracleBulkExec engine component.

sqlldr is an external binary, so these tests mock ``subprocess.run`` and assert
the deterministic surface: generated control file, data file, sqlldr argv, log
parsing, stats, and exit-code handling. A real load lives in @pytest.mark.oracle
integration tests (mocks lie).
"""
import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError, FileOperationError
from src.v1.engine.global_map import GlobalMap

MODULE = "src.v1.engine.components.database.oracle_bulk_exec"


def _make_component(config, global_map=None, input_schema=None):
    from src.v1.engine.components.database.oracle_bulk_exec import OracleBulkExec

    gm = global_map if global_map is not None else GlobalMap()
    comp = OracleBulkExec(
        component_id="tOracleBulkExec_1",
        config=config,
        global_map=gm,
        context_manager=ContextManager(),
    )
    comp.config = dict(config)
    comp.input_schema = input_schema or [{"name": "id", "type": "int"},
                                         {"name": "name", "type": "string"}]
    comp.oracle_manager = MagicMock()
    return comp


def _base_config(**overrides):
    cfg = {
        "table": "EMP",
        "data_action": "APPEND",
        "connection_type": "ORACLE_SID",
        "host": "dbhost",
        "port": "1521",
        "dbname": "ORCL",
        "user": "scott",
        "password": "tiger",
        "fields_terminator": "COMMA",
    }
    cfg.update(overrides)
    return cfg


def _completed(returncode=0, stderr=""):
    cp = MagicMock()
    cp.returncode = returncode
    cp.stderr = stderr
    return cp


@pytest.mark.unit
class TestRegistration:
    def test_both_aliases_resolve(self):
        from src.v1.engine.components import database  # noqa: F401
        from src.v1.engine.component_registry import REGISTRY
        from src.v1.engine.components.database.oracle_bulk_exec import (
            OracleBulkExec,
        )

        assert REGISTRY.get("OracleBulkExec") is OracleBulkExec
        assert REGISTRY.get("tOracleBulkExec") is OracleBulkExec


@pytest.mark.unit
class TestValidateConfig:
    def test_missing_table_raises(self):
        cfg = _base_config()
        del cfg["table"]
        with pytest.raises(ConfigurationError) as exc:
            _make_component(cfg)._validate_config()
        assert "table" in str(exc.value)

    def test_invalid_data_action_raises(self):
        with pytest.raises(ConfigurationError) as exc:
            _make_component(_base_config(data_action="MERGE"))._validate_config()
        assert "MERGE" in str(exc.value)

    def test_valid_passes(self):
        _make_component(_base_config())._validate_config()


@pytest.mark.unit
class TestTableActionRefusal:
    def test_create_action_refused(self):
        comp = _make_component(_base_config(table_action="DROP_CREATE"))
        with pytest.raises(ConfigurationError) as exc:
            comp._process(pd.DataFrame({"id": [1]}))
        assert "table_action" in str(exc.value)

    def test_truncate_allowed(self):
        comp = _make_component(_base_config(table_action="TRUNCATE"))
        with patch(f"{MODULE}.subprocess.run", return_value=_completed()) as run:
            comp._process(pd.DataFrame({"id": [1], "name": ["a"]}))
        run.assert_called_once()


@pytest.mark.unit
class TestDelimiter:
    @pytest.mark.parametrize("term,expected", [
        ("COMMA", ","), ("SEMICOLON", ";"), ("TAB", "\t"),
        ("PIPE", "|"), ("SPACE", " "),
    ])
    def test_named_terminators(self, term, expected):
        comp = _make_component(_base_config(fields_terminator=term))
        assert comp._resolve_delimiter() == expected

    def test_other_uses_terminator_value(self):
        comp = _make_component(
            _base_config(fields_terminator="OTHER", terminator_value="~")
        )
        assert comp._resolve_delimiter() == "~"


@pytest.mark.unit
class TestControlFile:
    def test_generated_control_has_core_clauses(self):
        comp = _make_component(_base_config(data_action="REPLACE"))
        ctl = comp._generate_control_file("/tmp/data.dat")
        assert "LOAD DATA" in ctl
        assert "INFILE '/tmp/data.dat'" in ctl
        assert "REPLACE" in ctl
        assert "INTO TABLE EMP" in ctl
        assert "FIELDS TERMINATED BY ','" in ctl
        assert "  id" in ctl
        assert "  name" in ctl

    def test_enclosure_and_options(self):
        comp = _make_component(_base_config(
            use_fields_enclosure=True,
            preserve_blanks=True,
            trailing_nullcols=True,
        ))
        ctl = comp._generate_control_file("/tmp/d.dat")
        assert 'OPTIONALLY ENCLOSED BY \'"\'' in ctl
        assert "PRESERVE BLANKS" in ctl
        assert "TRAILING NULLCOLS" in ctl

    def test_date_pattern_and_uppercase(self):
        schema = [{"name": "hired", "type": "date", "date_pattern": "yyyy-MM-dd"}]
        comp = _make_component(
            _base_config(use_date_pattern=True,
                         convert_column_table_to_uppercase=True),
            input_schema=schema,
        )
        ctl = comp._generate_control_file("/tmp/d.dat")
        assert "HIRED" in ctl
        assert 'DATE "YYYY-MM-DD"' in ctl

    def test_existing_clt_file_used(self):
        comp = _make_component(_base_config(
            use_existing_clt_file=True, clt_file="/my/load.ctl"
        ))
        assert comp._resolve_control_file(None, "/d.dat", []) == "/my/load.ctl"

    def test_existing_clt_file_empty_raises(self):
        comp = _make_component(_base_config(
            use_existing_clt_file=True, clt_file=""
        ))
        with pytest.raises(ConfigurationError):
            comp._resolve_control_file(None, "/d.dat", [])


@pytest.mark.unit
class TestDsnAndUserid:
    def test_sid_easyconnect_dsn(self):
        comp = _make_component(_base_config())
        assert comp._build_dsn() == "//dbhost:1521/ORCL"

    def test_rac_uses_rac_url(self):
        comp = _make_component(_base_config(
            connection_type="ORACLE_RAC", rac_url="  (DESCRIPTION=...)  "
        ))
        assert comp._build_dsn() == "(DESCRIPTION=...)"

    def test_no_host_yields_empty_dsn(self):
        comp = _make_component(_base_config(host=""))
        assert comp._build_dsn() == ""
        # userid still embeds user/pass when no dsn.
        assert comp._build_userid() == "scott/tiger"

    def test_userid_embeds_password(self):
        comp = _make_component(_base_config())
        assert comp._build_userid() == "scott/tiger@//dbhost:1521/ORCL"


@pytest.mark.unit
class TestArgvAndEnv:
    def test_argv_structure(self):
        comp = _make_component(_base_config(options=["errors=50", "rows=1000"]))
        argv = comp._build_sqlldr_argv("/c.ctl", "/d.dat", "/l.log", "/b.bad")
        assert argv[0] == "sqlldr"
        assert argv[1] == "scott/tiger@//dbhost:1521/ORCL"
        assert "control=/c.ctl" in argv
        assert "data=/d.dat" in argv
        assert "log=/l.log" in argv
        assert "bad=/b.bad" in argv
        assert "errors=50" in argv and "rows=1000" in argv

    def test_nls_env_set_when_configured(self):
        comp = _make_component(_base_config(
            nls_language="AMERICAN", nls_territory="AMERICA", encoding="UTF8"
        ))
        env = comp._build_nls_env()
        assert env["NLS_LANG"] == "AMERICAN_AMERICA.UTF8"

    def test_nls_env_default_not_set(self):
        comp = _make_component(_base_config())  # defaults
        env = comp._build_nls_env()
        assert "NLS_LANG" not in env


@pytest.mark.unit
class TestLogParsing:
    def test_parse_loaded_and_rejected(self, tmp_path):
        log = tmp_path / "x.log"
        log.write_text(
            "  98 Rows successfully loaded.\n"
            "  2 Rows not loaded due to data errors.\n"
        )
        comp = _make_component(_base_config())
        loaded, rejected = comp._parse_log(str(log))
        assert loaded == 98
        assert rejected == 2

    def test_missing_log_returns_zeros(self):
        comp = _make_component(_base_config())
        assert comp._parse_log("/no/such.log") == (0, 0)


@pytest.mark.unit
class TestProcessEndToEnd:
    def test_full_run_publishes_stats(self, tmp_path):
        gm = GlobalMap()
        comp = _make_component(_base_config(), global_map=gm)
        df = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})

        def fake_run(argv, **kwargs):
            # Locate the log= arg and write a sqlldr-style summary into it.
            log_path = next(a.split("=", 1)[1] for a in argv if a.startswith("log="))
            with open(log_path, "w", encoding="utf-8") as fh:
                fh.write("3 Rows successfully loaded.\n0 Rows not loaded.\n")
            return _completed(returncode=0)

        with patch(f"{MODULE}.subprocess.run", side_effect=fake_run):
            result = comp._process(df)
        assert result == {"main": None, "reject": None}
        assert gm.get("tOracleBulkExec_1_NB_LINE") == 3
        assert gm.get("tOracleBulkExec_1_NB_LINE_INSERTED") == 3
        assert gm.get("tOracleBulkExec_1_NB_LINE_REJECTED") == 0

    def test_temp_files_cleaned_up(self):
        comp = _make_component(_base_config())
        df = pd.DataFrame({"id": [1], "name": ["a"]})
        captured = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = argv
            return _completed(returncode=0)

        with patch(f"{MODULE}.subprocess.run", side_effect=fake_run):
            comp._process(df)
        # All temp paths referenced in argv must be gone after cleanup.
        for arg in captured["argv"]:
            if "=" in arg and arg.startswith(("control=", "data=", "log=", "bad=")):
                assert not os.path.exists(arg.split("=", 1)[1])

    def test_fatal_exit_raises(self):
        comp = _make_component(_base_config())
        df = pd.DataFrame({"id": [1], "name": ["a"]})
        with patch(f"{MODULE}.subprocess.run",
                   return_value=_completed(returncode=2, stderr="SP2-fatal")):
            with pytest.raises(FileOperationError) as exc:
                comp._process(df)
        assert "exit 2" in str(exc.value)

    def test_warning_exit_does_not_raise(self):
        comp = _make_component(_base_config())
        df = pd.DataFrame({"id": [1], "name": ["a"]})
        with patch(f"{MODULE}.subprocess.run",
                   return_value=_completed(returncode=1)):
            comp._process(df)  # exit 1 = warnings only, tolerated

    def test_die_on_error_with_rejects_raises(self, tmp_path):
        comp = _make_component(_base_config(die_on_error=True))
        df = pd.DataFrame({"id": [1, 2], "name": ["a", "b"]})

        def fake_run(argv, **kwargs):
            log_path = next(a.split("=", 1)[1] for a in argv if a.startswith("log="))
            with open(log_path, "w", encoding="utf-8") as fh:
                fh.write("1 Rows successfully loaded.\n1 Rows not loaded.\n")
            return _completed(returncode=1)

        with patch(f"{MODULE}.subprocess.run", side_effect=fake_run):
            with pytest.raises(ConfigurationError) as exc:
                comp._process(df)
        assert "rejected" in str(exc.value)

    def test_data_file_write_failure_raises(self):
        comp = _make_component(_base_config())
        df = pd.DataFrame({"id": [1], "name": ["a"]})
        with patch.object(
            pd.DataFrame, "to_csv", side_effect=OSError("disk full")
        ):
            with pytest.raises(FileOperationError) as exc:
                comp._process(df)
        assert "data file" in str(exc.value)

    def test_control_file_write_failure_raises(self):
        comp = _make_component(_base_config())
        df = pd.DataFrame({"id": [1], "name": ["a"]})
        # Let the data file write succeed but the control file open() fail.
        real_open = open

        def flaky_open(path, *a, **k):
            if str(path).endswith(".ctl"):
                raise OSError("ctl write denied")
            return real_open(path, *a, **k)

        with patch(f"{MODULE}.open", side_effect=flaky_open, create=True):
            with pytest.raises(FileOperationError) as exc:
                comp._process(df)
        assert "control file" in str(exc.value)

    def test_temp_cleanup_failure_swallowed(self, caplog):
        comp = _make_component(_base_config())
        df = pd.DataFrame({"id": [1], "name": ["a"]})
        with patch(f"{MODULE}.subprocess.run", return_value=_completed()), \
                patch(f"{MODULE}.os.remove", side_effect=OSError("locked")):
            comp._process(df)  # must not raise
        assert any(
            "Could not remove temp file" in r.getMessage() for r in caplog.records
        )

    def test_no_input_no_data_raises(self):
        comp = _make_component(_base_config())
        with pytest.raises(ConfigurationError) as exc:
            comp._process(None)
        assert "nothing to load" in str(exc.value)

    def test_no_input_with_existing_data_file(self, tmp_path):
        data = tmp_path / "prepared.dat"
        data.write_text("1,a\n")
        comp = _make_component(
            _base_config(data=str(data), use_existing_clt_file=True,
                         clt_file=str(tmp_path / "load.ctl"))
        )
        (tmp_path / "load.ctl").write_text("LOAD DATA\n")
        with patch(f"{MODULE}.subprocess.run", return_value=_completed()) as run:
            comp._process(None)
        argv = run.call_args.args[0]
        assert f"data={data}" in argv
