"""Converter for Talend tFileArchive component.

Compresses files or directories into archive formats (ZIP, GZIP, TAR).

Config mapping (17 params + framework):
  SOURCE           -> source           (str, default "")
  SOURCE_FILE      -> source_file      (str, default "")
  SUB_DIRECTROY    -> sub_directroy    (bool, default True)   # Talend typo: no second I
  TARGET           -> target           (str, default "")
  MKDIR            -> mkdir            (bool, default False)
  ARCHIVE_FORMAT   -> archive_format   (str, default "ZIP")
  LEVEL            -> level            (str, default "4")
  ALL_FILES        -> all_files        (bool, default True)
  MASK             -> mask             (list, TABLE with FILEMASK entries)
  ENCODING         -> encoding         (str, default "ISO-8859-15")
  OVERWRITE        -> overwrite        (bool, default True)
  ENCRYPT_FILES    -> encrypt_files    (bool, default False)
  ENCRYPT_METHOD   -> encrypt_method   (str, default "ZIP4J_STANDARD")
  AES_KEY_STRENGTH -> aes_key_strength (str, default "AES256")
  PASSWORD         -> password         (str, always empty -- cleared for security)
  ZIP64_MODE       -> zip64_mode       (str, default "ASNEEDED")
  USE_SYNC_FLUSH   -> use_sync_flush   (bool, default False)  # advanced
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# TABLE parser functions
# ------------------------------------------------------------------
def _parse_mask(raw: Any) -> List[str]:
    """Parse MASK TABLE into list of mask pattern strings.

    Each entry has elementRef=FILEMASK with a quoted pattern value.
    Stride-1: one elementRef per row.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[str] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        ref = entry.get("elementRef", "")
        val = entry.get("value", "")
        if ref == "FILEMASK":
            result.append(val.strip('"'))
    return result


@REGISTRY.register("tFileArchive")
class FileArchiveConverter(ComponentConverter):
    """Convert Talend tFileArchive to v1 engine config."""

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
        config["source"] = self._get_str(node, "SOURCE", "")
        config["source_file"] = self._get_str(node, "SOURCE_FILE", "")
        config["sub_directroy"] = self._get_bool(node, "SUB_DIRECTROY", True)  # Talend typo preserved
        config["target"] = self._get_str(node, "TARGET", "")
        config["mkdir"] = self._get_bool(node, "MKDIR", False)

        # ---- 2. CLOSED_LIST parameters ----
        config["archive_format"] = self._get_str(node, "ARCHIVE_FORMAT", "ZIP")
        config["level"] = self._get_str(node, "LEVEL", "4")

        # ---- 3. File selection ----
        config["all_files"] = self._get_bool(node, "ALL_FILES", True)

        # ---- 4. TABLE parameters ----
        raw_mask = node.params.get("MASK", [])
        config["mask"] = _parse_mask(raw_mask)

        # ---- 5. Encoding ----
        config["encoding"] = self._get_str(node, "ENCODING", "ISO-8859-15")

        # ---- 6. Overwrite / encryption ----
        config["overwrite"] = self._get_bool(node, "OVERWRITE", True)
        config["encrypt_files"] = self._get_bool(node, "ENCRYPT_FILES", False)
        config["encrypt_method"] = self._get_str(node, "ENCRYPT_METHOD", "ZIP4J_STANDARD")
        config["aes_key_strength"] = self._get_str(node, "AES_KEY_STRENGTH", "AES256")
        config["password"] = ""  # Always empty -- never carry passwords into JSON
        config["zip64_mode"] = self._get_str(node, "ZIP64_MODE", "ASNEEDED")

        # ---- 7. Advanced parameters ----
        config["use_sync_flush"] = self._get_bool(node, "USE_SYNC_FLUSH", False)

        # ---- 8. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 9. Schema ----
        # Utility component -- no data flow schema
        schema = {"input": [], "output": []}

        # ---- 10. Engine gap needs_review entries ----
        # Engine reads 'include_subdirectories' but converter outputs 'sub_directroy' per _java.xml
        needs_review.append({
            "issue": "Engine reads 'include_subdirectories' but converter outputs 'sub_directroy' per _java.xml param name SUB_DIRECTROY",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine reads 'compression_level' but converter outputs 'level' per _java.xml
        needs_review.append({
            "issue": "Engine reads 'compression_level' (int) but converter outputs 'level' (str) per _java.xml param name LEVEL",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine default for include_subdirectories is True, _java.xml SUB_DIRECTROY default is True (matches)
        # Engine default for compression_level is 4, _java.xml LEVEL default is "4" (matches as value)
        # Engine default for encoding is not read -- engine_gap
        needs_review.append({
            "issue": "Engine does not read 'encoding' config key -- archive charset not configurable in engine",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine does not read mask, encrypt_files, encrypt_method, aes_key_strength, password, zip64_mode, use_sync_flush
        needs_review.append({
            "issue": "Engine does not read 'mask' config key -- file filtering not supported in engine",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        needs_review.append({
            "issue": "Engine does not read 'encrypt_files'/'encrypt_method'/'aes_key_strength'/'password' -- encryption not supported in engine",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        needs_review.append({
            "issue": "Engine does not read 'zip64_mode' config key -- uses Python zipfile default (allowZip64=True)",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        needs_review.append({
            "issue": "Engine does not read 'use_sync_flush' config key -- sync flush for gzip/tar.gz not supported",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        needs_review.append({
            "issue": "Engine does not read 'mkdir' config key -- engine auto-creates target directory unconditionally",
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 11. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="FileArchiveComponent",
            config=config,
            schema=schema,
        )

        # ---- 12. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
