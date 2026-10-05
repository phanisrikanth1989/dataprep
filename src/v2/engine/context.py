"""What a run carries: context values, globalMap entries, routines."""
from __future__ import annotations

import os
import re
import tempfile
from typing import Any, Callable, Dict, List, Mapping, Optional

from ..errors import ConfigurationError

_TEMPLATE = re.compile(r"\$\{context\.(\w+)\}")
_BARE = re.compile(r"\bcontext\.(\w+)\b")


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
        self._scratch: List[str] = []

    def resolve(self, text: str) -> Any:
        """Replace context references in a config value, as v1 does.

        ``${context.x}`` and a bare ``context.x`` are both replaced by the
        variable's value as text, wherever they stand. A bare reference to a
        variable that does not exist is left as written (it may be part of a
        file name). A value that is nothing but one reference becomes the
        variable's own value, type kept.

        Raises:
            ConfigurationError: When ``${context.x}`` names a variable that
                does not exist.
        """
        whole = _TEMPLATE.fullmatch(text) or _BARE.fullmatch(text)
        if whole and whole.group(1) in self.context:
            return self.context[whole.group(1)]
        text = _TEMPLATE.sub(lambda match: _as_text(self._value(match.group(1))), text)
        return _BARE.sub(self._bare, text)

    def _value(self, name: str) -> Any:
        if name not in self.context:
            raise ConfigurationError(f"context has no variable '{name}'")
        return self.context[name]

    def _bare(self, match: "re.Match[str]") -> str:
        name = match.group(1)
        return _as_text(self.context[name]) if name in self.context else match.group(0)

    # ------------------------------------------------------------------
    # Scratch files
    # ------------------------------------------------------------------

    def temp_path(self, suffix: str = "") -> str:
        """A fresh scratch file, removed when the job ends.

        Scratch files go to the folder named by the ``V2_TEMP_DIR``
        environment variable, or to the system's temporary folder.
        """
        handle, path = tempfile.mkstemp(prefix="v2_", suffix=suffix, dir=os.environ.get("V2_TEMP_DIR") or None)
        os.close(handle)
        self._scratch.append(path)
        return path

    def cleanup(self) -> None:
        """Remove every scratch file handed out."""
        for path in self._scratch:
            try:
                os.remove(path)
            except OSError:
                pass
        self._scratch.clear()


def _as_text(value: Any) -> str:
    return "" if value is None else str(value)
