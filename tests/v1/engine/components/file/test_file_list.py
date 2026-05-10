"""Unit tests for FileList engine component (Phase 10-03).

Covers ITER-04, ITER-05, ITER-06, ITER-07, ITER-10, ERROR=true/false 0-match,
FORMAT_FILEPATH_TO_SLASH, CASE_SENSITIVE normalization.
"""
import os
import pathlib
import time

import pytest

from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.components.file.file_list import FileList, FileListItem
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ComponentExecutionError, ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_file_list(comp_id="tFileList_1", config=None, global_map=None):
    """Create a FileList instance with a fresh GlobalMap and ContextManager.

    Sets comp.config = dict(cfg) so that direct calls to _validate_config()
    and prepare_iterations() work without going through the execute() lifecycle.
    This matches the pattern established in test_file_exist.py.
    """
    cfg = config if config is not None else {}
    gm = global_map if global_map is not None else GlobalMap()
    ctx = ContextManager()
    comp = FileList(comp_id, cfg, gm, ctx)
    # Populate comp.config so direct method calls work (BaseComponent leaves it
    # empty until execute() is called, but unit tests often call hooks directly).
    comp.config = dict(cfg)
    return comp


def _prep_iter(comp):
    """Call prepare_iterations() returning a list (materialises the iterator)."""
    return list(comp.prepare_iterations(None))


# ------------------------------------------------------------------
# Registration (ITER-10)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRegistration:
    def test_registered_as_FileList(self):
        assert REGISTRY.get("FileList") is FileList

    def test_registered_as_tFileList(self):
        assert REGISTRY.get("tFileList") is FileList


# ------------------------------------------------------------------
# _validate_config structural checks (D-L4 / Phase 7.1 Rule 12)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestValidateConfig:
    def test_missing_directory_raises(self):
        comp = _make_file_list(config={})
        with pytest.raises(ConfigurationError, match="DIRECTORY"):
            comp._validate_config()

    def test_invalid_list_mode_raises(self):
        comp = _make_file_list(config={"DIRECTORY": "/tmp/testdir", "LIST_MODE": "INVALID"})
        with pytest.raises(ConfigurationError, match="LIST_MODE"):
            comp._validate_config()

    def test_invalid_order_by_raises(self):
        comp = _make_file_list(config={
            "DIRECTORY": "/tmp",
            "ORDER_BY": "ORDER_BY_BANANA",
        })
        with pytest.raises(ConfigurationError, match="ORDER_BY"):
            comp._validate_config()

    def test_invalid_order_action_raises(self):
        comp = _make_file_list(config={
            "DIRECTORY": "/tmp",
            "ORDER_ACTION": "ASC",  # invalid
        })
        with pytest.raises(ConfigurationError, match="ORDER_ACTION"):
            comp._validate_config()

    def test_invalid_case_sensitive_raises(self):
        comp = _make_file_list(config={
            "DIRECTORY": "/tmp",
            "CASE_SENSITIVE": "MAYBE",
        })
        with pytest.raises(ConfigurationError, match="CASE_SENSITIVE"):
            comp._validate_config()

    def test_files_not_a_list_raises(self):
        comp = _make_file_list(config={"DIRECTORY": "/tmp", "FILES": "*.txt"})
        with pytest.raises(ConfigurationError, match="FILES"):
            comp._validate_config()

    def test_valid_minimal_config_does_not_raise(self, tmp_path):
        comp = _make_file_list(config={"DIRECTORY": str(tmp_path)})
        comp._validate_config()  # should not raise

    def test_valid_full_config_does_not_raise(self, tmp_path):
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "FILES": [{"FILEMASK": "*.txt"}],
            "GLOBEXPRESSIONS": "true",
            "CASE_SENSITIVE": "YES",
            "INCLUDSUBDIR": "false",
            "LIST_MODE": "FILES",
            "ORDER_BY": "ORDER_BY_FILENAME",
            "ORDER_ACTION": "ORDER_ACTION_ASC",
            "ERROR": "false",
            "IFEXCLUDE": "false",
            "EXCLUDEFILEMASK": "",
            "FORMAT_FILEPATH_TO_SLASH": "false",
        })
        comp._validate_config()

    def test_does_not_check_directory_existence(self):
        """_validate_config MUST NOT raise ConfigurationError for missing directory.
        That is a content check belonging in prepare_iterations (D-L4)."""
        comp = _make_file_list(config={"DIRECTORY": "/nonexistent/path/xyz123"})
        # Should not raise -- directory existence is NOT a structural check
        comp._validate_config()

    def test_files_entry_not_a_dict_raises(self):
        comp = _make_file_list(config={
            "DIRECTORY": "/tmp",
            "FILES": ["*.txt"],  # list of strings, not dicts
        })
        with pytest.raises(ConfigurationError, match=r"FILES\[0\]"):
            comp._validate_config()


