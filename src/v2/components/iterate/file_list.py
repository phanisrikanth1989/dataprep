"""FileList iterate component for V2 engine."""
import glob
import logging
import os
from typing import Any, Dict, List

import polars as pl

from ..base import PythonComponent
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("file_list", "iterate_file_list")
class FileList(PythonComponent):
    """
    Iterate over files in a directory.

    Returns iteration contexts -- one per file found.
    The engine runs downstream sub-pipeline once per iteration,
    injecting file info into context.

    Config:
        directory: str - Directory to scan (required)
        files: list - File masks [{"filemask": "*.csv"}] (default: [{"filemask": "*"}])
        include_subdirs: bool - Include subdirectories (default: False)
        list_mode: str - FILES, DIRECTORIES, or ALL (default: FILES)
        order_by: str - NOTHING, FILENAME, FILESIZE, MODIFIEDDATE (default: NOTHING)
        order_desc: bool - Descending sort (default: False)
        error: bool - Error if no files found (default: True)

    Iteration context variables (per file):
        {component_id}_CURRENT_FILE: filename
        {component_id}_CURRENT_FILEPATH: full path
        {component_id}_CURRENT_FILEDIRECTORY: directory
        {component_id}_CURRENT_FILEEXT: extension
        {component_id}_CURRENT_FILE_SIZE: size in bytes
    """

    def validate(self) -> List[str]:
        errors = []
        if "directory" not in self.config:
            errors.append("FileList requires 'directory' in config")
        return errors

    def apply(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        """
        Scan directory and return iteration contexts.

        Returns dict with "__iterations__" key containing list of
        context dicts (one per file found).
        """
        directory = self.resolve_context(self.config.get("directory", "."))
        directory = os.path.expanduser(os.path.expandvars(directory))

        list_mode = self.config.get("list_mode", "FILES").upper()
        include_subdirs = self.config.get("include_subdirs", False)
        error_if_no_file = self.config.get("error", True)
        order_by = self.config.get("order_by", "NOTHING").upper()
        order_desc = self.config.get("order_desc", False)

        # File masks
        file_masks = self.config.get("files", [{"filemask": "*"}])

        if not os.path.exists(directory):
            if error_if_no_file:
                raise FileNotFoundError(f"Directory not found: {directory}")
            return {"__iterations__": []}

        # Find matching files
        all_files = []
        for mask_config in file_masks:
            pattern = mask_config.get("filemask", "*") if isinstance(mask_config, dict) else str(mask_config)

            if include_subdirs:
                search_pattern = os.path.join(directory, "**", pattern)
                matched = glob.glob(search_pattern, recursive=True)
            else:
                search_pattern = os.path.join(directory, pattern)
                matched = glob.glob(search_pattern)

            for file_path in matched:
                if list_mode == "FILES" and not os.path.isfile(file_path):
                    continue
                elif list_mode == "DIRECTORIES" and not os.path.isdir(file_path):
                    continue

                file_info = self._get_file_info(file_path)
                if file_info not in all_files:
                    all_files.append(file_info)

        # Sort
        all_files = self._sort_files(all_files, order_by, order_desc)

        if not all_files and error_if_no_file:
            raise FileNotFoundError(f"No files matching patterns in {directory}")

        # Build iteration contexts
        iterations = []
        for file_info in all_files:
            ctx = {
                f"{self.component_id}_CURRENT_FILE": file_info["filename"],
                f"{self.component_id}_CURRENT_FILEPATH": file_info["filepath"],
                f"{self.component_id}_CURRENT_FILEDIRECTORY": file_info["directory"],
                f"{self.component_id}_CURRENT_FILEEXT": file_info["extension"],
                f"{self.component_id}_CURRENT_FILE_SIZE": file_info["size"],
            }
            iterations.append(ctx)

        logger.info(f"FileList found {len(iterations)} files in {directory}")

        return {"__iterations__": iterations}

    def _get_file_info(self, file_path: str) -> Dict[str, Any]:
        stat = os.stat(file_path)
        return {
            "filepath": file_path,
            "filename": os.path.basename(file_path),
            "directory": os.path.dirname(file_path),
            "extension": os.path.splitext(file_path)[1],
            "size": stat.st_size,
            "mtime": stat.st_mtime,
        }

    def _sort_files(self, files: List[Dict], order_by: str, reverse: bool) -> List[Dict]:
        if order_by == "NOTHING" or not files:
            return files
        key_map = {
            "FILENAME": lambda x: x["filename"],
            "FILESIZE": lambda x: x["size"],
            "MODIFIEDDATE": lambda x: x["mtime"],
        }
        key_func = key_map.get(order_by)
        if key_func:
            return sorted(files, key=key_func, reverse=reverse)
        return files
