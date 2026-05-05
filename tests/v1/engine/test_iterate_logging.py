"""Unit tests for iterate logging (Phase 10-06).

Covers D-H1..H7 incl. ASCII-only enforcement and threshold-based behavior switch.
"""
import logging
import pytest

from src.v1.engine.iterate_logging import (
    DEFAULT_LOG_PER_ITER_THRESHOLD,
    log_iterate_start,
    log_iterate_end,
    log_iteration_progress,
    log_body_component_debug,
)


def _assert_ascii(records):
    for rec in records:
        msg = rec.getMessage()
        for ch in msg:
            assert ord(ch) < 128, f"Non-ASCII char in log message: {msg!r}"


class TestIterateStartLog:
    def test_format(self, caplog):
        with caplog.at_level(logging.INFO, logger="src.v1.engine.iterate"):
            log_iterate_start("iter1", 5, 3)
        assert any(
            "[iter1] Starting iterate: 5 items, 3 components in body" in r.getMessage()
            for r in caplog.records
        )
        _assert_ascii(caplog.records)


class TestIterateEndLog:
    def test_format(self, caplog):
        with caplog.at_level(logging.INFO, logger="src.v1.engine.iterate"):
            log_iterate_end("iter1", 4, 1, 2.34)
        messages = [r.getMessage() for r in caplog.records]
        assert any(
            "[iter1] Iterate complete: 4 OK, 1 errors, total elapsed=2.34s" in m
            for m in messages
        )
        _assert_ascii(caplog.records)


class TestPerIterationLogBelowThreshold:
    def test_below_threshold_emits_per_iter(self, caplog):
        with caplog.at_level(logging.INFO, logger="src.v1.engine.iterate"):
            log_iteration_progress(
                cid="iter1", index=3, total=10, iter_time=0.5,
                key_info="file=/tmp/x.txt", threshold=50, avg_iter_time=0.5,
            )
        messages = [r.getMessage() for r in caplog.records]
        assert any(
            "[iter1] Iteration 3/10: file=/tmp/x.txt | iter_time=0.50s" in m
            for m in messages
        )
        _assert_ascii(caplog.records)

    def test_at_threshold_inclusive_emits_per_iter(self, caplog):
        with caplog.at_level(logging.INFO, logger="src.v1.engine.iterate"):
            log_iteration_progress(
                cid="iter1", index=1, total=50, iter_time=0.1,
                key_info="row_index=1", threshold=50, avg_iter_time=0.1,
            )
        assert any("Iteration 1/50" in r.getMessage() for r in caplog.records)


class TestPerIterationLogAboveThreshold:
    def test_rate_limited_at_10_percent(self, caplog):
        # total=200, threshold=50 -> emit at iter 20, 40, 60, ..., 200
        with caplog.at_level(logging.INFO, logger="src.v1.engine.iterate"):
            # Iter 19 should NOT emit
            log_iteration_progress(
                cid="iter1", index=19, total=200, iter_time=0.1,
                key_info="x", threshold=50, avg_iter_time=0.1,
            )
            assert not any("19/200" in r.getMessage() for r in caplog.records)

            # Iter 20 SHOULD emit
            log_iteration_progress(
                cid="iter1", index=20, total=200, iter_time=0.1,
                key_info="x", threshold=50, avg_iter_time=0.1,
            )
            assert any("20/200" in r.getMessage() for r in caplog.records)

    def test_progress_line_format(self, caplog):
        with caplog.at_level(logging.INFO, logger="src.v1.engine.iterate"):
            log_iteration_progress(
                cid="iter1", index=100, total=200, iter_time=0.1,
                key_info="x", threshold=50, avg_iter_time=0.5,
            )
        # eta = (200-100) * 0.5 = 50.0
        messages = [r.getMessage() for r in caplog.records]
        assert any(
            "[iter1] 100/200 iterations complete (50%, eta 50.0s)" in m
            for m in messages
        )


class TestUnboundedIterator:
    def test_total_negative_treated_as_per_iter(self, caplog):
        with caplog.at_level(logging.INFO, logger="src.v1.engine.iterate"):
            log_iteration_progress(
                cid="iter1", index=5, total=-1, iter_time=0.1,
                key_info="x", threshold=50, avg_iter_time=0.1,
            )
        assert any("Iteration 5/-1" in r.getMessage() for r in caplog.records)


class TestBodyComponentDebugTrace:
    def test_debug_format(self, caplog):
        with caplog.at_level(logging.DEBUG, logger="src.v1.engine.iterate"):
            log_body_component_debug("iter1", 2, "body_1", 10, 2)
        messages = [r.getMessage() for r in caplog.records]
        assert any(
            "[iter1.iter=2] body_1: NB_LINE=10 NB_REJECT=2" in m
            for m in messages
        )


class TestAsciiOnly:
    def test_all_logging_helpers_emit_ascii(self, caplog):
        with caplog.at_level(logging.DEBUG, logger="src.v1.engine.iterate"):
            log_iterate_start("iter1", 100, 5)
            log_iterate_end("iter1", 80, 20, 12.345)
            log_iteration_progress(
                cid="iter1", index=10, total=20, iter_time=0.1,
                key_info="file=/x/y.txt", threshold=50, avg_iter_time=0.1,
            )
            log_iteration_progress(
                cid="iter1", index=20, total=200, iter_time=0.1,
                key_info="row_index=20", threshold=50, avg_iter_time=0.1,
            )
            log_body_component_debug("iter1", 5, "body_1", 100, 0)
        _assert_ascii(caplog.records)


class TestGetIterKeyInfo:
    def test_filelist_returns_file_path(self):
        from pathlib import Path
        from src.v1.engine.components.file.file_list import FileList, FileListItem
        comp = object.__new__(FileList)  # bare instance for hook test
        item = FileListItem(path=Path("/x/y.txt"), name="y.txt", parent=Path("/x"), ext="txt", index=1)
        assert comp.get_iter_key_info(item, 1) == "file=/x/y.txt"

    def test_flowtoiterate_returns_row_index(self):
        from src.v1.engine.components.iterate.flow_to_iterate import FlowToIterate, FlowToIterateItem
        comp = object.__new__(FlowToIterate)
        item = FlowToIterateItem(row={"a": 1}, index=3)
        assert comp.get_iter_key_info(item, 3) == "row_index=3"

    def test_default_returns_index(self):
        from src.v1.engine.base_iterate_component import BaseIterateComponent
        comp = object.__new__(BaseIterateComponent)
        assert comp.get_iter_key_info(object(), 7) == "index=7"
