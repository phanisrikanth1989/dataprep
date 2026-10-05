"""What a run carries: context values, globalMap entries, routines."""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, Mapping, Optional

from ..errors import ConfigurationError

_TEMPLATE = re.compile(r"\$\{context\.(\w+)\}")
_BARE = re.compile(r"context\.(\w+)")


class RunContext:
    """The state of one run of one job.

    Attributes:
        job_name: The job's name.
        context: Context variables. A component may change them; components
            built later see the change.
        global_map: Entries set while the job runs, such as row counts.
        routines: Routine modules: name to its functions.
    """

    def __init__(
        self,
        job_name: str,
        context: Mapping[str, Any],
        routines: Optional[Mapping[str, Mapping[str, Callable[..., Any]]]] = None,
    ) -> None:
        self.job_name = job_name
        self.context: Dict[str, Any] = dict(context)
        self.global_map: Dict[str, Any] = {}
        self.routines: Mapping[str, Mapping[str, Callable[..., Any]]] = routines or {}

    def resolve(self, text: str) -> Any:
        """Replace context references in a config value.

        A value that is nothing but one reference, ``${context.x}`` or
        ``context.x``, becomes the variable's own value, type kept. Anywhere
        else ``${context.x}`` is replaced by the value as text.

        Raises:
            ConfigurationError: When a named variable does not exist.
        """
        whole = _TEMPLATE.fullmatch(text) or _BARE.fullmatch(text)
        if whole:
            return self._value(whole.group(1))
        return _TEMPLATE.sub(lambda match: _as_text(self._value(match.group(1))), text)

    def _value(self, name: str) -> Any:
        if name not in self.context:
            raise ConfigurationError(f"context has no variable '{name}'")
        return self.context[name]


def _as_text(value: Any) -> str:
    return "" if value is None else str(value)
