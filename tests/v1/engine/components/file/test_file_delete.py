"""Engine unit tests for FileDelete (tFileDelete)."""
import os

import pytest

from src.v1.engine.components.file.file_delete import FileDelete
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError, FileOperationError
from src.v1.engine.global_map import GlobalMap


def _make_component(config, global_map=None):
    gm = global_map if global_map is not None else GlobalMap()
    comp = FileDelete(
        component_id="tFileDelete_1",
        config=config,
        global_map=gm,
        context_manager=ContextManager(),
    )
    comp.config = dict(config)
    return comp


@pytest.mark.unit
class TestRegistration:
    def test_registered_under_aliases(self):
        from src.v1.engine.component_registry import REGISTRY
        assert REGISTRY.get("FileDelete") is FileDelete
        assert REGISTRY.get("tFileDelete") is FileDelete


@pytest.mark.unit
class TestValidateConfig:
    def test_missing_path_raises(self):
        comp = _make_component({})
        with pytest.raises(ConfigurationError, match="path"):
            comp._validate_config()

    def test_filename_alias_accepted(self, tmp_path):
        comp = _make_component({"filename": str(tmp_path / "a.txt")})
        comp._validate_config()

    def test_directory_alias_accepted_in_folder_mode(self, tmp_path):
        comp = _make_component(
            {"directory": str(tmp_path / "d"), "folder": True}
        )
        comp._validate_config()

    def test_failon_must_be_bool(self, tmp_path):
        comp = _make_component(
            {"path": str(tmp_path / "a.txt"), "failon": "yes"}
        )
        with pytest.raises(ConfigurationError, match="failon"):
            comp._validate_config()


@pytest.mark.unit
class TestProcessFileMode:
    def test_deletes_existing_file(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("x", encoding="utf-8")
        comp = _make_component({"filename": str(f)})
        result = comp.execute()
        assert not f.exists()
        assert result["main"]["status"] == "deleted"

    def test_missing_file_returns_not_exist(self, tmp_path):
        # failon defaults to True per Talend, so this raises.
        comp = _make_component({"filename": str(tmp_path / "missing.txt")})
        # NB: Missing file is not an OS error; deleted=False, no exception.
        result = comp.execute()
        assert result["main"]["status"] == "not exist"


@pytest.mark.unit
class TestProcessDirectoryMode:
    def test_deletes_directory_recursive(self, tmp_path):
        d = tmp_path / "d"
        d.mkdir()
        (d / "a.txt").write_text("x", encoding="utf-8")
        comp = _make_component({"directory": str(d), "folder": True})
        result = comp.execute()
        assert not d.exists()
        assert result["main"]["status"] == "deleted"

    def test_legacy_is_directory_alias(self, tmp_path):
        d = tmp_path / "d"
        d.mkdir()
        comp = _make_component(
            {"path": str(d), "is_directory": True, "recursive": True}
        )
        result = comp.execute()
        assert not d.exists()


@pytest.mark.unit
class TestProcessFolderFileMode:
    def test_auto_detects_file(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("x", encoding="utf-8")
        comp = _make_component({"path": str(f), "folder_file": True})
        result = comp.execute()
        assert not f.exists()
        assert result["main"]["status"] == "deleted"

    def test_auto_detects_directory(self, tmp_path):
        d = tmp_path / "d"
        d.mkdir()
        comp = _make_component({"path": str(d), "folder_file": True})
        result = comp.execute()
        assert not d.exists()


@pytest.mark.unit
class TestErrorPolicy:
    def test_failon_true_raises_on_os_error(self, tmp_path):
        # Try to delete a non-empty directory in non-recursive directory mode.
        d = tmp_path / "d"
        d.mkdir()
        (d / "a.txt").write_text("x", encoding="utf-8")
        comp = _make_component(
            {"directory": str(d), "folder": True, "recursive": False, "failon": True}
        )
        with pytest.raises(Exception):
            comp.execute()

    def test_failon_false_returns_error_dict(self, tmp_path):
        d = tmp_path / "d"
        d.mkdir()
        (d / "a.txt").write_text("x", encoding="utf-8")
        comp = _make_component(
            {
                "directory": str(d),
                "folder": True,
                "recursive": False,
                "failon": False,
                "die_on_error": False,
            }
        )
        result = comp.execute()
        assert result["main"]["status"] == "error"

    def test_legacy_fail_on_error_alias(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("x", encoding="utf-8")
        comp = _make_component({"filename": str(f), "fail_on_error": True})
        result = comp.execute()
        assert not f.exists()


@pytest.mark.unit
class TestGlobalMapVariables:
    def test_sets_delete_path_and_status(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("x", encoding="utf-8")
        gm = GlobalMap()
        comp = _make_component({"filename": str(f)}, global_map=gm)
        comp.execute()
        assert gm.get("tFileDelete_1_DELETE_PATH") == str(f)
        assert gm.get("tFileDelete_1_CURRENT_STATUS") == "deleted"

    def test_sets_status_not_exist(self, tmp_path):
        gm = GlobalMap()
        comp = _make_component(
            {"filename": str(tmp_path / "missing.txt")}, global_map=gm
        )
        comp.execute()
        assert gm.get("tFileDelete_1_CURRENT_STATUS") == "not exist"


@pytest.mark.unit
class TestStatistics:
    def test_success_stats(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("x", encoding="utf-8")
        comp = _make_component({"filename": str(f)})
        result = comp.execute()
        assert result["stats"]["NB_LINE_OK"] == 1
        assert result["stats"]["NB_LINE_REJECT"] == 0

    def test_missing_file_reject_stats(self, tmp_path):
        comp = _make_component({"filename": str(tmp_path / "missing.txt")})
        result = comp.execute()
        assert result["stats"]["NB_LINE_OK"] == 0
        assert result["stats"]["NB_LINE_REJECT"] == 1
