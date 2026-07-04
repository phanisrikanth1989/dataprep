"""Root pytest configuration -- Phase 14 pipeline-test infrastructure.

Provides cross-tree helpers used by Phase 14 subsystem-lift plans:

- ``PipelineResult`` -- structured result of a fixture-job run via ETLEngine.
- ``FIXTURE_JOBS_ROOT`` -- absolute Path to ``tests/fixtures/jobs``.
- ``run_job_fixture`` -- callable that loads a fixture JSON, applies optional
  per-component config mutations onto a tmp_path copy, runs ``ETLEngine.execute()``,
  and returns a ``PipelineResult`` snapshot of stats + globalMap + engine + path.
- ``assert_ascii_logs`` -- captures DEBUG-level log records during a test and
  fails on teardown if any captured message contains a non-ASCII byte (project
  rule: ASCII-only logging on RHEL servers).

This file complements ``tests/v1/engine/conftest.py`` (engine-specific stubs:
StubComponent, IterateStubComponent, java_bridge). pytest discovers both via
parent-walk; do NOT shadow or replace the engine conftest.

Pattern reference: tests/integration/test_iterate_e2e.py (the seed pattern that
this generalizes).
"""

from __future__ import annotations

import copy
import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import pytest

from src.v1.engine.engine import ETLEngine


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

FIXTURE_JOBS_ROOT: Path = Path(__file__).resolve().parent / "fixtures" / "jobs"
"""Absolute path to the fixture-jobs root used by ``run_job_fixture``."""


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class PipelineResult:
    """Result of a fixture-job execution via ``run_job_fixture``.

    Attributes:
        stats: Dict returned by ``ETLEngine.execute()`` (job-level stats).
        global_map: Snapshot of ``engine.global_map.get_all()`` taken AFTER
            ``execute()`` returns. Independent of the live engine instance so
            the test can mutate it freely.
        engine: The live ``ETLEngine`` instance, retained for tests that want
            to reach into ``engine.components``, ``engine.context_manager``,
            etc., for assertions beyond stats and globalMap.
        json_path: Path to the mutated copy of the fixture JSON inside
            ``tmp_path``. Useful for tests that need to re-read the executed
            config or inspect the on-disk shape post-mutation.
    """

    stats: Dict[str, Any]
    global_map: Dict[str, Any]
    engine: ETLEngine
    json_path: Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _apply_mutations(
    config: Dict[str, Any],
    mutations: Optional[Dict[str, Dict[str, Any]]],
) -> None:
    """Apply per-component config overrides in place.

    Mutations is a mapping of component_id -> dict of config-key overrides.
    Each override is merged shallowly into the matching component's
    ``config`` dict via ``setdefault("config", {})[key] = value``. Components
    not named in ``mutations`` are left untouched.

    Args:
        config: Parsed job-config dict (mutated in place).
        mutations: Optional component_id -> {config_key: value} dict. ``None``
            and empty dict are no-ops.
    """
    if not mutations:
        return
    for comp in config.get("components", []):
        comp_id = comp.get("id")
        if comp_id in mutations:
            for key, val in mutations[comp_id].items():
                comp.setdefault("config", {})[key] = val


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def run_job_fixture(
    tmp_path: Path,
) -> Callable[..., PipelineResult]:
    """Return a callable that runs a fixture JSON job through ``ETLEngine``.

    Usage::

        def test_something(run_job_fixture, tmp_path):
            result = run_job_fixture(
                "file/csv_with_header",
                mutations={
                    "tFileInputDelimited_1": {"filepath": str(tmp_path / "in.csv")},
                },
            )
            assert result.global_map["tFileInputDelimited_1_NB_LINE"] == 3

    Behavior:
      1. Locate the fixture JSON at ``FIXTURE_JOBS_ROOT / f"{name}.json"``.
      2. Copy it to ``tmp_path / f"{<basename>}.json"`` so mutations never
         touch the on-disk fixture.
      3. Apply ``mutations`` (component_id -> {config_key: value}) to the
         copy.
      4. Build ``ETLEngine(config_dict)`` and call ``.execute()``.
      5. Return a ``PipelineResult`` snapshot. ``global_map`` is a shallow
         copy via ``dict(engine.global_map.get_all())`` so tests can mutate
         it freely.

    Args:
        tmp_path: pytest tmp_path fixture (auto-injected).

    Returns:
        Callable ``(name, mutations=None) -> PipelineResult``.
    """

    def _run(
        name: str,
        mutations: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> PipelineResult:
        src = FIXTURE_JOBS_ROOT / f"{name}.json"
        if not src.is_file():
            raise FileNotFoundError(
                f"Pipeline fixture not found: {src} "
                f"(FIXTURE_JOBS_ROOT={FIXTURE_JOBS_ROOT})"
            )

        # Copy fixture into tmp so we can mutate without dirtying the on-disk
        # fixture. Use the basename of the slug to keep tmp paths short and
        # readable.
        dst = tmp_path / f"{Path(name).name}.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)

        with dst.open("r", encoding="utf-8") as f:
            config = json.load(f)

        _apply_mutations(config, mutations)

        # Persist the mutated config back to disk so tests that pass json_path
        # to other helpers (or re-read it) see the actual config that ran.
        with dst.open("w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

        # ETLEngine accepts a dict directly; pass a deep copy so engine-side
        # mutation (e.g. context resolution) does not surprise the caller.
        engine = ETLEngine(copy.deepcopy(config))
        stats = engine.execute()
        global_map_snapshot = dict(engine.global_map.get_all())

        return PipelineResult(
            stats=stats,
            global_map=global_map_snapshot,
            engine=engine,
            json_path=dst,
        )

    return _run


@pytest.fixture
def assert_ascii_logs(caplog: pytest.LogCaptureFixture):
    """Capture log records at DEBUG and fail on teardown if any non-ASCII byte appears.

    Project rule (memory ``feedback_ascii_logging``): RHEL servers consume
    DataPrep logs. Emojis and unicode break log shipping pipelines. Phase 14
    tests opt into this fixture to enforce the rule on whatever code path the
    test exercises.

    Usage::

        def test_runs_clean(run_job_fixture, assert_ascii_logs):
            run_job_fixture("file/csv_with_header", mutations={...})
            # On teardown, fixture asserts no captured log message contains
            # a non-ASCII byte. No explicit assertion needed in the test body.

    The fixture yields ``caplog`` so the test can also do positive-content
    assertions (e.g. ``assert "wrote 3 rows" in caplog.text``).
    """
    caplog.set_level(logging.DEBUG)
    yield caplog
    offenders = []
    for record in caplog.records:
        message = record.getMessage()
        try:
            message.encode("ascii")
        except UnicodeEncodeError:
            offenders.append(
                f"  [{record.levelname}] {record.name}: {message!r}"
            )
    if offenders:
        joined = "\n".join(offenders)
        raise AssertionError(
            "Non-ASCII log message(s) captured (project rule: ASCII-only logs):\n"
            + joined
        )
