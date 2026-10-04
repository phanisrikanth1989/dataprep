"""
Base Component for v2 Engine.

Defines the abstract base class and specializations for all v2 components.

Hierarchy:
  Component(ABC)          -- abstract root with apply(), validate(), resolve_context()
    SourceComponent       -- _read() -> LazyFrame; produce() wraps with schema validation
    SinkComponent         -- consume(inputs) -> None  (is_barrier=True)
    TransformComponent    -- pass-through (override apply())
    PythonComponent       -- Python UDF wrapper (is_barrier=True)
    UtilityComponent      -- side-effect components (is_barrier=True), e.g. ContextLoad
"""
from abc import ABC
from typing import Any, ClassVar, Dict, List, Optional
import logging
import re

import polars as pl

from .capabilities import FeatureSupport

logger = logging.getLogger(__name__)


class Component(ABC):
    """
    Abstract base for all v2 components.

    Subclasses override apply() which operates on
    Dict[str, pl.LazyFrame] -> Dict[str, pl.LazyFrame].
    """

    SUPPORTED_FEATURES: ClassVar[Dict[str, FeatureSupport]] = {}

    def __init__(
        self,
        component_id: str,
        config: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        routine_registry: Optional[Any] = None,
        streaming: bool = False,
    ):
        self.component_id = component_id
        self.config = config
        self.context = context or {}
        self.routine_registry = routine_registry
        self.streaming = streaming
        self._collect_kwargs: Dict[str, Any] = (
            {"engine": "streaming"} if streaming else {}
        )
        self._post_init()

    def _post_init(self):
        """Override to initialize subclass-specific state.

        Called automatically at the end of __init__. Subclasses should
        override this instead of __init__ so that base class constructor
        changes never break them.
        """
        pass

    def apply(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        """
        Core processing method -- override in subclasses.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement apply()"
        )

    @property
    def is_barrier(self) -> bool:
        """Whether this component forces materialization."""
        return False

    def validate(self) -> List[str]:
        """Validate component configuration. Override for custom checks."""
        return []

    def resolve_context(self, value: Any) -> Any:
        """
        Resolve ${context.varname} placeholders in a string value.

        Non-string values pass through unchanged.
        """
        if not isinstance(value, str) or "${context." not in value:
            return value

        def _replace(match):
            var_name = match.group(1)
            if var_name in self.context:
                return str(self.context[var_name])
            return match.group(0)

        return re.sub(r'\$\{context\.(\w+)\}', _replace, value)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.component_id})"


class SourceComponent(Component):
    """
    Base for source components (no inputs, produces data).

    Subclasses implement _read() -> pl.LazyFrame (or pl.DataFrame).
    The base class wraps _read() with optional schema validation
    controlled by die_on_error.

    When die_on_error is false and a schema is defined, the base class:
    1. Collects the LazyFrame (barrier)
    2. Casts columns with strict=False (failures -> null)
    3. Detects new nulls (cast failures vs pre-existing nulls)
    4. Splits into main (good rows) and reject (bad rows with _error_message)
    5. Re-wraps as LazyFrame for downstream
    """

    def apply(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        """Sources ignore inputs and call produce()."""
        return self.produce()

    def produce(self) -> Dict[str, pl.LazyFrame]:
        """Read data and optionally validate schema."""
        data = self._read()
        die_on_error = self.config.get("die_on_error", True)
        schema_config = self.config.get("schema", [])

        if die_on_error or not schema_config:
            # Default: fully lazy, zero overhead
            if isinstance(data, pl.DataFrame):
                data = data.lazy()
            return {"main": data}

        # die_on_error=false with schema: validate types
        return self._validate_schema(data, schema_config)

    def _read(self) -> pl.LazyFrame:
        """Override to read raw data. Return LazyFrame or DataFrame."""
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _read()"
        )

    def _validate_schema(
        self,
        data,
        schema_config: list,
    ) -> Dict[str, pl.LazyFrame]:
        """Validate data against schema, splitting good/bad rows."""
        from .file.schema_types import TYPE_MAPPING, DATE_TYPES

        # Collect to DataFrame for validation
        if isinstance(data, pl.LazyFrame):
            df = data.collect(**self._collect_kwargs)
        else:
            df = data

        # Identify columns that need type casting (non-string targets)
        cast_columns = []
        for col_def in schema_config:
            col_name = col_def.get("name")
            col_type = col_def.get("type", "string").lower()
            target_type = TYPE_MAPPING.get(col_type, pl.Utf8)
            if col_name in df.columns and target_type != pl.Utf8:
                cast_columns.append((col_name, target_type, col_def))

        if not cast_columns:
            # No non-string columns to validate — all string types
            return {"main": df.lazy()}

        # Record pre-cast null masks
        pre_null_masks = {}
        for col_name, *_ in cast_columns:
            pre_null_masks[col_name] = df[col_name].is_null()

        # Cast with strict=False (failures -> null)
        # Date/datetime columns use str.to_date/str.to_datetime with format
        cast_exprs = []
        for col_name, target_type, col_def in cast_columns:
            col_type = col_def.get("type", "string").lower()
            if col_type in DATE_TYPES:
                fmt = col_def.get("date_pattern")
                if col_type in ("date", "id_Date"):
                    cast_exprs.append(
                        pl.col(col_name).str.to_date(fmt, strict=False).alias(col_name)
                    )
                else:  # datetime
                    cast_exprs.append(
                        pl.col(col_name).str.to_datetime(fmt, strict=False).alias(col_name)
                    )
            else:
                cast_exprs.append(
                    pl.col(col_name).cast(target_type, strict=False).alias(col_name)
                )
        df_cast = df.with_columns(cast_exprs)

        # Detect new nulls (null after cast AND not null before = cast failure)
        error_mask = pl.Series("_has_error", [False] * len(df_cast))
        for col_name, *_ in cast_columns:
            new_nulls = df_cast[col_name].is_null() & ~pre_null_masks[col_name]
            if new_nulls.any():
                error_mask = error_mask | new_nulls

        if not error_mask.any():
            # All rows valid
            return {"main": df_cast.lazy()}

        # Split good/bad
        good_df = df_cast.filter(~error_mask)
        bad_df = df.filter(error_mask)  # Use original (pre-cast) data for reject

        # Build error message per rejected row (only iterate error indices)
        error_indices = error_mask.arg_true()
        error_msgs = []
        for i in error_indices:
            failed_cols = []
            for col_name, target_type, _ in cast_columns:
                if df_cast[col_name].is_null()[i] and not pre_null_masks[col_name][i]:
                    failed_cols.append(f"{col_name} -> {target_type}")
            error_msgs.append(f"Schema cast failed: {', '.join(failed_cols)}")

        bad_df = bad_df.with_columns(
            pl.Series("_error_message", error_msgs)
        )

        result = {"main": good_df.lazy()}
        if len(bad_df) > 0:
            result["reject"] = bad_df.lazy()
        return result


class SinkComponent(Component):
    """
    Base for sink components (consumes data, always a barrier).

    Subclasses must implement consume(inputs) -> None.
    apply() delegates to consume() and returns empty dict.
    """

    @property
    def is_barrier(self) -> bool:
        return True

    def apply(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        """Sinks consume input and return empty output."""
        self.consume(inputs)
        return {}

    def consume(self, inputs: Dict[str, pl.LazyFrame]) -> None:
        """Override to consume input data."""
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement consume()"
        )

    def _validate_output_schema(self, df: pl.DataFrame) -> None:
        """Validate DataFrame against output schema config.

        Raises ValueError if column is missing or has wrong dtype.
        Only runs if config["schema"] is defined.
        """
        schema_config = self.config.get("schema", [])
        if not schema_config:
            return

        from .file.schema_types import TYPE_MAPPING

        errors = []
        for col_def in schema_config:
            col_name = col_def.get("name")
            col_type = col_def.get("type", "string").lower()
            expected_type = TYPE_MAPPING.get(col_type, pl.Utf8)

            if col_name not in df.columns:
                errors.append(f"column '{col_name}' not found in data")
                continue

            actual_type = df[col_name].dtype
            if actual_type != expected_type:
                errors.append(
                    f"column '{col_name}' expected {expected_type}, got {actual_type}"
                )

        if errors:
            raise ValueError(
                f"Sink schema validation failed: {'; '.join(errors)}"
            )


class TransformComponent(Component):
    """
    Base for transform components (LazyFrame in, LazyFrame out).

    Subclasses override apply(inputs) -> Dict[str, pl.LazyFrame].
    """
    pass


class PythonComponent(Component):
    """
    Base for Python UDF components (always a barrier).

    Python UDFs require materialization, so they force a collect().
    """

    @property
    def is_barrier(self) -> bool:
        return True


class UtilityComponent(Component):
    """
    Base for utility components that perform side effects (e.g. ContextLoad).

    Utility components modify execution context or perform control-flow
    operations rather than transforming data.  They are barriers because
    their side effects must complete before downstream components execute.
    """

    def apply(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Utility components return metadata dicts, not LazyFrames."""
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement apply()"
        )

    @property
    def is_barrier(self) -> bool:
        return True
