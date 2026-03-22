"""Converter for Talend tHashOutput component."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# Parameters to skip when copying from node.params to config — these are
# handled structurally (component id, etc.) and should not leak into config.
_SKIP_PARAMS = frozenset({"UNIQUE_NAME"})


@REGISTRY.register("tHashOutput")
class HashOutputConverter(ComponentConverter):
    """Convert a Talend tHashOutput node into a v1 HashOutput component.

    tHashOutput stores incoming data in an in-memory hash structure so that
    downstream components (typically tHashInput) can look up rows by key.

    The old complex_converter copies *every* element parameter into config
    (converting string booleans) because tHashOutput has no mandatory,
    well-defined parameter set.  This converter follows the same approach:
    all parameters from ``node.params`` (except ``UNIQUE_NAME``) are
    forwarded into the v1 config, with string booleans normalised to real
    ``bool`` values and surrounding quotes stripped from string values.

    Schema is passthrough: input equals output.
    """

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        config: Dict[str, Any] = {}
        for key, value in node.params.items():
            if key in _SKIP_PARAMS:
                continue
            config[key] = self._normalise_value(value)

        schema_cols = self._parse_schema(node)

        component = self._build_component_dict(
            node=node,
            type_name="HashOutput",
            config=config,
            schema={"input": schema_cols, "output": schema_cols},
        )

        return ComponentResult(component=component, warnings=warnings)

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _normalise_value(value: Any) -> Any:
        """Normalise a raw parameter value.

        * String booleans (``"true"`` / ``"false"``) become real ``bool``.
        * Surrounding double-quotes are stripped from plain strings.
        * Everything else is returned as-is.
        """
        if isinstance(value, str):
            if value.lower() in ("true", "false"):
                return value.lower() == "true"
            if value.startswith('"') and value.endswith('"') and len(value) >= 2:
                return value[1:-1]
        return value
