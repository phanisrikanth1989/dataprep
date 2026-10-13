"""Prejob: where a job's set-up starts."""
from __future__ import annotations

from ...job.keys import Key, Kind
from ..base import BEFORE, Action
from ..registry import REGISTRY


@REGISTRY.register
class Prejob(Action):
    """Mark where a job's set-up starts: what its trigger leads to runs before everything else in the job.

    It does nothing itself. When the set-up fails, the job itself is not
    run: what it would have worked with is not there. What a postjob sets
    off still runs. Nothing leads to a prejob, and no flow comes to it or
    leaves it.
    """

    names = ("prejob", "Prejob", "tPrejob")
    part = BEFORE
    keys = (
        Key("die_on_error", kind=Kind.IGNORED, type=object, doc="Nothing here can fail; v1 reads it on every component."),
    )

    def act(self) -> None:
        """Nothing: it is a mark."""
