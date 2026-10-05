"""Errors the v2 engine raises."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .job.refusal import RefusalReport


class V2Error(Exception):
    """Root of every error the v2 engine raises."""


class JobRefusedError(V2Error):
    """A job config holds something v2 will not run with.

    Raised before anything runs. ``report`` lists every problem found.
    """

    def __init__(self, report: "RefusalReport") -> None:
        super().__init__(report.format())
        self.report = report
