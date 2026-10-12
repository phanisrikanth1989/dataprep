"""Postjob: where a job's clean-up starts."""
from __future__ import annotations

from ...job.keys import Key, Kind
from ..base import AFTER, Action
from ..registry import REGISTRY


@REGISTRY.register
class Postjob(Action):
    """Mark where a job's clean-up starts: what its trigger leads to runs after everything else in the job.

    It does nothing itself. The clean-up runs whatever became of the job:
    after a failure, and after a die. A clean-up that fails fails the job,
    and does not hide why the job had failed before it. A step meant for
    a job that succeeded stands behind the job's own subjob, on its
    OnSubjobOk trigger. Nothing leads to a postjob, and no flow comes to
    it or leaves it.
    """

    names = ("postjob", "Postjob", "tPostjob")
    part = AFTER
    keys = (
        Key("die_on_error", kind=Kind.IGNORED, type=object, doc="Nothing here can fail; v1 reads it on every component."),
    )

    def act(self) -> None:
        """Nothing: it is a mark."""
