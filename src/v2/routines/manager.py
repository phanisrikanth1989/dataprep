"""
Python Routine Manager for v2 Engine.

High-performance routine loader and registry.
Loads Python modules ONCE and builds a flat function registry for O(1) lookup.

Performance optimizations:
- Single load at engine initialization
- Flat function registry (RoutineName.function → callable)
- No dynamic lookups during expression evaluation
- Cached function references
"""
import importlib.util
import inspect
import logging
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class RoutineRegistry:
    """
    Flat function registry for O(1) routine lookup.

    Maps "RoutineName.function_name" → callable for instant access.
    No nested lookups during expression evaluation.
    """

    __slots__ = ('_functions', '_routine_names', '_function_signatures')

    def __init__(self):
        # Flat registry: "RoutineName.func" → callable
        self._functions: Dict[str, Callable] = {}
        # Set of loaded routine names (for validation)
        self._routine_names: Set[str] = set()
        # Signatures for documentation/validation: "RoutineName.func" → (arg_names, defaults)
        self._function_signatures: Dict[str, Tuple[List[str], Dict[str, Any]]] = {}

    def register(
        self,
        routine_name: str,
        func_name: str,
        func: Callable,
        signature: Optional[Tuple[List[str], Dict[str, Any]]] = None
    ) -> None:
        """
        Register a function in the flat registry.

        Args:
            routine_name: Name of the routine (e.g., "DemoRoutine")
            func_name: Name of the function (e.g., "greet")
            func: The callable
            signature: Optional (arg_names, defaults) tuple
        """
        key = f"{routine_name}.{func_name}"
        self._functions[key] = func
        self._routine_names.add(routine_name)
        if signature:
            self._function_signatures[key] = signature

    def get(self, routine_name: str, func_name: str) -> Optional[Callable]:
        """
        Get a function by routine and function name.

        O(1) lookup via flat registry.
        """
        return self._functions.get(f"{routine_name}.{func_name}")

    def get_by_key(self, key: str) -> Optional[Callable]:
        """
        Get a function by full key (e.g., "DemoRoutine.greet").

        O(1) lookup.
        """
        return self._functions.get(key)

    def has_routine(self, routine_name: str) -> bool:
        """Check if a routine is registered."""
        return routine_name in self._routine_names

    def has_function(self, routine_name: str, func_name: str) -> bool:
        """Check if a specific function exists."""
        return f"{routine_name}.{func_name}" in self._functions

    def list_routines(self) -> List[str]:
        """List all registered routine names."""
        return sorted(self._routine_names)

    def list_functions(self, routine_name: str) -> List[str]:
        """List all functions for a given routine."""
        prefix = f"{routine_name}."
        return [
            key[len(prefix):]
            for key in self._functions
            if key.startswith(prefix)
        ]

    def get_signature(self, routine_name: str, func_name: str) -> Optional[Tuple[List[str], Dict[str, Any]]]:
        """Get function signature (arg_names, defaults)."""
        return self._function_signatures.get(f"{routine_name}.{func_name}")

    def __len__(self) -> int:
        return len(self._functions)

    def __contains__(self, key: str) -> bool:
        return key in self._functions


