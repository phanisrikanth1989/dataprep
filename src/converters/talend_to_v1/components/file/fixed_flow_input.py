"""Converter for tFixedFlowInput -> FixedFlowInputComponent.

tFixedFlowInput is a Talend source component that generates fixed rows of data.
It supports three modes:
  - Single mode (USE_SINGLEMODE): uses a VALUES table mapping column names to values.
  - Inline content mode (USE_INLINECONTENT): parses inline text using row/field separators.
  - Inline table mode (USE_INTABLE): uses an INTABLE table parameter.

The converter replicates Talend's row-generation logic, producing a ``rows`` list
in the config where each row is a dict mapping column names to their values.
"""
import logging
from typing import Any, Dict, List

from ...expression_converter import ExpressionConverter
from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFixedFlowInput")
class FixedFlowInputConverter(ComponentConverter):
    """Convert a Talend tFixedFlowInput node to v1 FixedFlowInputComponent."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # Basic configuration
        nb_rows = self._get_int(node, "NB_ROWS", 1)
        connection_format = self._get_str(node, "CONNECTION_FORMAT", "row")

        # Mode flags
        use_singlemode = self._get_bool(node, "USE_SINGLEMODE", True)
        use_intable = self._get_bool(node, "USE_INTABLE", False)
        use_inlinecontent = self._get_bool(node, "USE_INLINECONTENT", False)

        # Inline content parameters — unescape \n, \t etc. from XML-encoded values
        row_separator = self._get_str(node, "ROWSEPARATOR", "\n").encode().decode("unicode_escape")
        field_separator = self._get_str(node, "FIELDSEPARATOR", ";").encode().decode("unicode_escape")
        inline_content = self._get_str(node, "INLINECONTENT", "")

        # Schema columns from FLOW metadata
        schema_columns = self._parse_schema(node, "FLOW")

        # Parse VALUES table for single mode
        values_config: Dict[str, Any] = {}
        if use_singlemode:
            values_config = self._parse_values_table(node)

        if use_intable:
            warnings.append(
                "USE_INTABLE mode detected — INTABLE table parsing is not yet "
                "implemented; null rows will be generated"
            )

        # Generate rows based on the active mode
        rows = self._generate_rows(
            nb_rows=nb_rows,
            use_singlemode=use_singlemode,
            use_inlinecontent=use_inlinecontent,
            use_intable=use_intable,
            schema_columns=schema_columns,
            values_config=values_config,
            inline_content=inline_content,
            row_separator=row_separator,
            field_separator=field_separator,
        )

        config: Dict[str, Any] = {
            "nb_rows": nb_rows,
            "connection_format": connection_format,
            "use_singlemode": use_singlemode,
            "use_intable": use_intable,
            "use_inlinecontent": use_inlinecontent,
            "row_separator": row_separator,
            "field_separator": field_separator,
            "inline_content": inline_content,
            "schema": schema_columns,
            "values_config": values_config,
            "rows": rows,
        }

        component = self._build_component_dict(
            node=node,
            type_name="FixedFlowInputComponent",
            config=config,
            schema={"input": [], "output": schema_columns},
        )

        return ComponentResult(component=component, warnings=warnings)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_values_table(node: TalendNode) -> Dict[str, str]:
        """Parse the VALUES TABLE param into a {column_name: value} mapping.

        The XmlParser stores TABLE params as a list of ``{elementRef, value}``
        dicts.  For VALUES the entries come in pairs:
        ``SCHEMA_COLUMN`` followed by ``VALUE``.
        """
        values_config: Dict[str, str] = {}
        raw_values = node.params.get("VALUES", [])
        if not isinstance(raw_values, list):
            return values_config

        column_name = None
        for entry in raw_values:
            ref = entry.get("elementRef", "")
            raw_val = entry.get("value", "")
            val = raw_val.strip('"')

            if ref == "SCHEMA_COLUMN":
                column_name = val
            elif ref == "VALUE" and column_name:
                # Handle context variables and Java expressions
                if val.startswith("context."):
                    val = "${" + val + "}"
                elif val and not raw_val.startswith('"'):
                    # Only mark as Java expression if the raw value was NOT quoted
                    # (quoted values are string literals, not expressions)
                    val = ExpressionConverter.mark_java_expression(val)
                values_config[column_name] = val
                column_name = None

        return values_config

    @staticmethod
    def _generate_rows(
        *,
        nb_rows: int,
        use_singlemode: bool,
        use_inlinecontent: bool,
        use_intable: bool,
        schema_columns: List[Dict[str, Any]],
        values_config: Dict[str, str],
        inline_content: str,
        row_separator: str,
        field_separator: str,
    ) -> List[Dict[str, Any]]:
        """Generate the ``rows`` list that mirrors Talend runtime behaviour."""
        rows: List[Dict[str, Any]] = []

        for row_idx in range(nb_rows):
            if use_singlemode:
                # Single mode: each row copies values from VALUES config
                row = {}
                for col in schema_columns:
                    col_name = col["name"]
                    row[col_name] = values_config.get(col_name, None)
                rows.append(row)

            elif use_inlinecontent:
                # Inline content mode: split content by row/field separators
                if inline_content:
                    content_rows = inline_content.split(row_separator)
                    if row_idx < len(content_rows):
                        field_values = content_rows[row_idx].split(field_separator)
                        row = {}
                        for col_idx, col in enumerate(schema_columns):
                            if col_idx < len(field_values):
                                row[col["name"]] = field_values[col_idx]
                            else:
                                row[col["name"]] = None
                        rows.append(row)

            elif use_intable:
                # Inline table mode: placeholder (INTABLE parsing TBD)
                row = {col["name"]: None for col in schema_columns}
                rows.append(row)

        return rows
