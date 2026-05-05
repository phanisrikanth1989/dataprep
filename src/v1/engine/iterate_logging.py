"""Iterate logging infrastructure (Phase 10-06).

4-tier ASCII-only logging for iterate components per D-H1..H7:
  D-H1: iterate-start INFO
  D-H2: iterate-end INFO
  D-H3: per-iteration INFO when total <= threshold
  D-H4: rate-limited 10% progress INFO when total > threshold
  D-H5: DEBUG per-body-component trace per iteration
  D-H6: configurable threshold (default 50)
  D-H7: ASCII-only enforcement -- no emojis, no unicode arrows, no box-drawing.

All log lines emitted by these helpers are pure ASCII; tests assert this.
"""
import logging
from typing import Optional

logger = logging.getLogger("src.v1.engine.iterate")

DEFAULT_LOG_PER_ITER_THRESHOLD: int = 50
PROGRESS_INTERVAL_PERCENT: int = 10  # rate-limit: every 10% of total


def log_iterate_start(cid: str, total_items: int, body_component_count: int) -> None:
    """Emit D-H1: iterate-start INFO line.

    Args:
        cid: Iterate component ID.
        total_items: Total number of iteration items (-1 if unbounded).
        body_component_count: Number of components in the iterate body.
    """
    logger.info(
        "[%s] Starting iterate: %d items, %d components in body",
        cid, total_items, body_component_count,
    )


def log_iterate_end(
    cid: str,
    n_ok: int,
    n_err: int,
    total_elapsed: float,
) -> None:
    """Emit D-H2: iterate-end INFO line.

    Args:
        cid: Iterate component ID.
        n_ok: Number of successful iterations.
        n_err: Number of failed iterations.
        total_elapsed: Total elapsed time in seconds.
    """
    logger.info(
        "[%s] Iterate complete: %d OK, %d errors, total elapsed=%.2fs",
        cid, n_ok, n_err, total_elapsed,
    )


def log_iteration_progress(
    cid: str,
    index: int,
    total: int,
    iter_time: float,
    key_info: str,
    threshold: int,
    avg_iter_time: Optional[float] = None,
) -> None:
    """Emit D-H3 (per-iter) or D-H4 (rate-limited 10% progress) INFO line.

    When total <= 0 or total <= threshold: emits a per-iteration INFO line
    (D-H3) with key_info and iter_time for every iteration.

    When total > threshold: rate-limits to every 10% of total iterations
    (D-H4) emitting a progress line with percent complete and ETA.

    Args:
        cid: Iterate component ID.
        index: 1-based current iteration index.
        total: Total expected iterations (-1 if unbounded).
        iter_time: Time taken for this iteration in seconds.
        key_info: Component-specific key info string (e.g. "file=/tmp/x.txt").
        threshold: Log-per-iteration threshold. When total > threshold, rate-limit.
        avg_iter_time: Running average iteration time for ETA calculation.
    """
    if total <= 0 or total <= threshold:
        # D-H3: per-iteration line for small iterates
        logger.info(
            "[%s] Iteration %d/%d: %s | iter_time=%.2fs",
            cid, index, total if total > 0 else -1, key_info, iter_time,
        )
    else:
        # D-H4: rate-limited every 10% for large iterates
        interval = max(1, total // (100 // PROGRESS_INTERVAL_PERCENT))
        if index % interval != 0 and index != total:
            return  # skip this iteration
        percent = int((index / total) * 100)
        if avg_iter_time is not None and avg_iter_time > 0:
            remaining = total - index
            eta = remaining * avg_iter_time
        else:
            eta = 0.0
        logger.info(
            "[%s] %d/%d iterations complete (%d%%, eta %.1fs)",
            cid, index, total, percent, eta,
        )


def log_body_component_debug(
    cid: str,
    iter_index: int,
    body_id: str,
    nb_line: int,
    nb_reject: int,
) -> None:
    """Emit D-H5: per-body-component DEBUG trace per iteration.

    Args:
        cid: Iterate component ID.
        iter_index: 1-based current iteration index.
        body_id: Body component ID.
        nb_line: NB_LINE stat for this body component.
        nb_reject: NB_LINE_REJECT stat for this body component.
    """
    logger.debug(
        "[%s.iter=%d] %s: NB_LINE=%d NB_REJECT=%d",
        cid, iter_index, body_id, nb_line, nb_reject,
    )