# ------------------------------------------------------------------
# Walk behaviour (ITER-04, ITER-06)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestPrepareIterationsWalk:
    def test_walks_files_non_recursive(self, tmp_path):
        """ITER-04: non-recursive walk yields files in the directory."""
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        (tmp_path / "c.txt").write_text("c")
        comp = _make_file_list(config={"DIRECTORY": str(tmp_path)})
        items = _prep_iter(comp)
        assert len(items) == 3
        assert all(isinstance(it, FileListItem) for it in items)

    def test_walks_files_recursive(self, tmp_path):
        """ITER-06: recursive walk with INCLUDSUBDIR=true yields nested files."""
        (tmp_path / "top.txt").write_text("top")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.txt").write_text("nested")

        comp_non_rec = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "INCLUDSUBDIR": "false",
        })
        comp_rec = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "INCLUDSUBDIR": "true",
        })
        non_rec_items = _prep_iter(comp_non_rec)
        rec_items = _prep_iter(comp_rec)
        # Non-recursive: only files at root level (not sub-directory itself)
        non_rec_files = [it for it in non_rec_items if it.name.endswith(".txt")]
        assert len(non_rec_files) == 1
        assert non_rec_files[0].name == "top.txt"
        # Recursive: should include nested.txt too
        rec_names = {it.name for it in rec_items if it.name.endswith(".txt")}
        assert "nested.txt" in rec_names
        assert "top.txt" in rec_names

    def test_list_mode_directories_only(self, tmp_path):
        """LIST_MODE=DIRECTORIES yields only subdirectories."""
        (tmp_path / "file.txt").write_text("x")
        (tmp_path / "subdir").mkdir()
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "LIST_MODE": "DIRECTORIES",
        })
        items = _prep_iter(comp)
        assert all(pathlib.Path(it.path).is_dir() for it in items)
        names = {it.name for it in items}
        assert "subdir" in names
        assert "file.txt" not in names

    def test_list_mode_both(self, tmp_path):
        """LIST_MODE=BOTH yields both files and directories."""
        (tmp_path / "file.txt").write_text("x")
        (tmp_path / "subdir").mkdir()
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "LIST_MODE": "BOTH",
        })
        items = _prep_iter(comp)
        names = {it.name for it in items}
        assert "file.txt" in names
        assert "subdir" in names

    def test_items_have_correct_shape(self, tmp_path):
        """FileListItem has name, ext, parent, index set correctly."""
        f = tmp_path / "report.java"
        f.write_text("code")
        comp = _make_file_list(config={"DIRECTORY": str(tmp_path)})
        items = _prep_iter(comp)
        assert len(items) == 1
        item = items[0]
        assert item.name == "report.java"
        assert item.ext == "java"   # no leading dot
        assert str(item.parent) == str(tmp_path.resolve())
        assert item.index == 1

    def test_missing_directory_with_error_false_returns_empty(self, tmp_path):
        """Missing directory + ERROR=false: no iterations, no exception."""
        nonexistent = tmp_path / "ghost_dir"
        comp = _make_file_list(config={
            "DIRECTORY": str(nonexistent),
            "ERROR": "false",
        })
        items = _prep_iter(comp)
        assert items == []
        assert comp.total_iterations == 0


# ------------------------------------------------------------------
# Glob matching (D-G4)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestGlobMatching:
    def test_glob_case_sensitive_no_match(self, tmp_path):
        """CASE_SENSITIVE=YES means 'Foo.txt' does NOT match '*.TXT'."""
        (tmp_path / "Foo.txt").write_text("x")
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "FILES": [{"FILEMASK": "*.TXT"}],
            "GLOBEXPRESSIONS": "true",
            "CASE_SENSITIVE": "YES",
            "ERROR": "false",
        })
        items = _prep_iter(comp)
        assert len(items) == 0

    def test_glob_case_insensitive_match(self, tmp_path):
        """CASE_SENSITIVE=NO means 'Foo.txt' DOES match '*.TXT'."""
        (tmp_path / "Foo.txt").write_text("x")
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "FILES": [{"FILEMASK": "*.TXT"}],
            "GLOBEXPRESSIONS": "true",
            "CASE_SENSITIVE": "NO",
        })
        items = _prep_iter(comp)
        assert len(items) == 1
        assert items[0].name == "Foo.txt"

    def test_multiple_masks_or(self, tmp_path):
        """Multiple FILEMASK entries are OR-wise: matches *.txt OR *.csv."""
        (tmp_path / "data.txt").write_text("t")
        (tmp_path / "data.csv").write_text("c")
        (tmp_path / "data.xml").write_text("x")
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "FILES": [{"FILEMASK": "*.txt"}, {"FILEMASK": "*.csv"}],
            "GLOBEXPRESSIONS": "true",
            "CASE_SENSITIVE": "YES",
        })
        items = _prep_iter(comp)
        names = {it.name for it in items}
        assert "data.txt" in names
        assert "data.csv" in names
        assert "data.xml" not in names

    def test_glob_no_masks_returns_all_files(self, tmp_path):
        """Empty FILES list returns all files (no inclusion filter)."""
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.csv").write_text("b")
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "FILES": [],
            "GLOBEXPRESSIONS": "true",
        })
        items = _prep_iter(comp)
        assert len(items) == 2


