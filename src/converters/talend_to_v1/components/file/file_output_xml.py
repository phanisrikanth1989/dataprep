"""Converter for Talend tAdvancedFileOutputXML component.

Writes data as XML output with configurable element structure defined by
ROOT, GROUP, and LOOP TABLE parameters. Supports DOM4J and Null generation
modes, file validation (DTD/XSL), split output, and advanced separators.

Config mapping (33 unique + 2 framework = 35 params total):
  FILENAME               -> filename               (str, default "")
  USESTREAM              -> usestream              (bool, default False)
  STREAMNAME             -> streamname             (str, default "outputStream")
  ROOT                   -> root                   (list/TABLE, stride-5: PATH/COLUMN/VALUE/ATTRIBUTE/ORDER)
  GROUP                  -> group                  (list/TABLE, stride-5: PATH/COLUMN/VALUE/ATTRIBUTE/ORDER)
  LOOP                   -> loop                   (list/TABLE, stride-5: PATH/COLUMN/VALUE/ATTRIBUTE/ORDER)
  MAP                    -> map                    (str, default "")
  MERGE                  -> merge                  (bool, default False)
  PRETTY_COMPACT         -> pretty_compact         (bool, default False)
  FILE_VALID             -> file_valid             (bool, default False)
  DTD_VALID              -> dtd_valid              (bool, default True) [RADIO]
  DTD_NAME               -> dtd_name               (str, default "Root")
  DTD_SYSTEMID           -> dtd_systemid           (str, default "Talend.dtd")
  XSL_VALID              -> xsl_valid              (bool, default False) [RADIO]
  XSL_TYPE               -> xsl_type               (str, default "text/xsl")
  XSL_HREF               -> xsl_href               (str, default "Talend.xsl")
  SPLIT                  -> split                  (bool, default False)
  SPLIT_EVERY            -> split_every            (str, default "1000")
  TRIM                   -> trim                   (bool, default False)
  CREATE                 -> create                 (bool, default True)
  CREATE_EMPTY_ELEMENT   -> create_empty_element   (bool, default True)
  ADD_EMPTY_ATTRIBUTE    -> add_empty_attribute    (bool, default False)
  ADD_UNMAPPED_ATTRIBUTE -> add_unmapped_attribute (bool, default False)
  ADD_DOCUMENT_AS_NODE   -> add_document_as_node   (bool, default False)
  OUTPUT_AS_XSD          -> output_as_xsd          (bool, default False)
  ADVANCED_SEPARATOR     -> advanced_separator     (bool, default False)
  THOUSANDS_SEPARATOR    -> thousands_separator    (str, default ",")
  DECIMAL_SEPARATOR      -> decimal_separator      (str, default ".")
  GENERATION_MODE        -> generation_mode        (str/CLOSED_LIST, default "DOM4J")
  ENCODING               -> encoding              (str, default "ISO-8859-15")
  DELETE_EMPTYFILE       -> delete_empty_file      (bool, default False)
  --- framework ---
  TSTATCATCHER_STATS     -> tstatcatcher_stats     (bool, default False)
  LABEL                  -> label                  (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# TABLE constants for ROOT/GROUP/LOOP (all share same 5-field structure)
# ------------------------------------------------------------------
_XML_TABLE_FIELDS = ("PATH", "COLUMN", "VALUE", "ATTRIBUTE", "ORDER")
_XML_TABLE_GROUP_SIZE = len(_XML_TABLE_FIELDS)


# ------------------------------------------------------------------
# TABLE parser function
# ------------------------------------------------------------------
def _parse_xml_table(raw: Any) -> List[Dict[str, Any]]:
    """Parse ROOT/GROUP/LOOP TABLE into list of dicts.

    Each group of 5 consecutive elementRef entries maps to one row:
      PATH      -> path      (str)
      COLUMN    -> column    (str)
      VALUE     -> value     (str)
      ATTRIBUTE -> attribute (str)
      ORDER     -> order     (str)

    Incomplete trailing groups (< 5 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, Any]] = []
    for i in range(0, len(raw), _XML_TABLE_GROUP_SIZE):
        group = raw[i: i + _XML_TABLE_GROUP_SIZE]
        if len(group) < _XML_TABLE_GROUP_SIZE:
            break
        row: Dict[str, Any] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            # Strip quotes -- XmlParser doesn't strip TABLE entry quotes
            if isinstance(val, str):
                val = val.strip('"')
            if ref == "PATH":
                row["path"] = val
            elif ref == "COLUMN":
                row["column"] = val
            elif ref == "VALUE":
                row["value"] = val
            elif ref == "ATTRIBUTE":
                row["attribute"] = val
            elif ref == "ORDER":
                row["order"] = val
        if row:
            result.append(row)
    return result


