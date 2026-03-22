"""Converter for Talend tJoin component.

The JOIN_KEY TABLE parameter contains flat {elementRef, value} pairs where
LEFT_COLUMN/INPUT_COLUMN entries map to 'main' and RIGHT_COLUMN/LOOKUP_COLUMN
entries map to 'lookup'.  Each LEFT+RIGHT pair is grouped into a single
{main, lookup} dict.
"""
import logging
from typing import Any, Dict, List, Optional

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tJoin")
class JoinConverter(ComponentConverter):
    """Convert a Talend tJoin node into a v1 Join component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # ------------------------------------------------------------------
        # Parse JOIN_KEY table
        # ------------------------------------------------------------------
        join_keys: List[Dict[str, str]] = []
        raw_keys = self._get_param(node, "JOIN_KEY", [])

        if isinstance(raw_keys, list):
            main_col: Optional[str] = None
            lookup_col: Optional[str] = None

            for entry in raw_keys:
                ref = entry.get("elementRef", "")
                val = entry.get("value", "").strip('"')

                if ref in ("LEFT_COLUMN", "INPUT_COLUMN"):
                    # If we already had a main without a lookup, emit warning
                    if main_col is not None:
                        warnings.append(
                            f"LEFT_COLUMN '{main_col}' has no matching "
                            "RIGHT_COLUMN — skipped"
                        )
                    main_col = val
                elif ref in ("RIGHT_COLUMN", "LOOKUP_COLUMN"):
                    if main_col is None:
                        warnings.append(
                            f"RIGHT_COLUMN '{val}' has no preceding "
                            "LEFT_COLUMN — skipped"
                        )
                    else:
                        lookup_col = val

                # When we have both, emit the pair and reset
                if main_col is not None and lookup_col is not None:
                    join_keys.append({"main": main_col, "lookup": lookup_col})
                    main_col = None
                    lookup_col = None

            # Handle trailing unpaired entries
            if main_col is not None and lookup_col is None:
                warnings.append(
                    f"LEFT_COLUMN '{main_col}' has no matching "
                    "RIGHT_COLUMN — skipped"
                )
            if lookup_col is not None and main_col is None:
                warnings.append(
                    f"RIGHT_COLUMN '{lookup_col}' has no preceding "
                    "LEFT_COLUMN — skipped"
                )
        else:
            warnings.append(
                "JOIN_KEY param is not a list — expected TABLE structure"
            )

        if not join_keys:
            warnings.append(
                "No join keys defined — component will have no join criteria"
            )

        # ------------------------------------------------------------------
        # Other parameters
        # ------------------------------------------------------------------
        use_inner_join = self._get_bool(node, "USE_INNER_JOIN", default=False)
        case_sensitive = self._get_bool(node, "CASE_SENSITIVE", default=True)
        die_on_error = self._get_bool(node, "DIE_ON_ERROR", default=False)

        config: Dict[str, Any] = {
            "join_keys": join_keys,
            "use_inner_join": use_inner_join,
            "case_sensitive": case_sensitive,
            "die_on_error": die_on_error,
        }

        # ------------------------------------------------------------------
        # Schema: transform component passes schema through
        # ------------------------------------------------------------------
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        component = self._build_component_dict(
            node=node,
            type_name="Join",
            config=config,
            schema=schema,
        )
        return ComponentResult(component=component, warnings=warnings)
