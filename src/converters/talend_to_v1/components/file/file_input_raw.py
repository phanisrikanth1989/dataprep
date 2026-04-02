"""Converter for tFileInputRaw -> FileInputRaw."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileInputRaw")
class FileInputRawConverter(ComponentConverter):
    """Convert a Talend tFileInputRaw node to v1 FileInputRaw."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        config: Dict[str, Any] = {
            # Core params
            "filename": self._get_str(node, "FILENAME"),
            "as_string": self._get_bool(node, "AS_STRING", True),
            "as_bytearray": self._get_bool(node, "AS_BYTEARRAY", False),
            "as_inputstream": self._get_bool(node, "AS_INPUTSTREAM", False),
            "encoding": self._get_str(node, "ENCODING", "ISO-8859-15"),
            "die_on_error": self._get_bool(node, "DIE_ON_ERROR", False),
            # Metadata
            "tstatcatcher_stats": self._get_bool(node, "TSTATCATCHER_STATS", False),
            "label": self._get_str(node, "LABEL"),
        }

        # Warn when filename is empty — it is mandatory in Talend
        if not config["filename"]:
            warnings.append("FILENAME is empty — this is a required parameter")

        # Engine-gap warning: stream mode
        if config["as_inputstream"]:
            warnings.append(
                "AS_INPUTSTREAM=true: engine does not support streaming cursors; "
                "file will be fully loaded into memory as a bytearray"
            )

        component = self._build_component_dict(
            node=node,
            type_name="FileInputRaw",
            config=config,
            schema={"input": [], "output": self._parse_schema(node)},
        )

        return ComponentResult(component=component, warnings=warnings)