# ------------------------------------------------------------------
# Regex matching (D-G5)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRegexMatching:
    def test_regex_fullmatch_required(self, tmp_path):
        """Regex mode uses fullmatch: 'report\\.\\w+' matches report.txt
        but NOT report.txt.bak (which is longer than the pattern)."""
        (tmp_path / "report.txt").write_text("x")
        (tmp_path / "report.txt.bak").write_text("x")
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "FILES": [{"FILEMASK": r"report\.\w+"}],
            "GLOBEXPRESSIONS": "false",
            "CASE_SENSITIVE": "YES",
        })
        items = _prep_iter(comp)
        names = {it.name for it in items}
        assert "report.txt" in names
        assert "report.txt.bak" not in names

    def test_regex_case_insensitive(self, tmp_path):
        """Regex CASE_SENSITIVE=NO applies re.IGNORECASE flag."""
        (tmp_path / "REPORT.txt").write_text("x")
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "FILES": [{"FILEMASK": r"report\.txt"}],
            "GLOBEXPRESSIONS": "false",
            "CASE_SENSITIVE": "NO",
        })
        items = _prep_iter(comp)
        assert len(items) == 1
        assert items[0].name == "REPORT.txt"

    def test_regex_case_sensitive_no_match(self, tmp_path):
        """Regex CASE_SENSITIVE=YES: 'REPORT.txt' does NOT match 'report\\.txt'."""
        (tmp_path / "REPORT.txt").write_text("x")
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "FILES": [{"FILEMASK": r"report\.txt"}],
            "GLOBEXPRESSIONS": "false",
            "CASE_SENSITIVE": "YES",
            "ERROR": "false",
        })
        items = _prep_iter(comp)
        assert len(items) == 0


# ------------------------------------------------------------------
# EXCLUDEFILEMASK (D-G7)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestExcludeFilemask:
    def test_exclude_in_same_mode_glob(self, tmp_path):
        """Glob inclusion *.txt + exclusion *.bak.txt removes only *.bak.txt files."""
        (tmp_path / "data.txt").write_text("d")
        (tmp_path / "data.bak.txt").write_text("b")
        (tmp_path / "other.csv").write_text("o")
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "FILES": [{"FILEMASK": "*.txt"}],
            "GLOBEXPRESSIONS": "true",
            "CASE_SENSITIVE": "YES",
            "IFEXCLUDE": "true",
            "EXCLUDEFILEMASK": "*.bak.txt",
        })
        items = _prep_iter(comp)
        names = {it.name for it in items}
        assert "data.txt" in names
        assert "data.bak.txt" not in names
        assert "other.csv" not in names

    def test_exclude_not_applied_when_ifexclude_false(self, tmp_path):
        """When IFEXCLUDE=false, EXCLUDEFILEMASK is ignored."""
        (tmp_path / "data.txt").write_text("d")
        (tmp_path / "data.bak.txt").write_text("b")
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "FILES": [{"FILEMASK": "*.txt"}],
            "GLOBEXPRESSIONS": "true",
            "CASE_SENSITIVE": "YES",
            "IFEXCLUDE": "false",
            "EXCLUDEFILEMASK": "*.bak.txt",
        })
        items = _prep_iter(comp)
        names = {it.name for it in items}
        assert "data.txt" in names
        assert "data.bak.txt" in names  # not excluded when IFEXCLUDE=false


