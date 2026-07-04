"""Engine component for RowGenerator (tRowGenerator).

Source component -- generates a configurable number of rows from column
expressions.  No input DataFrame is required.

Config keys consumed:
    nb_rows  (int | str, default "100") -- number of rows to generate;
                                           supports context variable references.
    values   (list[dict], required)     -- [{schema_column: str, array: str}, ...]
                                            one entry per output column.
    tstatcatcher_stats (bool, default False) -- BaseComponent stats hook (passthrough).
    label              (str,  default "")    -- BaseComponent display label (passthrough).

GlobalMap variables set:
    {id}_NB_LINE        -- total rows attempted (accepted + rejected)
    {id}_NB_LINE_OK     -- accepted rows
    {id}_NB_LINE_REJECT -- rejected rows
"""
import logging
import re
import random as _random_module
from typing import Any, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, ExpressionError

logger = logging.getLogger(__name__)

# Restricted eval globals -- only ``random`` is exposed to expression code.
_EVAL_GLOBALS: dict[str, Any] = {"__builtins__": {}, "random": _random_module}

# Compiled patterns for Talend StringHandling calls.
_RE_SH_SPACE = re.compile(r"StringHandling\.SPACE\(([^)]+)\)")
_RE_SH_LEN = re.compile(r"StringHandling\.LEN\(([^)]+)\)")


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _preprocess_expression(expr: str) -> str:
    """Replace Talend StringHandling calls with plain Python equivalents.

    Handles ``StringHandling.SPACE(n)`` → ``" " * n`` (as a repr'd string)
    and ``StringHandling.LEN(s)`` → ``len(s)`` so the result can be passed
    to a standard Python ``eval``.

    Args:
        expr: Raw expression string from the values config.

    Returns:
        Expression string with StringHandling calls expanded.
    """
    def _space_repl(m: re.Match) -> str:
        arg = m.group(1).strip()
        try:
            n = int(eval(arg, {"__builtins__": {}}))  # safe: numeric-literal only  # noqa: S307
            return repr(" " * n)
        except Exception:
            return repr("")

    def _len_repl(m: re.Match) -> str:
        arg = m.group(1).strip()
        # String literal -- return the length directly as a numeric literal.
        if (arg.startswith('"') and arg.endswith('"')) or (
            arg.startswith("'") and arg.endswith("'")
        ):
            return str(len(arg[1:-1]))
        return f"len({arg})"

    expr = _RE_SH_SPACE.sub(_space_repl, expr)
    expr = _RE_SH_LEN.sub(_len_repl, expr)
    return expr


def _eval_expr(
    expr: str,
    row_idx: int,
    col: str,
    java_bridge: Any,
    global_map: Any,
    component_id: str,
) -> Any:
    """Evaluate a single column expression for one row.

    Evaluation order:
      1. ``{{java}}`` prefix  → Java bridge ``execute_one_time_expression``.
      2. StringHandling.SPACE / .LEN  → converted to Python equivalents.
      3. Restricted ``eval`` with ``random`` in namespace.
      4. ``SyntaxError``  → treat the value as a plain string literal.

    Args:
        expr:         Expression string (already context-resolved by BaseComponent).
        row_idx:      Current row index (for logging).
        col:          Column name (for logging).
        java_bridge:  Live JavaBridge instance or ``None``.
        global_map:   Engine GlobalMap instance or ``None``.
        component_id: Component ID (for logging / error messages).

    Returns:
        Evaluated value (any type).

    Raises:
        ExpressionError: If a ``{{java}}`` expression is encountered but the
                         Java bridge is unavailable.
    """
    # ---- 1. Java bridge path -----------------------------------------------
    if isinstance(expr, str) and expr.startswith("{{java}}"):
        java_expr = expr[len("{{java}}"):]
        if java_bridge is None:
            raise ExpressionError(
                f"[{component_id}] Java bridge required for expression in "
                f"column '{col}' at row {row_idx}: {java_expr!r}"
            )
        # Sync engine GlobalMap into the bridge before each call (same pattern
        # as java_component.py).
        if global_map:
            java_bridge.global_map.update(global_map._map)
        result = java_bridge.execute_one_time_expression(java_expr)
        # Py4J returns Java primitives/Strings as Python types automatically, but
        # compound Java objects (e.g. java.util.Date from TalendDate.getRandomDate)
        # arrive as JavaObject instances.
        #
        # For Date-like objects (anything that has a getTime() method returning
        # epoch milliseconds) we produce an ISO datetime string that
        # _parse_datetime_column can reliably parse via the Talend default format
        # chain.  For any other JavaObject we fall back to str().
        if not isinstance(result, (str, int, float, bool, type(None))):
            try:
                import datetime as _dt
                epoch_ms = result.getTime()  # java.util.Date.getTime() → long
                result = _dt.datetime.utcfromtimestamp(epoch_ms / 1000.0).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            except Exception:
                result = str(result)
        return result

    # ---- 2 & 3. Pre-process then eval Python expression --------------------
    processed = _preprocess_expression(expr)
    try:
        return eval(processed, _EVAL_GLOBALS)  # noqa: S307 -- restricted namespace
    except (SyntaxError, NameError):
        # Treat as a string literal.
        #
        # NameError is included here because BaseComponent resolves {{java}}
        # expressions *before* _process() runs, replacing them with their
        # computed string values (e.g. 'CK0nxM2A', 'company.com').  Those
        # plain strings look like Python identifiers when eval'd and raise
        # NameError — but they are valid result values, not broken expressions.
        stripped = processed.strip()
        if (stripped.startswith('"') and stripped.endswith('"')) or (
            stripped.startswith("'") and stripped.endswith("'")
        ):
            return stripped[1:-1]
        logger.debug(
            "[%s] row %d col '%s': eval fallback, returning as literal: %r",
            component_id,
            row_idx,
            col,
            stripped,
        )
        return stripped


