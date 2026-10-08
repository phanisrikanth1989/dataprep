"""What a run carries: context values, globalMap entries, routines."""
from __future__ import annotations

import os
import re
import tempfile
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

import polars as pl

from ..errors import ConfigurationError

_TEMPLATE = re.compile(r"\$\{context\.(\w+)\}")
_BARE = re.compile(r"\bcontext\.(\w+)\b")


class RunContext:
    """The state of one run of one job.

    Attributes:
        job_name: The job's name.
        context: Context variables. A component may change them; components
            built later see the change.
        context_types: The declared type name of each context variable that
            has one (``int``, ``id_Integer``, ``str``...).
        global_map: Entries set while the job runs, such as row counts.
        routines: Routine modules: name to its functions.
    """

    def __init__(
        self,
        job_name: str,
        context: Mapping[str, Any],
        routines: Optional[Mapping[str, Mapping[str, Callable[..., Any]]]] = None,
        context_types: Optional[Mapping[str, str]] = None,
    ) -> None:
        self.job_name = job_name
        self.context: Dict[str, Any] = dict(context)
        self.context_types: Dict[str, str] = dict(context_types or {})
        self.global_map: Dict[str, Any] = {}
        self.routines: Mapping[str, Mapping[str, Callable[..., Any]]] = routines or {}
        self._scratch: List[str] = []
        # The UTF-8 copies files in other encodings are read through: (file, encoding) to the copy.
        self.utf8_copies: Dict[Tuple[str, str], str] = {}
        # Every text of the job config that could name a globalMap entry; None when the job is not known.
        self.job_text: Optional[str] = None
        # Whether a source may let Polars parse numbers itself. That is faster and fails outright on a
        # value only the tolerant reader takes (" 7 ", "1.0" for a whole number), so the engine allows
        # it only where it can run the subjob again, and a source that uses it says so.
        self.fast_read = False
        self.used_fast_read = False
        # The sources of the subjob being run, by id: a failure asks them where a row's number is.
        self.sources: Dict[str, Any] = {}

    @staticmethod
    def noticing(frame: pl.LazyFrame, kind: pl.Expr) -> Tuple[pl.LazyFrame, Callable[[], bool]]:
        """A frame that notes whether a row of a kind passes through it.

        The frame hands every row on as it is, and looks at each batch of
        rows as the subjob's pass brings it by. That costs no reading of its
        own, which a second frame over the same rows would: the engine
        counts the rows handed to a file output the same way.

        Args:
            frame: The rows.
            kind: True for a row of the kind looked for.

        Returns:
            The frame to go on with, and the question, to be asked once the
            subjob has run, whether any such row passed.
        """
        passed: List[bool] = []

        def notice(batch: pl.DataFrame) -> pl.DataFrame:
            # Batches arrive from several threads; adding to a list is safe from all of them.
            if batch.select(kind.any()).item():
                passed.append(True)
            return batch

        # A filter on the kind has to stay above this, or rows of the kind would never be seen here.
        noting = frame.map_batches(notice, streamable=True, validate_output_schema=False, predicate_pushdown=False)
        return noting, lambda: bool(passed)

    def reads(self, key: str) -> bool:
        """Whether anything in the job reads a globalMap entry.

        A component asks before it computes a value that costs something
        (a count over its rows) only to put it in the globalMap. True when
        the name stands anywhere in the job config, or when the job is not
        known.
        """
        return self.job_text is None or key in self.job_text

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
        self.utf8_copies.clear()
        self.sources.clear()


def _as_text(value: Any) -> str:
    return "" if value is None else str(value)