# ------------------------------------------------------------------
# Sort variants (ITER-07)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestSortVariants:
    def _create_sort_fixtures(self, tmp_path):
        """Create 3 files with controlled sizes and mtimes."""
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        c = tmp_path / "c.txt"
        a.write_text("x")            # small (1 byte)
        b.write_text("xxxx")         # large (4 bytes)
        c.write_text("xx")           # mid (2 bytes)
        # Set explicit modification times: b older, c mid, a recent
        t_base = time.time() - 1000
        os.utime(str(b), (t_base, t_base))
        os.utime(str(c), (t_base + 200, t_base + 200))
        os.utime(str(a), (t_base + 400, t_base + 400))
        return a, b, c

    def test_order_by_filename_asc(self, tmp_path):
        a, b, c = self._create_sort_fixtures(tmp_path)
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "ORDER_BY": "ORDER_BY_FILENAME",
            "ORDER_ACTION": "ORDER_ACTION_ASC",
        })
        items = _prep_iter(comp)
        names = [it.name for it in items]
        assert names == ["a.txt", "b.txt", "c.txt"]

    def test_order_by_filename_desc(self, tmp_path):
        a, b, c = self._create_sort_fixtures(tmp_path)
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "ORDER_BY": "ORDER_BY_FILENAME",
            "ORDER_ACTION": "ORDER_ACTION_DESC",
        })
        items = _prep_iter(comp)
        names = [it.name for it in items]
        assert names == ["c.txt", "b.txt", "a.txt"]

    def test_order_by_filesize_asc(self, tmp_path):
        a, b, c = self._create_sort_fixtures(tmp_path)
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "ORDER_BY": "ORDER_BY_FILESIZE",
            "ORDER_ACTION": "ORDER_ACTION_ASC",
        })
        items = _prep_iter(comp)
        # a=1 byte (smallest), c=2 bytes (mid), b=4 bytes (largest)
        names = [it.name for it in items]
        assert names == ["a.txt", "c.txt", "b.txt"]

    def test_order_by_modifieddate_asc(self, tmp_path):
        a, b, c = self._create_sort_fixtures(tmp_path)
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "ORDER_BY": "ORDER_BY_MODIFIEDDATE",
            "ORDER_ACTION": "ORDER_ACTION_ASC",
        })
        items = _prep_iter(comp)
        # b older (t_base), c mid (t_base+200), a recent (t_base+400)
        names = [it.name for it in items]
        assert names == ["b.txt", "c.txt", "a.txt"]

    def test_order_by_nothing_returns_all(self, tmp_path):
        """ORDER_BY_NOTHING: all files returned; order is not asserted (parity)."""
        for name in ["a.txt", "b.txt", "c.txt"]:
            (tmp_path / name).write_text("x")
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "ORDER_BY": "ORDER_BY_NOTHING",
            "ORDER_ACTION": "ORDER_ACTION_ASC",
        })
        items = _prep_iter(comp)
        assert len(items) == 3  # all present; order not asserted

    def test_order_by_modifieddate_desc(self, tmp_path):
        a, b, c = self._create_sort_fixtures(tmp_path)
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "ORDER_BY": "ORDER_BY_MODIFIEDDATE",
            "ORDER_ACTION": "ORDER_ACTION_DESC",
        })
        items = _prep_iter(comp)
        # DESC reversal: a most recent first, then c, then b
        names = [it.name for it in items]
        assert names == ["a.txt", "c.txt", "b.txt"]


# ------------------------------------------------------------------
# ERROR=true / false with 0 matches (D-G8 / D-E4)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestErrorBehavior:
    def test_error_true_zero_matches_raises(self, tmp_path):
        """Empty directory + ERROR=true -> ComponentExecutionError with parity message."""
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "ERROR": "true",
        })
        with pytest.raises(ComponentExecutionError, match="No file found in directory"):
            _prep_iter(comp)

    def test_error_false_zero_matches_warns(self, tmp_path, caplog):
        """Empty directory + ERROR=false -> no exception; total_iterations=0; WARNING logged."""
        import logging
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "ERROR": "false",
        })
        with caplog.at_level(logging.WARNING):
            items = _prep_iter(comp)
        assert items == []
        assert comp.total_iterations == 0
        # Check WARNING was logged
        warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("no files matched" in msg.lower() or "error=false" in msg.lower()
                   for msg in warning_messages)

    def test_error_true_directory_missing_raises(self, tmp_path):
        """Nonexistent directory + ERROR=true -> ComponentExecutionError."""
        nonexistent = tmp_path / "ghost_dir"
        comp = _make_file_list(config={
            "DIRECTORY": str(nonexistent),
            "ERROR": "true",
        })
        with pytest.raises(ComponentExecutionError, match="No file found in directory"):
            _prep_iter(comp)

    def test_error_true_with_matches_does_not_raise(self, tmp_path):
        """ERROR=true with actual matches: no exception."""
        (tmp_path / "file.txt").write_text("x")
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "ERROR": "true",
        })
        items = _prep_iter(comp)
        assert len(items) == 1

    def test_error_false_zero_stats_set(self, tmp_path):
        """ERROR=false with 0 matches sets NB_FILE=0 in stats."""
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "ERROR": "false",
        })
        _prep_iter(comp)
        assert comp.stats.get("NB_FILE", 0) == 0