class RoutineManager:
    """
    Manages loading and access to Python routines.

    Performance-optimized:
    - Loads all routines once at initialization
    - Builds flat function registry for O(1) lookup
    - Extracts function signatures for validation
    - No runtime module imports

    Usage:
        manager = RoutineManager("src/v2/routines/user")
        registry = manager.get_registry()

        # In expression evaluation:
        func = registry.get("DemoRoutine", "greet")
        result = func("World")  # "Hello, World!"
    """

    def __init__(
        self,
        routines_dir: Optional[str] = None,
        auto_load: bool = True
    ):
        """
        Initialize routine manager.

        Args:
            routines_dir: Directory containing Python routine files.
                         If None, uses default location.
            auto_load: Whether to load routines immediately.
        """
        if routines_dir is None:
            # Default to src/v2/routines/user relative to this file
            base_path = Path(__file__).parent / "user"
            self.routines_dir = base_path
        else:
            self.routines_dir = Path(routines_dir)

        self._registry = RoutineRegistry()
        self._modules: Dict[str, Any] = {}  # Keep module refs to prevent GC
        self._loaded = False

        if auto_load:
            self.load()

    def load(self) -> None:
        """
        Load all routines from directory.

        Idempotent - can be called multiple times safely.
        """
        if self._loaded:
            return

        if not self.routines_dir.exists():
            logger.info(f"Routines directory not found: {self.routines_dir}")
            self._loaded = True
            return

        logger.info(f"Loading Python routines from: {self.routines_dir}")

        # Find all .py files (excluding __init__.py and private files)
        routine_files = [
            f for f in self.routines_dir.glob("*.py")
            if not f.name.startswith('_')
        ]

        for routine_file in routine_files:
            try:
                self._load_routine(routine_file)
            except Exception as e:
                # exc_info=True attaches the full traceback to the log
                # record so downstream handlers (and pytest's caplog) can
                # recover the call site. Per PITFALLS #7 observability
                # prevention rule: loader failures must "log with traceback",
                # not just the exception's __str__. See AUD-RTN-02.
                logger.error(
                    f"Failed to load routine {routine_file.name}: {e}",
                    exc_info=True,
                )

        self._loaded = True
        logger.info(
            f"Loaded {len(self._modules)} routines with "
            f"{len(self._registry)} functions"
        )

    def _load_routine(self, file_path: Path) -> None:
        """Load a single routine module and register its functions."""
        module_name = f"v2_routine_{file_path.stem}"
        routine_name = self._to_class_name(file_path.stem)

        # Load module
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module from {file_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Store module reference
        self._modules[routine_name] = module

        # Extract and register public functions
        func_count = 0
        for name, obj in inspect.getmembers(module, inspect.isfunction):
            # Skip private functions
            if name.startswith('_'):
                continue

            # Skip imported functions (only include functions defined in this module)
            if obj.__module__ != module_name:
                continue

            # Extract signature
            try:
                sig = inspect.signature(obj)
                arg_names = list(sig.parameters.keys())
                defaults = {
                    k: v.default
                    for k, v in sig.parameters.items()
                    if v.default is not inspect.Parameter.empty
                }
                signature = (arg_names, defaults)
            except (ValueError, TypeError):
                signature = None

            self._registry.register(routine_name, name, obj, signature)
            func_count += 1

        logger.debug(f"Loaded routine {routine_name} with {func_count} functions")

    def _to_class_name(self, snake_case: str) -> str:
        """Convert snake_case to ClassName."""
        return ''.join(word.capitalize() for word in snake_case.split('_'))

    def get_registry(self) -> RoutineRegistry:
        """Get the function registry for expression evaluation."""
        if not self._loaded:
            self.load()
        return self._registry

    def get_function(self, routine_name: str, func_name: str) -> Optional[Callable]:
        """
        Get a specific function.

        Convenience method - for expression evaluation, use get_registry()
        for O(1) lookups.
        """
        return self._registry.get(routine_name, func_name)

    def reload(self) -> None:
        """
        Reload all routines.

        Useful during development when routine code changes.
        """
        self._loaded = False
        self._registry = RoutineRegistry()
        self._modules.clear()
        self.load()

    def list_routines(self) -> List[str]:
        """List all loaded routine names."""
        return self._registry.list_routines()

    def list_functions(self, routine_name: str) -> List[str]:
        """List all functions for a routine."""
        return self._registry.list_functions(routine_name)

    def __repr__(self) -> str:
        return (
            f"RoutineManager(dir={self.routines_dir}, "
            f"routines={len(self._modules)}, functions={len(self._registry)})"
        )