# ---------------------------------------------------------------------------
# Component class
# ---------------------------------------------------------------------------


@REGISTRY.register("RowGenerator", "tRowGenerator")
class RowGenerator(BaseComponent):
    """tRowGenerator engine implementation.

    Source component.  Generates ``nb_rows`` rows where each column value is
    produced by evaluating the column's ``array`` expression.  Rows that
    raise an exception during expression evaluation are routed to the REJECT
    output.
    """

    # ------------------------------------------------------------------
    # Expression Resolution Override
    # ------------------------------------------------------------------

    def _resolve_java_expressions(self) -> None:
        """Skip bulk Java resolution for tRowGenerator.

        BaseComponent resolves all ``{{java}}`` expressions once before
        ``_process()`` runs.  For tRowGenerator that would make every row
        receive the same pre-resolved value (e.g. the same random string).
        By overriding this method with a no-op, all ``{{java}}`` prefixes
        survive intact into ``_process()``, where ``_eval_expr()`` re-fires
        each expression fresh on every row via
        ``java_bridge.execute_one_time_expression()``.

        Context-variable resolution (``${context.var}``) is still performed
        by the base ``_resolve_expressions()`` call chain — only the Java
        batch execution step is skipped here.
        """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate structural config before expression resolution (Rule 12).

        Only checks key presence and container shape.  ``nb_rows`` is
        intentionally NOT validated here because it can hold a context
        variable reference such as ``${context.row_count}``; numeric
        coercion is deferred to ``_process()``.

        Raises:
            ConfigurationError: If ``values`` is absent or not a list.
        """
        values = self.config.get("values")
        if values is None:
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'values'"
            )
        if not isinstance(values, list):
            raise ConfigurationError(
                f"[{self.id}] Config key 'values' must be a list, "
                f"got {type(values).__name__}"
            )

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict[str, Any]:
        """Generate rows and return them as a DataFrame.

        Args:
            input_data: Not used -- this is a source component.

        Returns:
            Dict with ``'main'`` key (accepted rows DataFrame) and
            ``'reject'`` key (rows that failed expression evaluation).

        Raises:
            ConfigurationError: If ``nb_rows`` cannot be coerced to a
                                 non-negative integer after resolution.
        """
        # ---- 1. Resolve nb_rows --------------------------------------------
        nb_rows_raw = self.config.get("nb_rows", "100")
        try:
            nb_rows = int(nb_rows_raw)
        except (TypeError, ValueError):
            raise ConfigurationError(
                f"[{self.id}] 'nb_rows' must resolve to an integer, "
                f"got {nb_rows_raw!r}"
            )
        if nb_rows < 0:
            raise ConfigurationError(
                f"[{self.id}] 'nb_rows' must be >= 0, got {nb_rows}"
            )

        # ---- 2. Column names and expressions --------------------------------
        values: list[dict] = self.config.get("values", [])
        columns: list[str] = [v.get("schema_column", "") for v in values]
        exprs: list[str] = [str(v.get("array", "")) for v in values]

        logger.info("[%s] generating %d rows × %d columns", self.id, nb_rows, len(columns))

        # ---- 3. Row generation loop ----------------------------------------
        data: list[dict] = []
        rejects: list[dict] = []

        for i in range(nb_rows):
            row: dict[str, Any] = {}
            reject_row = False

            for col, expr in zip(columns, exprs):
                try:
                    row[col] = _eval_expr(
                        expr,
                        i,
                        col,
                        self.java_bridge,
                        self.global_map,
                        self.id,
                    )
                except Exception as exc:
                    logger.error(
                        "[%s] row %d col '%s': expression error: %s",
                        self.id,
                        i,
                        col,
                        exc,
                    )
                    row[col] = None
                    reject_row = True

            if reject_row:
                rejects.append(row)
            else:
                data.append(row)

        # ---- 4. Build DataFrames -------------------------------------------
        main_df = pd.DataFrame(data, columns=columns)
        reject_df = pd.DataFrame(rejects, columns=columns)

        logger.info("[%s] done: %d accepted, %d rejected", self.id, len(data), len(rejects))

        # ---- 5. Stats (source semantics: rows_read = total attempted) ------
        self._update_stats(
            rows_read=nb_rows,
            rows_ok=len(data),
            rows_reject=len(rejects),
        )

        return {"main": main_df, "reject": reject_df}