# ------------------------------------------------------------------
# FORMAT_FILEPATH_TO_SLASH (D-G10)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestFormatFilepathToSlash:
    def test_replaces_backslashes(self, tmp_path, monkeypatch):
        """FORMAT_FILEPATH_TO_SLASH=true replaces backslashes with forward slashes
        in CURRENT_FILEPATH globalMap variable."""
        (tmp_path / "file.txt").write_text("x")
        gm = GlobalMap()
        comp = _make_file_list(
            config={
                "DIRECTORY": str(tmp_path),
                "FORMAT_FILEPATH_TO_SLASH": "true",
            },
            global_map=gm,
        )
        items = _prep_iter(comp)
        assert len(items) == 1
        # Set globalMap for the single item
        comp.set_iteration_globalmap(items[0])
        path_val = gm.get("tFileList_1_CURRENT_FILEPATH")
        assert "\\" not in path_val, f"Expected no backslashes, got: {path_val}"

    def test_unchanged_on_posix_paths(self, tmp_path):
        """On POSIX, FORMAT_FILEPATH_TO_SLASH=true produces the same result as =false."""
        (tmp_path / "file.txt").write_text("x")
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "FORMAT_FILEPATH_TO_SLASH": "false",
        })
        items_off = _prep_iter(comp)
        comp2 = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "FORMAT_FILEPATH_TO_SLASH": "true",
        })
        items_on = _prep_iter(comp2)
        # On POSIX both should produce identical paths
        assert str(items_off[0].path) == str(items_on[0].path)

    def test_apply_format_filepath_to_slash_static_with_backslash(self):
        """Static helper: a path string with backslashes is normalised."""
        p = pathlib.Path("C:\\Users\\foo\\bar.txt")
        result = FileList._apply_format_filepath_to_slash(p, enabled=True)
        assert "\\" not in str(result)
        assert "/" in str(result)

    def test_apply_format_filepath_to_slash_disabled(self):
        """Static helper: when disabled, path returned unchanged."""
        p = pathlib.Path("some/path/file.txt")
        result = FileList._apply_format_filepath_to_slash(p, enabled=False)
        assert result == p


# ------------------------------------------------------------------
# GlobalMap RETURN variables (ITER-05)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestGlobalMapVariables:
    def test_globalmap_return_vars(self, tmp_path):
        """ITER-05: all 5 RETURN vars set in globalMap per iteration."""
        f = tmp_path / "report.java"
        f.write_text("code")
        gm = GlobalMap()
        comp = _make_file_list(
            config={"DIRECTORY": str(tmp_path)},
            global_map=gm,
        )
        items = _prep_iter(comp)
        assert len(items) == 1
        comp.set_iteration_globalmap(items[0])

        assert gm.get("tFileList_1_CURRENT_FILE") == "report.java"
        assert gm.get("tFileList_1_CURRENT_FILEPATH") is not None
        assert gm.get("tFileList_1_CURRENT_FILEDIRECTORY") is not None
        assert gm.get("tFileList_1_CURRENT_FILEEXTENSION") == "java"
        assert gm.get("tFileList_1_NB_FILE") == 1

    def test_current_fileextension_no_leading_dot(self, tmp_path):
        """ITER-05: extension is 'java' not '.java'."""
        f = tmp_path / "report.java"
        f.write_text("code")
        gm = GlobalMap()
        comp = _make_file_list(
            config={"DIRECTORY": str(tmp_path)},
            global_map=gm,
        )
        items = _prep_iter(comp)
        comp.set_iteration_globalmap(items[0])
        ext = gm.get("tFileList_1_CURRENT_FILEEXTENSION")
        assert not ext.startswith("."), f"Extension should not start with dot, got: {ext!r}"
        assert ext == "java"

    def test_nb_file_increments_per_item(self, tmp_path):
        """_NB_FILE is 1-based and increments."""
        for name in ["a.txt", "b.txt", "c.txt"]:
            (tmp_path / name).write_text("x")
        gm = GlobalMap()
        comp = _make_file_list(
            config={
                "DIRECTORY": str(tmp_path),
                "ORDER_BY": "ORDER_BY_FILENAME",
                "ORDER_ACTION": "ORDER_ACTION_ASC",
            },
            global_map=gm,
        )
        items = _prep_iter(comp)
        assert len(items) == 3
        for i, item in enumerate(items, start=1):
            assert item.index == i

    def test_set_iteration_globalmap_with_no_global_map(self, tmp_path):
        """set_iteration_globalmap is a no-op when global_map is None."""
        (tmp_path / "file.txt").write_text("x")
        comp = _make_file_list(config={"DIRECTORY": str(tmp_path)}, global_map=None)
        comp.global_map = None
        items = _prep_iter(comp)
        # Should not raise
        comp.set_iteration_globalmap(items[0])

    def test_current_filepath_is_absolute(self, tmp_path):
        """CURRENT_FILEPATH should be an absolute path."""
        (tmp_path / "file.txt").write_text("x")
        gm = GlobalMap()
        comp = _make_file_list(
            config={"DIRECTORY": str(tmp_path)},
            global_map=gm,
        )
        items = _prep_iter(comp)
        comp.set_iteration_globalmap(items[0])
        filepath = gm.get("tFileList_1_CURRENT_FILEPATH")
        assert pathlib.Path(filepath).is_absolute()

    def test_current_filedirectory_equals_parent(self, tmp_path):
        """CURRENT_FILEDIRECTORY equals the parent directory of the file."""
        (tmp_path / "file.txt").write_text("x")
        gm = GlobalMap()
        comp = _make_file_list(
            config={"DIRECTORY": str(tmp_path)},
            global_map=gm,
        )
        items = _prep_iter(comp)
        comp.set_iteration_globalmap(items[0])
        dirval = gm.get("tFileList_1_CURRENT_FILEDIRECTORY")
        assert pathlib.Path(dirval) == tmp_path.resolve()


