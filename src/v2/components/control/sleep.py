"""Sleep: the job waits a number of seconds."""
from __future__ import annotations

import logging
import math
import time

from ...job.keys import Key, Kind
from ..base import Action
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


def _seconds(value: float) -> float:
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{value:g} seconds is no time to wait; give zero or more")
    return value


@REGISTRY.register
class Sleep(Action):
    """Wait `pause_duration` seconds, and then let the job go on.

    It stands alone: a trigger or an iterate link leads to it, and no flow
    comes to it or leaves it. A part of a second may be given, and the
    value may come from the context. What is no number of zero or more
    refuses the job, or fails it when the value is known only as its turn
    comes. The log says how long it waits, before and after. Whoever
    stops the job ends the wait at once. It counts one row.

    It waits a length of time, not for anything: a file that is still
    being written is a file list's `min_age_seconds`.
    """

    names = ("sleep", "Sleep", "SleepComponent", "tSleep")
    keys = (
        Key("pause_duration", type=float, default=1.0, convert=_seconds,
            doc="How long to wait, in seconds; a part of a second may be given."),
        Key("die_on_error", kind=Kind.IGNORED, type=object, doc="Nothing here can fail; v1 reads it on every component."),
    )

    def act(self) -> None:
        seconds = self.config["pause_duration"]
        logger.info(f"[{self.id}] waiting {seconds:g} s")
        time.sleep(seconds)
        logger.info(f"[{self.id}] waited {seconds:g} s")
        self.global_map.update({f"{self.id}_NB_LINE": 1, f"{self.id}_NB_LINE_OK": 1, f"{self.id}_NB_LINE_REJECT": 0})
