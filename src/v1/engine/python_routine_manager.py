"""
Python Routine Manager - Loads and manages custom Python routines

This module provides functionality to discover, load, and access custom Python
routines that can be used in ETL transformations. Similar to Java routines in
Talend, but for pure Python execution.

Example:
    manager = PythonRoutineManager('src/python_routines')
    routines = manager.get_all_routines()
    # Use in expressions: routines.DemoRoutine.greet('World')
"""

import os
import sys
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class PythonRoutineManager:
    """
    Manages loading and access to custom Python routines

    Discovers .py files in a specified directory and loads them as modules,
    making their functions available for use in ETL expressions.

    Attributes:
        routines_dir: Directory containing Python routine files
        routines: Dictionary mapping routine names to loaded modules
    """

    def __init__(self, routines_dir: str):
        """
        Initialize the routine manager

        Args:
            routines_dir: Path to directory containing Python routine files
        """
        self.routines_dir = routines_dir
        self.routines: Dict[str, Any] = {}

        # Ensure directory exists
        if not os.path.exists(routines_dir):
            logger.warning(f"Python routines directory not found: {routines_dir}")
            return

        # Load all routines
        self._load_routines()

    def _load_routines(self):
        """
        Discover and load all Python routines from the routines directory

        Scans for .py files (excluding __init__.py), imports them as modules,
        and stores them for later access.
        """
        routines_path = Path(self.routines_dir)

        if not routines_path.exists():
            logger.warning(f"Routines directory does not exist: {self.routines_dir}")
            return

        # Find all .py files
        routine_files = list(routines_path.glob("*.py"))

        logger.info(f"Discovering Python routines in {self.routines_dir}...")

        for routine_file in routine_files:
            # Skip __init__.py and private files
            if routine_file.name.startswith('_'):
                continue

            routine_name = routine_file.stem

            try:
                # Load the module
                module = self._load_module(routine_file)

                # Store with capitalized name (e.g., demo_routine -> DemoRoutine)
                # to match Java convention
                class_name = self._to_class_name(routine_name)
                self.routines[class_name] = module

                logger.info(f"\u2705 Loaded: {class_name}")

            except Exception as e:
                logger.error(f"\u274c Failed to load {routine_name}: {e}")

    def _load_module(self, file_path: Path):
        """
        Load a Python module from a file path

        Args:
            file_path: Path to the Python file

        Returns:
            Loaded module object
        """
        module_name = file_path.stem

        # Create module spec
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module from {file_path}")

        # Load the module
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        return module

    def _to_class_name(self, snake_case: str) -> str:
        """
        Convert snake_case filename to ClassName

        Args:
            snake_case: Filename in snake_case (e.g., 'demo_routine')

        Returns:
            Class name in CamelCase (e.g., 'DemoRoutine')
        """
        parts = snake_case.split('_')
        return ''.join(word.capitalize() for word in parts)

    def get_routine(self, name: str) -> Optional[Any]:
        """
        Get a routine module by name

        Args:
            name: Name of the routine (e.g., 'DemoRoutine')

        Returns:
            Module object if found, None otherwise
        """
        return self.routines.get(name)

    def get_all_routines(self) -> Dict[str, Any]:
        """
        Get all loaded routines

        Returns:
            Dictionary mapping routine names to module objects
        """
        return self.routines.copy()

    def reload_routine(self, name: str):
        """
        Reload a specific routine module

        Useful for development when routine code changes.

        Args:
            name: Name of the routine to reload
        """
        if name not in self.routines:
            logger.warning(f"Routine {name} not found, cannot reload")
            return

        try:
            module = self.routines[name]
            importlib.reload(module)
            logger.info(f"\u2705 Reloaded routine: {name}")
        except Exception as e:
            logger.error(f"\u274c Failed to reload {name}: {e}")

    def list_routines(self) -> list:
        """
        Get list of all loaded routine names

        Returns:
            List of routine names
        """
        return list(self.routines.keys())