# ------------------------------------------------------------------
# CASE_SENSITIVE normalization (D-G9)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestCaseSensitiveNormalization:
    def test_yes_no(self):
        assert FileList._normalize_case_sensitive("cid", "YES") is True
        assert FileList._normalize_case_sensitive("cid", "NO") is False

    def test_yes_no_lowercase(self):
        assert FileList._normalize_case_sensitive("cid", "yes") is True
        assert FileList._normalize_case_sensitive("cid", "no") is False

    def test_true_false_strings(self):
        assert FileList._normalize_case_sensitive("cid", "true") is True
        assert FileList._normalize_case_sensitive("cid", "false") is False

    def test_true_false_titlecase(self):
        assert FileList._normalize_case_sensitive("cid", "True") is True
        assert FileList._normalize_case_sensitive("cid", "False") is False

    def test_python_booleans(self):
        assert FileList._normalize_case_sensitive("cid", True) is True
        assert FileList._normalize_case_sensitive("cid", False) is False

    def test_invalid_raises(self):
        with pytest.raises(ConfigurationError, match="CASE_SENSITIVE"):
            FileList._normalize_case_sensitive("cid", "MAYBE")

    def test_integer_one_not_true(self):
        """The integer 1 is NOT accepted as True (prevents bool/int collision)."""
        with pytest.raises(ConfigurationError, match="CASE_SENSITIVE"):
            FileList._normalize_case_sensitive("cid", 1)

    def test_integer_zero_not_false(self):
        """The integer 0 is NOT accepted as False (prevents bool/int collision)."""
        with pytest.raises(ConfigurationError, match="CASE_SENSITIVE"):
            FileList._normalize_case_sensitive("cid", 0)


# ------------------------------------------------------------------
# Statistics (finalize + total_iterations)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestStatistics:
    def test_nb_line_equals_matched_count(self, tmp_path):
        """finalize() sets NB_LINE = number of matched files."""
        for name in ["a.txt", "b.txt", "c.txt"]:
            (tmp_path / name).write_text("x")
        comp = _make_file_list(config={"DIRECTORY": str(tmp_path)})
        _prep_iter(comp)
        comp.finalize()
        assert comp.stats["NB_LINE"] == 3

    def test_nb_file_alias_set(self, tmp_path):
        """finalize() sets NB_FILE (Talend alias) to matched count."""
        for name in ["a.txt", "b.txt"]:
            (tmp_path / name).write_text("x")
        comp = _make_file_list(config={"DIRECTORY": str(tmp_path)})
        _prep_iter(comp)
        comp.finalize()
        assert comp.stats["NB_FILE"] == 2

    def test_nb_line_reject_always_zero(self, tmp_path):
        """NB_LINE_REJECT is always 0 for tFileList (no REJECT flow)."""
        (tmp_path / "file.txt").write_text("x")
        comp = _make_file_list(config={"DIRECTORY": str(tmp_path)})
        _prep_iter(comp)
        comp.finalize()
        assert comp.stats["NB_LINE_REJECT"] == 0

    def test_total_iterations_set_correctly(self, tmp_path):
        """total_iterations = count of matched files."""
        for name in ["a.txt", "b.txt", "c.txt", "d.txt"]:
            (tmp_path / name).write_text("x")
        comp = _make_file_list(config={"DIRECTORY": str(tmp_path)})
        _prep_iter(comp)
        assert comp.total_iterations == 4


