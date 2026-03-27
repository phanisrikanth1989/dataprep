"""Converter for Talend tFileArchive -> v1 FileArchive component.

Maps tFileArchive parameters to a v1 FileArchive config:
  SOURCE            -> source
  TARGET            -> target
  ARCHIVE_FORMAT    -> archive_format  (default "zip")
  SUB_DIRECTORY     -> include_subdirectories (bool)
  OVERWRITE         -> overwrite (bool, default True)
  LEVEL             -> compression_level (str enum, default "Normal")
  DIE_ON_ERROR      -> die_on_error (bool, default False)
  SOURCE_FILE       -> source_file (str)
  CREATE_DIRECTORY  -> create_directory (bool)
  ALL_FILES         -> all_files (bool, default True)
  FILEMASK          -> filemask (str)
  ENCODING          -> encoding (str)
  ENCRYPT_FILES     -> encrypt_files (bool)
  ENCRYPT_METHOD    -> encrypt_method (str)
  AES_KEY_STRENGTH  -> aes_key_strength (str)
  PASSWORD          -> password (str)
  ZIP64_MODE        -> zip64_mode (str)
  USE_SYNC_FLUSH    -> use_sync_flush (bool)
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool)
  LABEL             -> label (str)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileArchive")
class FileArchiveConverter(ComponentConverter):
    """Convert a Talend tFileArchive node into a v1 FileArchive component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # --- Extract config parameters ---
        source = self._get_str(node, "SOURCE")
        target = self._get_str(node, "TARGET")
        archive_format = self._get_str(node, "ARCHIVE_FORMAT", default="zip")
        include_subdirectories = self._get_bool(node, "SUB_DIRECTORY")
        overwrite = self._get_bool(node, "OVERWRITE", True)
        compression_level = self._get_str(node, "LEVEL", default="Normal")
        die_on_error = self._get_bool(node, "DIE_ON_ERROR", False)

        # --- Validation warnings ---
        if not source:
            warnings.append("SOURCE is empty — this is a required parameter")
        if not target:
            warnings.append("TARGET is empty — this is a required parameter")

        # --- Build config dict ---
        config: Dict[str, Any] = {
            "source": source,
            "target": target,
            "archive_format": archive_format,
            "include_subdirectories": include_subdirectories,
            "overwrite": overwrite,
            "compression_level": compression_level,
            "die_on_error": die_on_error,
            # New params
            "source_file": self._get_str(node, "SOURCE_FILE"),
            "create_directory": self._get_bool(node, "CREATE_DIRECTORY", False),
            "all_files": self._get_bool(node, "ALL_FILES", True),
            "filemask": self._get_str(node, "FILEMASK"),
            "encoding": self._get_str(node, "ENCODING"),
            "encrypt_files": self._get_bool(node, "ENCRYPT_FILES", False),
            "encrypt_method": self._get_str(node, "ENCRYPT_METHOD"),
            "aes_key_strength": self._get_str(node, "AES_KEY_STRENGTH"),
            "password": self._get_str(node, "PASSWORD"),
            "zip64_mode": self._get_str(node, "ZIP64_MODE"),
            "use_sync_flush": self._get_bool(node, "USE_SYNC_FLUSH", False),
            # Metadata
            "tstatcatcher_stats": self._get_bool(node, "TSTATCATCHER_STATS", False),
            "label": self._get_str(node, "LABEL"),
        }

        # --- Engine-gap warnings ---
        if config["archive_format"] != "zip":
            warnings.append(
                f"ARCHIVE_FORMAT={config['archive_format']}: engine only "
                "supports zip format"
            )
        if config["encrypt_files"]:
            warnings.append(
                "ENCRYPT_FILES=true: engine does not support archive encryption"
            )
        if config["filemask"]:
            warnings.append(
                "FILEMASK set: engine does not support file filtering in archives"
            )
        if config["use_sync_flush"]:
            warnings.append(
                "USE_SYNC_FLUSH=true: engine does not support sync flush "
                "for gzip/tar.gz"
            )
        if config["zip64_mode"] and config["zip64_mode"] != "ASNEEDED":
            warnings.append(
                f"ZIP64_MODE={config['zip64_mode']}: engine uses Python "
                "zipfile default (allowZip64=True)"
            )
        if config["create_directory"]:
            warnings.append(
                "CREATE_DIRECTORY=true: engine does not auto-create target "
                "archive directory"
            )

        component = self._build_component_dict(
            node=node,
            type_name="FileArchiveComponent",
            config=config,
            # Utility component — no data flow schema
            schema={"input": [], "output": []},
        )

        return ComponentResult(component=component, warnings=warnings)
