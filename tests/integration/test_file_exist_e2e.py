"""Integration tests for tFileExist (Phase 10-08, verify-only).

tFileExist is already GREEN per Phase 9 audit. This test verifies
ITER-08 (file_name vs file_path keys) and ITER-09 ({id}_EXISTS, {id}_FILENAME
globalMap vars) in a real RUN_IF branching scenario (D-K3).

No engine code changes in Phase 10 for tFileExist.
"""
import pytest

from src.v1.engine.engine import ETLEngine


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _make_job_config(
    file_path_value: str,
    config_key: str = "file_name",
    downstream_marker_path: str = "/tmp/marker.out",
) -> dict:
    """Build a job config with tFileExist_1 -> RUN_IF -> tPython_marker subjob.

    Downstream tPython_marker writes a CSV marker file when the RUN_IF
    fires, giving a file-system-observable side effect without Java.

    The trigger condition references globalMap.get('tFileExist_1_EXISTS').
    TriggerManager._resolve_global_map_refs() replaces the call with the
    Python repr of the stored value (True or False) before eval, so this
    is a pure-Python condition -- no Java bridge required.
    """
    # pd.DataFrame(...).to_csv() is safe inside tPython: pandas uses
    # the CPython built-in open() internally, which is NOT restricted by
    # the exec __builtins__ whitelist (the whitelist only gates the user-code
    # namespace; pandas itself runs in the normal interpreter context).
    marker_code = (
        f"pd.DataFrame([{{'fired': True}}]).to_csv(r'{downstream_marker_path}', index=False)"
    )

    return {
        "job_name": "test_file_exist_e2e",
        "components": [
            {
                "id": "tFileExist_1",
                "type": "tFileExist",
                "config": {config_key: file_path_value},
                "inputs": [],
                "outputs": [],
                "subjob_id": "subjob_1",
            },
            {
                "id": "tPython_marker",
                "type": "tPython",
                "config": {
                    "python_code": marker_code,
                    "die_on_error": False,
                },
                "inputs": [],
                "outputs": [],
                "subjob_id": "subjob_2",
            },
        ],
        "flows": [],
        "triggers": [
            {
                "type": "RunIf",
                "from": "tFileExist_1",
                "to": "tPython_marker",
                # TriggerManager._resolve_global_map_refs() replaces the
                # globalMap.get(...) call with the Python literal repr of the
                # value stored by FileExistComponent._process() before eval().
                "condition": "globalMap.get('tFileExist_1_EXISTS') == True",
            },
        ],
        "subjobs": {
            "subjob_1": {"components": ["tFileExist_1"]},
            "subjob_2": {"components": ["tPython_marker"]},
        },
        "context": {},
    }


# ---------------------------------------------------------------------------
# ITER-08: file_name vs file_path config keys both accepted
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestFileExistConfigKeyAliases:
    """ITER-08: file_name and file_path keys both accepted by tFileExist."""

    def test_file_name_key_accepted(self, tmp_path):
        """file_name (preferred key) is accepted and sets _EXISTS correctly."""
        target = tmp_path / "exists.txt"
        target.write_text("x", encoding="utf-8")
        config = _make_job_config(
            str(target),
            config_key="file_name",
            downstream_marker_path=str(tmp_path / "marker.out"),
        )
        engine = ETLEngine(config)
        engine.execute()
        assert engine.global_map.get("tFileExist_1_EXISTS") is True

    def test_file_path_key_accepted_legacy(self, tmp_path):
        """file_path (legacy alias) is accepted and sets _EXISTS correctly."""
        target = tmp_path / "exists.txt"
        target.write_text("x", encoding="utf-8")
        config = _make_job_config(
            str(target),
            config_key="file_path",
            downstream_marker_path=str(tmp_path / "marker.out"),
        )
        engine = ETLEngine(config)
        engine.execute()
        assert engine.global_map.get("tFileExist_1_EXISTS") is True


