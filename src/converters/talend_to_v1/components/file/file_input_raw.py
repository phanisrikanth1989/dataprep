"""Converter for tFileInputRaw -> TFileInputRaw."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileInputRaw")
class FileInputRawConverter(ComponentConverter):
    """Convert a Talend tFileInputRaw node to v1 TFileInputRaw."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        config: Dict[str, Any] = {
            "filename": self._get_str(node, "FILENAME"),
            "as_string": self._get_bool(node, "AS_STRING", True),
            "encoding": self._get_str(node, "ENCODING", "UTF-8"),
            "die_on_error": self._get_bool(node, "DIE_ON_ERROR", False),
        }

        # Warn when filename is empty — it is mandatory in Talend
        if not config["filename"]:
            warnings.append("FILENAME is empty — this is a required parameter")

        component = self._build_component_dict(
            node=node,
            type_name="TFileInputRaw",
            config=config,
            schema={"input": [], "output": self._parse_schema(node)},
        )

        return ComponentResult(component=component, warnings=warnings)
