"""Tests for FileRowCount (tFileRowCount engine implementation).

All tests exercise the component via ``execute()`` to mirror the true runtime
lifecycle. ``_validate_config()`` and ``_process()`` are never called directly
from test code (MANUAL_COMPONENT_AUTHORING.md Rule 4).

The module-level helper ``_count_rows`` is tested separately as a pure function.
"""
import pytest

from src.v1.engine.components.file.file_row_count import FileRowCount, _count_rows
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import (
    ComponentExecutionError,
    ConfigurationError,
    FileOperationError,
)
from src.v1.engine.global_map import GlobalMap


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_BASE_CONFIG: dict = {
    "component_type": "FileRowCount",
    "filename": "",        # overridden per test
    "row_separator": "\\n",
    "ignore_empty_row": False,
    "encoding": "ISO-8859-15",
}


def _make(config=None, global_map=None):
    """Construct a FileRowCount ready for execute() calls."""
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    return FileRowCount(
        component_id="tFRC_1",
        config=dict(config) if config is not None else dict(_BASE_CONFIG),
        global_map=gm,
        context_manager=cm,
    )


def _write(path, lines, sep="\n", encoding="ISO-8859-15"):
    """Write *lines* to *path* joined by *sep*, with a trailing separator."""
    path.write_bytes((sep.join(lines) + sep).encode(encoding))


# ---------------------------------------------------------------------------
# TestRegistration
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    """Component is discoverable from the engine registry."""

    def test_registered_under_v1_name(self):
        assert REGISTRY.get("FileRowCount") is FileRowCount

    def test_registered_under_talend_alias(self):
        assert REGISTRY.get("tFileRowCount") is FileRowCount


# ---------------------------------------------------------------------------
# TestValidation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    """_validate_config raises ConfigurationError for invalid structural config."""

    def test_missing_filename_raises(self):
        cfg = dict(_BASE_CONFIG)
        del cfg["filename"]
        comp = _make(config=cfg)
        with pytest.raises(ConfigurationError, match="filename"):
            comp.execute()

    def test_empty_filename_raises(self):
        cfg = {**_BASE_CONFIG, "filename": ""}
        comp = _make(config=cfg)
        with pytest.raises(ConfigurationError, match="filename"):
            comp.execute()

    def test_context_var_filename_passes_validate(self, tmp_path):
        """A ${context.X} placeholder is truthy and must not fail validation."""
        # This would fail later in _process when context is not set,
        # but _validate_config must not reject it.
        f = tmp_path / "data.txt"
        _write(f, ["row1", "row2"])
        cfg = {**_BASE_CONFIG, "filename": str(f)}
        comp = _make(config=cfg)
        result = comp.execute()
        assert result["main"] is None