# ---------------------------------------------------------------------------
# ITER-09: {id}_EXISTS and {id}_FILENAME both set in globalMap
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestGlobalMapVariables:
    """ITER-09: tFileExist sets {id}_EXISTS (bool) and {id}_FILENAME (str)."""

    def test_exists_true_and_filename_set_for_present_file(self, tmp_path):
        """Both _EXISTS=True and _FILENAME=path are written for an existing file."""
        target = tmp_path / "x.txt"
        target.write_text("x", encoding="utf-8")
        config = _make_job_config(
            str(target),
            downstream_marker_path=str(tmp_path / "marker.out"),
        )
        engine = ETLEngine(config)
        engine.execute()
        gm = engine.global_map
        assert gm.get("tFileExist_1_EXISTS") is True
        assert gm.get("tFileExist_1_FILENAME") == str(target)

    def test_exists_false_and_filename_set_for_missing_file(self, tmp_path):
        """Both _EXISTS=False and _FILENAME=path are written for a missing file."""
        missing = tmp_path / "missing.txt"
        config = _make_job_config(
            str(missing),
            downstream_marker_path=str(tmp_path / "marker.out"),
        )
        engine = ETLEngine(config)
        engine.execute()
        gm = engine.global_map
        assert gm.get("tFileExist_1_EXISTS") is False
        assert gm.get("tFileExist_1_FILENAME") == str(missing)

    def test_filename_value_matches_checked_path(self, tmp_path):
        """_FILENAME equals the exact path passed in config, regardless of existence."""
        target = tmp_path / "somewhere.txt"
        config = _make_job_config(
            str(target),
            downstream_marker_path=str(tmp_path / "marker.out"),
        )
        engine = ETLEngine(config)
        engine.execute()
        assert engine.global_map.get("tFileExist_1_FILENAME") == str(target)


# ---------------------------------------------------------------------------
# D-K3: tFileExist + RUN_IF -> downstream subjob branching
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestRunIfBranching:
    """D-K3: RUN_IF fires (or skips) the downstream subjob based on file existence."""

    def test_run_if_branches_when_file_exists(self, tmp_path):
        """When file exists, RUN_IF condition evaluates True -> marker written."""
        target = tmp_path / "x.txt"
        target.write_text("x", encoding="utf-8")
        marker = tmp_path / "marker.out"
        config = _make_job_config(
            str(target),
            downstream_marker_path=str(marker),
        )
        ETLEngine(config).execute()
        assert marker.exists(), (
            "RUN_IF should have fired tPython_marker when file exists"
        )

    def test_run_if_skips_when_file_missing(self, tmp_path):
        """When file is missing, RUN_IF condition evaluates False -> marker NOT written."""
        missing = tmp_path / "missing.txt"
        marker = tmp_path / "marker.out"
        config = _make_job_config(
            str(missing),
            downstream_marker_path=str(marker),
        )
        ETLEngine(config).execute()
        assert not marker.exists(), (
            "RUN_IF should NOT fire tPython_marker when file is missing"
        )


# ---------------------------------------------------------------------------
# M-6 fallback: direct component instantiation (no engine, no RunIf)
# These tests verify ITER-08 / ITER-09 even if ETLEngine or TriggerManager
# regressions prevent the full-engine tests above from running.
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFileExistGlobalMapDirect:
    """Direct component instantiation -- ITER-08 / ITER-09 without engine overhead."""

    def test_globalmap_exists_true_for_present_file(self, tmp_path):
        """_EXISTS is True when file exists (direct _process invocation)."""
        from src.v1.engine.components.file.file_exist import FileExistComponent
        from src.v1.engine.global_map import GlobalMap
        from src.v1.engine.context_manager import ContextManager

        target = tmp_path / "x.txt"
        target.write_text("x", encoding="utf-8")
        gm = GlobalMap()
        ctx = ContextManager()
        comp = FileExistComponent("tFileExist_1", {"file_name": str(target)}, gm, ctx)
        comp.execute()
        assert gm.get("tFileExist_1_EXISTS") is True
        assert gm.get("tFileExist_1_FILENAME") == str(target)

    def test_globalmap_exists_false_for_missing_file(self, tmp_path):
        """_EXISTS is False when file is missing (direct _process invocation)."""
        from src.v1.engine.components.file.file_exist import FileExistComponent
        from src.v1.engine.global_map import GlobalMap
        from src.v1.engine.context_manager import ContextManager

        missing = tmp_path / "missing.txt"
        gm = GlobalMap()
        ctx = ContextManager()
        comp = FileExistComponent("tFileExist_1", {"file_name": str(missing)}, gm, ctx)
        comp.execute()
        assert gm.get("tFileExist_1_EXISTS") is False
        assert gm.get("tFileExist_1_FILENAME") == str(missing)

    def test_legacy_file_path_key_accepted_directly(self, tmp_path):
        """file_path legacy alias accepted at component level (ITER-08)."""
        from src.v1.engine.components.file.file_exist import FileExistComponent
        from src.v1.engine.global_map import GlobalMap
        from src.v1.engine.context_manager import ContextManager

        target = tmp_path / "y.txt"
        target.write_text("y", encoding="utf-8")
        gm = GlobalMap()
        ctx = ContextManager()
        comp = FileExistComponent("tFileExist_1", {"file_path": str(target)}, gm, ctx)
        comp.execute()
        assert gm.get("tFileExist_1_EXISTS") is True
