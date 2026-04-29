"""Engine unit tests for FileCopy (tFileCopy)."""
import os

import pytest

from src.v1.engine.components.file.file_copy import FileCopy
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError, FileOperationError
from src.v1.engine.global_map import GlobalMap


def _make_component(config, global_map=None):
    gm = global_map if global_map is not None else GlobalMap()
    comp = FileCopy(
        component_id="tFileCopy_1",
        config=config,
        global_map=gm,
        context_manager=ContextManager(),
    )
    comp.config = dict(config)
    return comp


def _src_file(tmp_path, name="src.txt", content="hello"):
    f = tmp_path / name
    f.write_text(content, encoding="utf-8")
    return f


@pytest.mark.unit
class TestRegistration:
    def test_registered_under_aliases(self):
        from src.v1.engine.component_registry import REGISTRY
        assert REGISTRY.get("FileCopy") is FileCopy
        assert REGISTRY.get("tFileCopy") is FileCopy


@pytest.mark.unit
class TestValidateConfig:
    def test_missing_source_raises(self, tmp_path):
        comp = _make_component({"destination": str(tmp_path)})
        with pytest.raises(ConfigurationError, match="source"):
            comp._validate_config()

    def test_missing_destination_raises(self, tmp_path):
        comp = _make_component({"filename": str(tmp_path / "a.txt")})
        with pytest.raises(ConfigurationError, match="destination"):
            comp._validate_config()

    def test_legacy_source_alias_accepted(self, tmp_path):
        comp = _make_component(
            {"source": str(tmp_path / "a.txt"), "destination": str(tmp_path / "out")}
        )
        comp._validate_config()

    def test_replace_file_must_be_bool(self, tmp_path):
        comp = _make_component(
            {
                "filename": str(tmp_path / "a.txt"),
                "destination": str(tmp_path / "out"),
                "replace_file": "yes",
            }
        )
        with pytest.raises(ConfigurationError, match="replace_file"):
            comp._validate_config()


@pytest.mark.unit
class TestProcessFileCopy:
    def test_copies_file_to_directory(self, tmp_path):
        src = _src_file(tmp_path)
        dest = tmp_path / "out"
        comp = _make_component({"filename": str(src), "destination": str(dest)})
        result = comp.execute()
        assert (dest / "src.txt").read_text(encoding="utf-8") == "hello"
        assert result["main"]["status"] == "success"

    def test_legacy_source_key(self, tmp_path):
        src = _src_file(tmp_path)
        dest = tmp_path / "out"
        comp = _make_component({"source": str(src), "destination": str(dest)})
        comp.execute()
        assert (dest / "src.txt").exists()


@pytest.mark.unit
class TestRename:
    def test_destination_rename(self, tmp_path):
        src = _src_file(tmp_path)
        dest = tmp_path / "out"
        comp = _make_component(
            {
                "filename": str(src),
                "destination": str(dest),
                "rename": True,
                "destination_rename": "renamed.txt",
            }
        )
        comp.execute()
        assert (dest / "renamed.txt").exists()

    def test_legacy_new_name_alias(self, tmp_path):
        src = _src_file(tmp_path)
        dest = tmp_path / "out"
        comp = _make_component(
            {
                "filename": str(src),
                "destination": str(dest),
                "rename": True,
                "new_name": "newname.txt",
            }
        )
        comp.execute()
        assert (dest / "newname.txt").exists()


@pytest.mark.unit
class TestReplaceFile:
    def test_replace_file_true_overwrites(self, tmp_path):
        src = _src_file(tmp_path, content="new")
        dest = tmp_path / "out"
        dest.mkdir()
        existing = dest / "src.txt"
        existing.write_text("old", encoding="utf-8")
        comp = _make_component(
            {"filename": str(src), "destination": str(dest), "replace_file": True}
        )
        comp.execute()
        assert existing.read_text(encoding="utf-8") == "new"

    def test_replace_file_false_raises_when_exists(self, tmp_path):
        src = _src_file(tmp_path)
        dest = tmp_path / "out"
        dest.mkdir()
        (dest / "src.txt").write_text("old", encoding="utf-8")
        comp = _make_component(
            {"filename": str(src), "destination": str(dest), "replace_file": False}
        )
        with pytest.raises(Exception):
            comp.execute()


@pytest.mark.unit
class TestDirectoryCopy:
    def test_copies_directory_tree(self, tmp_path):
        src = tmp_path / "src_dir"
        src.mkdir()
        (src / "a.txt").write_text("a", encoding="utf-8")
        (src / "b.txt").write_text("b", encoding="utf-8")
        dest = tmp_path / "dest_dir"
        comp = _make_component(
            {
                "source_derectory": str(src),
                "destination": str(dest),
                "enable_copy_directory": True,
            }
        )
        comp.execute()
        assert (dest / "a.txt").exists()
        assert (dest / "b.txt").exists()


@pytest.mark.unit
class TestRemoveFile:
    def test_remove_file_acts_as_move(self, tmp_path):
        src = _src_file(tmp_path)
        dest = tmp_path / "out"
        comp = _make_component(
            {"filename": str(src), "destination": str(dest), "remove_file": True}
        )
        comp.execute()
        assert (dest / "src.txt").exists()
        assert not src.exists()


@pytest.mark.unit
class TestPreserveLastModified:
    def test_preserve_last_modified_time(self, tmp_path):
        src = _src_file(tmp_path)
        # Force a known mtime in the past.
        os.utime(src, (1_600_000_000, 1_600_000_000))
        dest = tmp_path / "out"
        comp = _make_component(
            {
                "filename": str(src),
                "destination": str(dest),
                "preserve_last_modified_time": True,
            }
        )
        comp.execute()
        copied_mtime = (dest / "src.txt").stat().st_mtime
        assert int(copied_mtime) == 1_600_000_000


@pytest.mark.unit
class TestErrorHandling:
    def test_missing_source_raises(self, tmp_path):
        dest = tmp_path / "out"
        # Validation passes (source path string non-empty); _process raises.
        comp = _make_component(
            {"filename": str(tmp_path / "missing.txt"), "destination": str(dest)}
        )
        with pytest.raises(Exception):
            comp.execute()

    def test_failon_false_returns_error_dict(self, tmp_path):
        dest = tmp_path / "out"
        comp = _make_component(
            {
                "filename": str(tmp_path / "missing.txt"),
                "destination": str(dest),
                "failon": False,
                "die_on_error": False,
            }
        )
        result = comp.execute()
        assert result["main"]["status"] == "error"


@pytest.mark.unit
class TestStatistics:
    def test_success_stats(self, tmp_path):
        src = _src_file(tmp_path)
        dest = tmp_path / "out"
        comp = _make_component({"filename": str(src), "destination": str(dest)})
        result = comp.execute()
        assert result["stats"]["NB_LINE_OK"] == 1
        assert result["stats"]["NB_LINE_REJECT"] == 0
