"""Engine unit tests for FileExistComponent (tFileExist)."""
import pytest

from src.v1.engine.components.file.file_exist import FileExistComponent
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


def _make_component(config, global_map=None):
    gm = global_map if global_map is not None else GlobalMap()
    comp = FileExistComponent(
        component_id="tFileExist_1",
        config=config,
        global_map=gm,
        context_manager=ContextManager(),
    )
    comp.config = dict(config)
    return comp


@pytest.mark.unit
class TestRegistration:
    def test_registered_under_all_aliases(self):
        from src.v1.engine.component_registry import REGISTRY
        assert REGISTRY.get("FileExistComponent") is FileExistComponent
        assert REGISTRY.get("FileExist") is FileExistComponent
        assert REGISTRY.get("tFileExist") is FileExistComponent


@pytest.mark.unit
class TestValidateConfig:
    def test_missing_file_path_raises(self):
        comp = _make_component({})
        with pytest.raises(ConfigurationError, match="file_name"):
            comp._validate_config()

    def test_empty_file_path_raises(self):
        comp = _make_component({"file_name": "   "})
        with pytest.raises(ConfigurationError):
            comp._validate_config()

    def test_accepts_file_name(self, tmp_path):
        comp = _make_component({"file_name": str(tmp_path / "a.txt")})
        comp._validate_config()

    def test_accepts_legacy_FILE_NAME(self, tmp_path):
        comp = _make_component({"FILE_NAME": str(tmp_path / "a.txt")})
        comp._validate_config()

    def test_check_directory_must_be_bool(self, tmp_path):
        comp = _make_component(
            {"file_name": str(tmp_path / "a.txt"), "check_directory": "yes"}
        )
        with pytest.raises(ConfigurationError, match="check_directory"):
            comp._validate_config()


@pytest.mark.unit
class TestProcessFileExistence:
    def test_existing_file_reports_true(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("hi", encoding="utf-8")
        comp = _make_component({"file_name": str(f)})
        result = comp.execute()
        assert result["main"]["file_exists"] is True

    def test_missing_file_reports_false(self, tmp_path):
        comp = _make_component({"file_name": str(tmp_path / "missing.txt")})
        result = comp.execute()
        assert result["main"]["file_exists"] is False


@pytest.mark.unit
class TestProcessDirectoryMode:
    def test_directory_mode_true_for_dir(self, tmp_path):
        comp = _make_component(
            {"file_name": str(tmp_path), "check_directory": True}
        )
        result = comp.execute()
        assert result["main"]["file_exists"] is True

    def test_directory_mode_false_for_file(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("x", encoding="utf-8")
        comp = _make_component({"file_name": str(f), "check_directory": True})
        result = comp.execute()
        assert result["main"]["file_exists"] is False


@pytest.mark.unit
class TestGlobalMapVariables:
    def test_sets_exists_and_filename(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("x", encoding="utf-8")
        gm = GlobalMap()
        comp = _make_component({"file_name": str(f)}, global_map=gm)
        comp.execute()
        assert gm.get("tFileExist_1_EXISTS") is True
        assert gm.get("tFileExist_1_FILENAME") == str(f)


@pytest.mark.unit
class TestStatistics:
    def test_stats_always_one_ok(self, tmp_path):
        comp = _make_component({"file_name": str(tmp_path / "missing.txt")})
        result = comp.execute()
        assert result["stats"]["NB_LINE"] == 1
        assert result["stats"]["NB_LINE_OK"] == 1
        assert result["stats"]["NB_LINE_REJECT"] == 0


@pytest.mark.unit
class TestLegacyKeyAliases:
    def test_file_path_alias(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("x", encoding="utf-8")
        comp = _make_component({"file_path": str(f)})
        result = comp.execute()
        assert result["main"]["file_exists"] is True

    def test_FILE_NAME_alias(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("x", encoding="utf-8")
        comp = _make_component({"FILE_NAME": str(f)})
        result = comp.execute()
        assert result["main"]["file_exists"] is True
