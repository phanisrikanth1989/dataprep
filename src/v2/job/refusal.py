"""Refusals: the reasons a job config cannot run on v2."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Iterator, List

from ..errors import JobRefusedError


@dataclass(frozen=True)
class Refusal:
    """One reason a job config is refused.

    Attributes:
        where: The part of the job config it belongs to, in words a user can
            find: ``"job"``, ``"component in_1 (FileInputDelimited)"``.
        key: The config key as the user wrote it, with its path inside nested
            values: ``"encoding"``, ``"criteria[1].colum"``.
        reason: Why v2 refuses it.
    """

    where: str
    key: str
    reason: str


@dataclass
class RefusalReport:
    """Everything in one job config that v2 refuses, gathered in one pass."""

    job_name: str = ""
    refusals: List[Refusal] = field(default_factory=list)

    def add(self, where: str, key: str, reason: str) -> None:
        """Record one refusal."""
        self.refusals.append(Refusal(where, key, reason))

    def extend(self, refusals: Iterable[Refusal]) -> None:
        """Record several refusals."""
        self.refusals.extend(refusals)

    def __bool__(self) -> bool:
        return bool(self.refusals)

    def __len__(self) -> int:
        return len(self.refusals)

    def __iter__(self) -> Iterator[Refusal]:
        return iter(self.refusals)

    def raise_if_refused(self) -> None:
        """Raise ``JobRefusedError`` when the report holds anything."""
        if self.refusals:
            raise JobRefusedError(self)

    def format(self) -> str:
        """Render the report as plain ASCII text, grouped by owner."""
        if not self.refusals:
            return f"Job '{self.job_name}': nothing refused."
        count = len(self.refusals)
        noun = "problem" if count == 1 else "problems"
        lines = [f"Job '{self.job_name}' cannot run on v2: {count} {noun}."]
        owners: List[str] = []
        for refusal in self.refusals:
            if refusal.where not in owners:
                owners.append(refusal.where)
        for owner in owners:
            lines.append("")
            lines.append(f"{owner}:")
            for refusal in self.refusals:
                if refusal.where == owner:
                    key = f"{refusal.key}: " if refusal.key else ""
                    lines.append(f"  - {key}{refusal.reason}")
        return "\n".join(lines)