# ------------------------------------------------------------------
# Iterate re-execution (Rule 11 -- mandatory for all components)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestIterateReexecution:
    def test_second_prepare_after_reset(self, tmp_path):
        """After reset(), prepare_iterations() produces same items."""
        for name in ["a.txt", "b.txt"]:
            (tmp_path / name).write_text("x")
        comp = _make_file_list(config={"DIRECTORY": str(tmp_path)})
        items1 = _prep_iter(comp)
        comp.reset()
        items2 = _prep_iter(comp)
        assert len(items1) == len(items2) == 2

    def test_config_not_mutated_across_executions(self, tmp_path):
        """_original_config remains unchanged after prepare_iterations."""
        (tmp_path / "a.txt").write_text("x")
        comp = _make_file_list(config={"DIRECTORY": str(tmp_path)})
        snapshot = dict(comp._original_config)
        _prep_iter(comp)
        assert comp._original_config == snapshot


# ------------------------------------------------------------------
# is_iterate_component flag
# ------------------------------------------------------------------

@pytest.mark.unit
class TestIterateComponentFlag:
    def test_is_iterate_component_true(self):
        """FileList must set is_iterate_component=True for Executor branching."""
        comp = _make_file_list(config={"DIRECTORY": "/tmp"})
        assert comp.is_iterate_component is True


# ------------------------------------------------------------------
# Race condition: file deleted between walk and sort (CR-06 / 10-11)
# ------------------------------------------------------------------

@pytest.mark.unit
class TestSortPathsRaceCondition:
    """CR-06 gap closure: _sort_paths must not crash when a file is deleted mid-sort.

    The p.exists()+p.stat() pattern is racy: a file can be deleted between the
    exists check and the stat call. The fix wraps stat in try/except OSError and
    returns a sort-stable default (0 for size, 0.0 for mtime).
    """

    def test_filesize_sort_survives_deleted_file(self, tmp_path, caplog):
        """FILESIZE sort completes without exception when a file is removed mid-sort."""
        import logging

        # Create 3 real files
        f1 = tmp_path / "alpha.txt"
        f2 = tmp_path / "beta.txt"
        f3 = tmp_path / "gamma.txt"
        f1.write_text("aaaa")    # 4 bytes
        f2.write_text("bb")      # 2 bytes
        f3.write_text("ccccc")   # 5 bytes

        paths = [f1, f2, f3]

        # Simulate race: delete f2 BEFORE sort runs
        f2.unlink()
        assert not f2.exists(), "f2 must be deleted before the sort"

        # Sort must complete without raising FileNotFoundError
        with caplog.at_level(logging.WARNING):
            result = FileList._sort_paths(paths, "ORDER_BY_FILESIZE", "ORDER_ACTION_ASC")

        # No exception was raised -- result is a list
        assert isinstance(result, list)
        # Real files f1 (4 bytes) and f3 (5 bytes) are still in the list
        assert f1 in result
        assert f3 in result

        # WARNING logged for the deleted file
        assert any(
            "beta.txt" in record.message or str(f2) in record.message
            for record in caplog.records
            if record.levelno == logging.WARNING
        ), f"Expected WARNING about deleted file, got: {[r.message for r in caplog.records]}"

    def test_modifieddate_sort_survives_deleted_file(self, tmp_path, caplog):
        """MODIFIEDDATE sort completes without exception when a file is removed mid-sort."""
        import logging

        f1 = tmp_path / "x.csv"
        f2 = tmp_path / "y.csv"
        f1.write_text("data")
        f2.write_text("more")

        paths = [f1, f2]

        # Delete f1 before sort
        f1.unlink()

        with caplog.at_level(logging.WARNING):
            result = FileList._sort_paths(paths, "ORDER_BY_MODIFIEDDATE", "ORDER_ACTION_ASC")

        assert isinstance(result, list)
        assert f2 in result

        # WARNING logged for deleted f1
        assert any(
            "x.csv" in record.message or str(f1) in record.message
            for record in caplog.records
            if record.levelno == logging.WARNING
        ), f"Expected WARNING about deleted file, got: {[r.message for r in caplog.records]}"


# ------------------------------------------------------------------
# Plan 14-08 coverage lift: missed-line clusters
#   143 (_cfg lowercase fallback), 245/247/249 (ORDER_BY RADIO branches),
#   258 (ORDER_ACTION_DESC RADIO branch), 391 (get_iter_key_info),
#   496-500 (_match_path static helper), 625 / 628 (_truthy int + fallthrough).
# ------------------------------------------------------------------