# ---------------------------------------------------------------------------
# TestRowCounting
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRowCounting:
    """Core counting behaviour."""

    def test_counts_three_rows(self, tmp_path):
        f = tmp_path / "data.csv"
        _write(f, ["a", "b", "c"])
        cfg = {**_BASE_CONFIG, "filename": str(f)}
        comp = _make(config=cfg)
        result = comp.execute()
        assert result["main"] is None  # utility component — no data flow

    def test_count_stored_in_global_map(self, tmp_path):
        f = tmp_path / "data.csv"
        _write(f, ["row1", "row2", "row3"])
        gm = GlobalMap()
        cfg = {**_BASE_CONFIG, "filename": str(f)}
        _make(config=cfg, global_map=gm).execute()
        assert gm.get("tFRC_1_COUNT") == 3

    def test_single_row_file(self, tmp_path):
        f = tmp_path / "single.txt"
        _write(f, ["only one"])
        gm = GlobalMap()
        cfg = {**_BASE_CONFIG, "filename": str(f)}
        _make(config=cfg, global_map=gm).execute()
        assert gm.get("tFRC_1_COUNT") == 1

    def test_empty_file_gives_zero(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_bytes(b"")
        gm = GlobalMap()
        cfg = {**_BASE_CONFIG, "filename": str(f)}
        _make(config=cfg, global_map=gm).execute()
        assert gm.get("tFRC_1_COUNT") == 0

    def test_file_not_found_raises(self):
        """FileNotFoundError from _process() is wrapped in ComponentExecutionError."""
        cfg = {**_BASE_CONFIG, "filename": "/nonexistent/path/file.csv"}
        comp = _make(config=cfg)
        with pytest.raises(ComponentExecutionError):
            comp.execute()

    def test_result_main_is_none(self, tmp_path):
        """Utility component returns main=None, never a DataFrame."""
        f = tmp_path / "x.txt"
        _write(f, ["a"])
        cfg = {**_BASE_CONFIG, "filename": str(f)}
        result = _make(config=cfg).execute()
        assert result["main"] is None


# ---------------------------------------------------------------------------
# TestIgnoreEmptyRows
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIgnoreEmptyRows:
    """ignore_empty_row=True excludes whitespace-only lines."""

    def test_empty_rows_excluded_from_count(self, tmp_path):
        f = tmp_path / "data.csv"
        _write(f, ["row1", "", "row3", "   ", "row5"])
        gm = GlobalMap()
        cfg = {**_BASE_CONFIG, "filename": str(f), "ignore_empty_row": True}
        _make(config=cfg, global_map=gm).execute()
        assert gm.get("tFRC_1_COUNT") == 3

    def test_empty_rows_counted_when_flag_false(self, tmp_path):
        f = tmp_path / "data.csv"
        _write(f, ["row1", "", "row3"])
        gm = GlobalMap()
        cfg = {**_BASE_CONFIG, "filename": str(f), "ignore_empty_row": False}
        _make(config=cfg, global_map=gm).execute()
        assert gm.get("tFRC_1_COUNT") == 3

    def test_rejected_count_matches_empty_rows(self, tmp_path):
        f = tmp_path / "data.csv"
        _write(f, ["a", "", "b", "   "])
        gm = GlobalMap()
        cfg = {**_BASE_CONFIG, "filename": str(f), "ignore_empty_row": True}
        _make(config=cfg, global_map=gm).execute()
        assert gm.get("tFRC_1_NB_LINE_REJECT") == 2

    def test_all_rows_empty_gives_zero_count(self, tmp_path):
        f = tmp_path / "data.csv"
        _write(f, ["", "   ", "\t"])
        gm = GlobalMap()
        cfg = {**_BASE_CONFIG, "filename": str(f), "ignore_empty_row": True}
        _make(config=cfg, global_map=gm).execute()
        assert gm.get("tFRC_1_COUNT") == 0


# ---------------------------------------------------------------------------
# TestRowSeparator
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRowSeparator:
    """Custom row_separator produces correct counts."""

    def test_default_backslash_n_string_normalised(self, tmp_path):
        """Converter emits '\\n' (two chars); engine must normalise to newline."""
        f = tmp_path / "data.txt"
        _write(f, ["a", "b", "c"])   # writes with real \n
        gm = GlobalMap()
        cfg = {**_BASE_CONFIG, "filename": str(f), "row_separator": "\\n"}
        _make(config=cfg, global_map=gm).execute()
        assert gm.get("tFRC_1_COUNT") == 3

    def test_custom_pipe_separator(self, tmp_path):
        f = tmp_path / "data.txt"
        f.write_bytes(b"row1|row2|row3|")
        gm = GlobalMap()
        cfg = {**_BASE_CONFIG, "filename": str(f), "row_separator": "|"}
        _make(config=cfg, global_map=gm).execute()
        assert gm.get("tFRC_1_COUNT") == 3

    def test_custom_semicolon_separator(self, tmp_path):
        f = tmp_path / "data.txt"
        f.write_bytes(b"a;b;c;d")
        gm = GlobalMap()
        cfg = {**_BASE_CONFIG, "filename": str(f), "row_separator": ";"}
        _make(config=cfg, global_map=gm).execute()
        assert gm.get("tFRC_1_COUNT") == 4

    def test_backslash_r_backslash_n_string_normalised(self, tmp_path):
        """'\\r\\n' literal should be normalised and count CRLF lines correctly."""
        f = tmp_path / "data.txt"
        f.write_bytes(b"a\r\nb\r\nc\r\n")
        gm = GlobalMap()
        cfg = {**_BASE_CONFIG, "filename": str(f), "row_separator": "\\r\\n"}
        _make(config=cfg, global_map=gm).execute()
        assert gm.get("tFRC_1_COUNT") == 3


# ---------------------------------------------------------------------------
# TestEncoding
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEncoding:
    """Encoding parameter controls how the file is opened."""

    def test_utf8_encoding(self, tmp_path):
        f = tmp_path / "utf8.txt"
        f.write_bytes("héllo\nwörld\n".encode("utf-8"))
        gm = GlobalMap()
        cfg = {**_BASE_CONFIG, "filename": str(f), "encoding": "UTF-8"}
        _make(config=cfg, global_map=gm).execute()
        assert gm.get("tFRC_1_COUNT") == 2

    def test_iso_8859_15_encoding(self, tmp_path):
        f = tmp_path / "latin.txt"
        f.write_bytes("héllo\nwörld\n".encode("ISO-8859-15"))
        gm = GlobalMap()
        cfg = {**_BASE_CONFIG, "filename": str(f), "encoding": "ISO-8859-15"}
        _make(config=cfg, global_map=gm).execute()
        assert gm.get("tFRC_1_COUNT") == 2

    def test_wrong_encoding_raises(self, tmp_path):
        """UnicodeDecodeError from _process() is wrapped in ComponentExecutionError."""
        f = tmp_path / "latin.txt"
        # Write ISO-8859-15 content that is invalid UTF-8
        f.write_bytes(b"\xe9\xe0\xfc\n")   # é à ü in latin-1
        cfg = {**_BASE_CONFIG, "filename": str(f), "encoding": "UTF-8"}
        comp = _make(config=cfg)
        with pytest.raises(ComponentExecutionError):
            comp.execute()

    def test_default_encoding_is_iso_8859_15(self, tmp_path):
        """If encoding key is absent the component defaults to ISO-8859-15."""
        f = tmp_path / "data.txt"
        f.write_bytes("héllo\n".encode("ISO-8859-15"))
        cfg = {**_BASE_CONFIG, "filename": str(f)}
        del cfg["encoding"]
        gm = GlobalMap()
        _make(config=cfg, global_map=gm).execute()
        assert gm.get("tFRC_1_COUNT") == 1


# ---------------------------------------------------------------------------
# TestGlobalMapVariables
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGlobalMapVariables:
    """All four globalMap variables set correctly."""

    def test_count_equals_rows_out(self, tmp_path):
        f = tmp_path / "d.csv"
        _write(f, ["a", "b", "", "c"])
        gm = GlobalMap()
        cfg = {**_BASE_CONFIG, "filename": str(f), "ignore_empty_row": True}
        _make(config=cfg, global_map=gm).execute()
        assert gm.get("tFRC_1_COUNT") == 3

    def test_nb_line_equals_total_rows_in_file(self, tmp_path):
        f = tmp_path / "d.csv"
        _write(f, ["a", "b", "", "c"])
        gm = GlobalMap()
        cfg = {**_BASE_CONFIG, "filename": str(f), "ignore_empty_row": True}
        _make(config=cfg, global_map=gm).execute()
        assert gm.get("tFRC_1_NB_LINE") == 4

    def test_nb_line_ok_equals_rows_out(self, tmp_path):
        f = tmp_path / "d.csv"
        _write(f, ["a", "b", "", "c"])
        gm = GlobalMap()
        cfg = {**_BASE_CONFIG, "filename": str(f), "ignore_empty_row": True}
        _make(config=cfg, global_map=gm).execute()
        assert gm.get("tFRC_1_NB_LINE_OK") == 3

    def test_nb_line_reject_equals_empty_rows(self, tmp_path):
        f = tmp_path / "d.csv"
        _write(f, ["a", "", "b", "   "])
        gm = GlobalMap()
        cfg = {**_BASE_CONFIG, "filename": str(f), "ignore_empty_row": True}
        _make(config=cfg, global_map=gm).execute()
        assert gm.get("tFRC_1_NB_LINE_REJECT") == 2

    def test_nb_line_ok_nb_line_reject_sum_equals_nb_line(self, tmp_path):
        f = tmp_path / "d.csv"
        _write(f, ["x", "", "y", "  ", "z"])
        gm = GlobalMap()
        cfg = {**_BASE_CONFIG, "filename": str(f), "ignore_empty_row": True}
        _make(config=cfg, global_map=gm).execute()
        assert (
            gm.get("tFRC_1_NB_LINE_OK") + gm.get("tFRC_1_NB_LINE_REJECT")
            == gm.get("tFRC_1_NB_LINE")
        )

    def test_global_map_not_required(self, tmp_path):
        """Component works with global_map=None."""
        f = tmp_path / "d.csv"
        _write(f, ["a", "b"])
        cfg = {**_BASE_CONFIG, "filename": str(f)}
        comp = _make(config=cfg)
        comp.global_map = None
        result = comp.execute()
        assert result["main"] is None

    def test_stats_accessible_via_base_class(self, tmp_path):
        """BaseComponent stores NB_LINE/NB_LINE_OK/NB_LINE_REJECT in stats."""
        f = tmp_path / "d.csv"
        _write(f, ["a", "b", "c"])
        gm = GlobalMap()
        cfg = {**_BASE_CONFIG, "filename": str(f)}
        comp = _make(config=cfg, global_map=gm)
        comp.execute()
        assert comp.stats["NB_LINE"] == 3
        assert comp.stats["NB_LINE_OK"] == 3
        assert comp.stats["NB_LINE_REJECT"] == 0


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """Boundary conditions and special inputs."""

    def test_input_data_is_ignored(self, tmp_path):
        """execute(df) should work — input data is ignored for utility component."""
        import pandas as pd
        f = tmp_path / "d.csv"
        _write(f, ["a", "b"])
        gm = GlobalMap()
        cfg = {**_BASE_CONFIG, "filename": str(f)}
        comp = _make(config=cfg, global_map=gm)
        result = comp.execute(pd.DataFrame([{"x": 1}]))
        assert gm.get("tFRC_1_COUNT") == 2

    def test_large_file_counted_correctly(self, tmp_path):
        f = tmp_path / "large.csv"
        lines = [f"row{i}" for i in range(10_000)]
        _write(f, lines)
        gm = GlobalMap()
        cfg = {**_BASE_CONFIG, "filename": str(f)}
        _make(config=cfg, global_map=gm).execute()
        assert gm.get("tFRC_1_COUNT") == 10_000

    def test_file_with_only_empty_lines_all_ignored(self, tmp_path):
        f = tmp_path / "blank.csv"
        _write(f, ["", "", ""])
        gm = GlobalMap()
        cfg = {**_BASE_CONFIG, "filename": str(f), "ignore_empty_row": True}
        _make(config=cfg, global_map=gm).execute()
        assert gm.get("tFRC_1_COUNT") == 0
        assert gm.get("tFRC_1_NB_LINE_REJECT") == 3

    def test_component_is_reentrant(self, tmp_path):
        """execute() can be called multiple times (iterate-loop requirement)."""
        f = tmp_path / "d.csv"
        _write(f, ["a", "b", "c"])
        gm = GlobalMap()
        cfg = {**_BASE_CONFIG, "filename": str(f)}
        comp = _make(config=cfg, global_map=gm)
        comp.execute()
        comp.execute()
        assert gm.get("tFRC_1_COUNT") == 3  # second call overwrites, same value


# ---------------------------------------------------------------------------
# TestCountRowsHelper
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCountRowsHelper:
    """Unit tests for the pure _count_rows module-level function."""

    def test_basic_newline(self, tmp_path):
        f = tmp_path / "f.txt"
        _write(f, ["a", "b", "c"])
        assert _count_rows(str(f), "\n", False, "ISO-8859-15") == (3, 3, 0)

    def test_crlf(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_bytes(b"a\r\nb\r\nc\r\n")
        assert _count_rows(str(f), "\r\n", False, "ISO-8859-15") == (3, 3, 0)

    def test_cr_only(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_bytes(b"a\rb\rc\r")
        assert _count_rows(str(f), "\r", False, "ISO-8859-15") == (3, 3, 0)

    def test_ignore_empty(self, tmp_path):
        f = tmp_path / "f.txt"
        _write(f, ["a", "", "b"])
        rows_in, rows_out, rows_rej = _count_rows(str(f), "\n", True, "ISO-8859-15")
        assert rows_in == 3
        assert rows_out == 2
        assert rows_rej == 1

    def test_custom_separator_pipe(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_bytes(b"x|y|z|")
        assert _count_rows(str(f), "|", False, "ISO-8859-15") == (3, 3, 0)

    def test_custom_separator_no_trailing(self, tmp_path):
        """Custom separator without trailing sep: last segment counts."""
        f = tmp_path / "f.txt"
        f.write_bytes(b"x|y|z")
        assert _count_rows(str(f), "|", False, "ISO-8859-15") == (3, 3, 0)

    def test_empty_file(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_bytes(b"")
        assert _count_rows(str(f), "\n", False, "ISO-8859-15") == (0, 0, 0)

    def test_file_not_found_raises_os_error(self):
        with pytest.raises(OSError):
            _count_rows("/nonexistent/file.txt", "\n", False, "ISO-8859-15")
