"""Converter for Talend tChangeFileEncoding -> v1 ChangeFileEncoding component."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tChangeFileEncoding")
class ChangeFileEncodingConverter(ComponentConverter):
    """Convert a Talend tChangeFileEncoding node into a v1 ChangeFileEncoding component.

    tChangeFileEncoding is a utility component that re-encodes a file from one
    character encoding to another.  It operates on file paths rather than data
    flow rows, so the schema is always empty.

    Talend parameter mapping:
        INFILE_NAME       -> infile           (str)
        OUTFILE_NAME      -> outfile          (str)
        USE_INENCODING    -> use_inencoding   (bool)
        INENCODING        -> inencoding       (str)
        ENCODING          -> outencoding      (str)
        BUFFERSIZE        -> buffer_size      (int, default 8192)
        CREATE            -> create           (bool)
    """

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # --- Extract config parameters ---
        infile = self._get_str(node, "INFILE_NAME")
        outfile = self._get_str(node, "OUTFILE_NAME")
        use_inencoding = self._get_bool(node, "USE_INENCODING")
        inencoding = self._get_str(node, "INENCODING")
        outencoding = self._get_str(node, "ENCODING")
        buffer_size = self._get_int(node, "BUFFERSIZE", 8192)
        create = self._get_bool(node, "CREATE")

        # --- Validation warnings ---
        if not infile:
            warnings.append("INFILE_NAME (infile) is empty")
        if not outfile:
            warnings.append("OUTFILE_NAME (outfile) is empty")
        if not outencoding:
            warnings.append("ENCODING (outencoding) is empty")
        if use_inencoding and not inencoding:
            warnings.append(
                "USE_INENCODING is true but INENCODING is empty"
            )

        # --- Build config dict ---
        config: Dict[str, Any] = {
            "infile": infile,
            "outfile": outfile,
            "use_inencoding": use_inencoding,
            "inencoding": inencoding,
            "outencoding": outencoding,
            "buffer_size": buffer_size,
            "create": create,
        }

        component = self._build_component_dict(
            node=node,
            type_name="ChangeFileEncoding",
            config=config,
            # Utility component — no data flow schema
            schema={"input": [], "output": []},
        )

        return ComponentResult(component=component, warnings=warnings)