@pytest.mark.unit
class TestCoverageLift1408:
    """Targeted tests added in Plan 14-08 to lift file_list.py to >= 95%."""

    def test_cfg_lowercase_fallback(self):
        """_cfg returns lowercase value when uppercase key absent (line 143)."""
        comp = _make_file_list(config={"directory": "/tmp/lower_only"})
        # uppercase 'DIRECTORY' is absent, lowercase 'directory' provided.
        assert comp._cfg("DIRECTORY", "directory", "default") == "/tmp/lower_only"
        # When neither key is present, default is returned.
        assert comp._cfg("FOO", "foo", "fallback") == "fallback"

    def test_order_by_filename_radio_flag(self, tmp_path):
        """ORDER_BY_FILENAME RADIO flag derives order_by (line 245)."""
        f1 = tmp_path / "b.txt"
        f2 = tmp_path / "a.txt"
        f1.write_text("1")
        f2.write_text("2")
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "FILES": [{"FILEMASK": "*.txt"}],
            "GLOBEXPRESSIONS": "true",
            "ORDER_BY_FILENAME": True,
        })
        items = _prep_iter(comp)
        names = [it.name for it in items]
        assert names == ["a.txt", "b.txt"]

    def test_order_by_filesize_radio_flag(self, tmp_path):
        """ORDER_BY_FILESIZE RADIO flag derives order_by (line 247)."""
        big = tmp_path / "big.txt"
        small = tmp_path / "small.txt"
        big.write_text("xxxxxxxxxx")
        small.write_text("y")
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "FILES": [{"FILEMASK": "*.txt"}],
            "GLOBEXPRESSIONS": "true",
            "ORDER_BY_FILESIZE": True,
        })
        items = _prep_iter(comp)
        sizes = [p.path.stat().st_size for p in items]
        assert sizes == sorted(sizes)

    def test_order_by_modifieddate_radio_flag(self, tmp_path):
        """ORDER_BY_MODIFIEDDATE RADIO flag derives order_by (line 249)."""
        old = tmp_path / "old.txt"
        new = tmp_path / "new.txt"
        old.write_text("1")
        new.write_text("2")
        # set old's mtime explicitly to be older than new's
        os.utime(old, (time.time() - 100, time.time() - 100))
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "FILES": [{"FILEMASK": "*.txt"}],
            "GLOBEXPRESSIONS": "true",
            "ORDER_BY_MODIFIEDDATE": True,
        })
        items = _prep_iter(comp)
        names = [it.name for it in items]
        # ascending by mtime: old before new
        assert names == ["old.txt", "new.txt"]

    def test_order_action_desc_radio_flag(self, tmp_path):
        """ORDER_ACTION_DESC RADIO flag derives DESC direction (line 258)."""
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("1")
        f2.write_text("2")
        comp = _make_file_list(config={
            "DIRECTORY": str(tmp_path),
            "FILES": [{"FILEMASK": "*.txt"}],
            "GLOBEXPRESSIONS": "true",
            "ORDER_BY": "ORDER_BY_FILENAME",
            "ORDER_ACTION_DESC": True,
        })
        items = _prep_iter(comp)
        names = [it.name for it in items]
        assert names == ["b.txt", "a.txt"]

    def test_get_iter_key_info_returns_file_path(self, tmp_path):
        """get_iter_key_info returns 'file=<path>' (line 391)."""
        f = tmp_path / "report.txt"
        f.write_text("data")
        item = FileListItem(
            path=f.resolve(), name=f.name, parent=f.parent.resolve(), ext="txt", index=1
        )
        comp = _make_file_list()
        info = comp.get_iter_key_info(item, 1)
        assert info == f"file={item.path}"

    def test_match_path_helper_or_wise(self):
        """_match_path returns True when any mask matches (lines 496-500)."""
        # First mask matches
        assert FileList._match_path(
            "report.txt", ["*.txt", "*.log"], use_glob=True, case_sensitive=True
        ) is True
        # Second mask matches (first does not)
        assert FileList._match_path(
            "report.log", ["*.txt", "*.log"], use_glob=True, case_sensitive=True
        ) is True
        # No mask matches
        assert FileList._match_path(
            "report.csv", ["*.txt", "*.log"], use_glob=True, case_sensitive=True
        ) is False
        # Empty mask list
        assert FileList._match_path(
            "anything", [], use_glob=True, case_sensitive=True
        ) is False

    def test_truthy_accepts_int_and_unknown_falls_through(self):
        """_truthy: int(1) -> True (line 625); unknown types fall through to False (line 628)."""
        from src.v1.engine.components.file.file_list import _truthy

        # int branch (line 625)
        assert _truthy(1) is True
        assert _truthy(0) is False
        assert _truthy(2) is True

        # Unknown type fall-through (line 628): None / list / dict / object
        assert _truthy(None) is False
        assert _truthy([]) is False
        assert _truthy({"k": "v"}) is False
        assert _truthy(object()) is False
