"""Run one job on one engine and leave a note of how it went.

This is the process the scenario times. It is started once per run by
``scenarios.payments.run``, which measures it from the outside: the time
from start to exit and the most memory it held. From the inside it notes
when each stage of the job began, taken from the line each engine logs
when it starts a subjob.

    python -m scenarios.payments.engine_run v2 job.json note.json
"""
import time

_BEGAN = time.perf_counter()

import json  # noqa: E402
import logging  # noqa: E402
import sys  # noqa: E402
import warnings  # noqa: E402
from typing import Any, Dict, List  # noqa: E402

STAGES = ("settings", "validate and enrich", "reject report")
# The logger that says a subjob starts, and the words it says it with, per engine.
_STARTS = {
    "v1": ("src.v1.engine.executor", "Executing subjob:"),
    "v2": ("src.v2.engine.runner", "subjob starting:"),
}


class _StageClock(logging.Handler):
    """Notes the moment each subjob starts."""

    def __init__(self, words: str) -> None:
        super().__init__(level=logging.INFO)
        self.words = words
        self.starts: List[float] = []

    def emit(self, record: logging.LogRecord) -> None:
        if self.words in record.getMessage():
            self.starts.append(time.perf_counter())


def _stages(starts: List[float], ended: float) -> List[Dict[str, Any]]:
    """Start-up, then each stage: from its start to the next one's, the last to the end of the job."""
    edges = [_BEGAN] + starts + [ended]
    names = ("start-up",) + STAGES
    return [
        {"name": name, "seconds": round(edges[place + 1] - edges[place], 3)}
        for place, name in enumerate(names[:len(edges) - 1])
    ]


def main(argv: List[str]) -> int:
    engine, job_path, note_path = argv
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format="%(levelname)s %(name)s - %(message)s")
    logger_name, words = _STARTS[engine]
    clock = _StageClock(words)
    stage_logger = logging.getLogger(logger_name)
    stage_logger.setLevel(logging.INFO)
    stage_logger.addHandler(clock)
    stage_logger.propagate = False
    # Cut off from the root logger so that its INFO lines are not printed; what it warns of still is.
    loud = logging.StreamHandler(sys.stderr)
    loud.setLevel(logging.WARNING)
    loud.setFormatter(logging.Formatter("%(levelname)s %(name)s - %(message)s"))
    stage_logger.addHandler(loud)

    with open(job_path, encoding="utf-8") as handle:
        job = json.load(handle)
    note: Dict[str, Any] = {"engine": engine}
    if engine == "v2":
        from src.v2 import run_job

        result = run_job(job)
        note.update(status=result.status, error=result.error or "", written=result.rows)
    else:
        from src.v1.engine.engine import ETLEngine

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = ETLEngine(job).execute()
        steps = result.get("component_stats") or result.get("stats") or {}
        note.update(
            status=result.get("status"), error=str(result.get("error") or ""),
            # v1 runs one component at a time and says how long each took.
            components={name: round(float(step.get("execution_time", 0.0)), 3) for name, step in steps.items()
                        if isinstance(step, dict)},
        )
    note["stages"] = _stages(clock.starts, time.perf_counter())
    with open(note_path, "w", encoding="utf-8") as handle:
        json.dump(note, handle)
    return 0 if note["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