@REGISTRY.register("tAdvancedFileOutputXML")
class AdvancedFileOutputXmlConverter(ComponentConverter):
    """Convert Talend tAdvancedFileOutputXML to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters ----
        config: Dict[str, Any] = {}
        config["filename"] = self._get_str(node, "FILENAME", "")
        config["usestream"] = self._get_bool(node, "USESTREAM", False)
        config["streamname"] = self._get_str(node, "STREAMNAME", "outputStream")

        # ---- 2. TABLE parameters (ROOT, GROUP, LOOP) ----
        config["root"] = _parse_xml_table(node.params.get("ROOT", []))
        config["group"] = _parse_xml_table(node.params.get("GROUP", []))
        config["loop"] = _parse_xml_table(node.params.get("LOOP", []))

        # ---- 3. External map ----
        config["map"] = self._get_str(node, "MAP", "")

        # ---- 4. Output options ----
        config["merge"] = self._get_bool(node, "MERGE", False)
        config["pretty_compact"] = self._get_bool(node, "PRETTY_COMPACT", False)

        # ---- 5. Validation parameters ----
        config["file_valid"] = self._get_bool(node, "FILE_VALID", False)
        config["dtd_valid"] = self._get_bool(node, "DTD_VALID", True)  # RADIO, default True
        config["dtd_name"] = self._get_str(node, "DTD_NAME", "Root")
        config["dtd_systemid"] = self._get_str(node, "DTD_SYSTEMID", "Talend.dtd")
        config["xsl_valid"] = self._get_bool(node, "XSL_VALID", False)  # RADIO, default False
        config["xsl_type"] = self._get_str(node, "XSL_TYPE", "text/xsl")
        config["xsl_href"] = self._get_str(node, "XSL_HREF", "Talend.xsl")

        # ---- 6. Advanced parameters ----
        config["split"] = self._get_bool(node, "SPLIT", False)
        config["split_every"] = self._get_str(node, "SPLIT_EVERY", "1000")  # str for expression support
        config["trim"] = self._get_bool(node, "TRIM", False)
        config["create"] = self._get_bool(node, "CREATE", True)
        config["create_empty_element"] = self._get_bool(node, "CREATE_EMPTY_ELEMENT", True)
        config["add_empty_attribute"] = self._get_bool(node, "ADD_EMPTY_ATTRIBUTE", False)
        config["add_unmapped_attribute"] = self._get_bool(node, "ADD_UNMAPPED_ATTRIBUTE", False)
        config["add_document_as_node"] = self._get_bool(node, "ADD_DOCUMENT_AS_NODE", False)
        config["output_as_xsd"] = self._get_bool(node, "OUTPUT_AS_XSD", False)

        # ---- 7. Separator parameters ----
        config["advanced_separator"] = self._get_bool(node, "ADVANCED_SEPARATOR", False)
        config["thousands_separator"] = self._get_str(node, "THOUSANDS_SEPARATOR", ",")
        config["decimal_separator"] = self._get_str(node, "DECIMAL_SEPARATOR", ".")

        # ---- 8. Generation mode and encoding ----
        config["generation_mode"] = self._get_str(node, "GENERATION_MODE", "DOM4J")
        config["encoding"] = self._get_str(node, "ENCODING", "ISO-8859-15")  # per _java.xml
        config["delete_empty_file"] = self._get_bool(node, "DELETE_EMPTYFILE", False)

        # ---- 9. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 10. Schema (SINK: input populated, output empty) ----
        schema = {"input": self._parse_schema(node), "output": []}

        # ---- 11. Engine gap needs_review entries ----
        # Single consolidated needs_review per D-51 (no engine)
        needs_review.append({
            "issue": "No v1 engine implementation exists for tAdvancedFileOutputXML. All config keys are extracted for future engine support.",
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 12. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="tAdvancedFileOutputXML",  # D-43: no-engine uses Talend name
            config=config,
            schema=schema,
        )

        # ---- 13. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
