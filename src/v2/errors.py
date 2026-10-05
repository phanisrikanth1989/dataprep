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


class ExpressionError(V2Error):
    """An expression cannot be translated into Polars.

    Attributes:
        expression: The whole expression as written.
        reason: What is wrong, naming the part that cannot be translated.
    """

    def __init__(self, expression: str, reason: str) -> None:
        super().__init__(f"{reason} (in: {expression})")
        self.expression = expression
        self.reason = reason
