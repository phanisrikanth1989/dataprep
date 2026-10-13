"""Routines: the job's own Python functions, usable in expressions.

A routine in v2 takes Polars expressions and returns one, so it runs on
whole columns. Modules are found and named as v1 finds and names them: every
``.py`` file of the routines folder, ``fee_rules.py`` becoming ``FeeRules``,
read in an expression as ``routines.FeeRules.net(row1.amount)`` or
``FeeRules.net(row1.amount)``.
"""
from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

from ..errors import ConfigurationError

logger = logging.getLogger(__name__)

DEFAULT_FOLDER = "src/python_routines"


def load_routines(settings: Optional[Mapping[str, Any]]) -> Dict[str, Dict[str, Callable[..., Any]]]:
    """Load the routine modules a job config asks for.

    Args:
        settings: The job config's ``python_config`` block: ``enabled``,
            ``routines_dir`` and ``routines`` (names that must be there).

    Returns:
        Module name to its public functions. Empty unless routines are
        enabled.

    Raises:
        ConfigurationError: When the folder does not exist, a module cannot
            be imported, or a required routine is not found.
    """
    if not settings or not settings.get("enabled"):
        return {}
    folder = Path(settings.get("routines_dir") or DEFAULT_FOLDER)
    if not folder.is_dir():
        raise ConfigurationError(f"routines folder does not exist: {folder}")
    modules: Dict[str, Dict[str, Callable[..., Any]]] = {}
    for path in sorted(folder.glob("*.py")):
        if path.name.startswith("_"):
            continue
        name = "".join(word.capitalize() for word in path.stem.split("_"))
        modules[name] = _functions(path)
        logger.info(f"Loaded routine {name} from {path}")
    missing = [name for name in settings.get("routines") or [] if name not in modules]
    if missing:
        raise ConfigurationError(f"routine(s) not found in {folder}: {', '.join(missing)}")
    return modules


def _functions(path: Path) -> Dict[str, Callable[..., Any]]:
    """Import one routine file and return its public functions."""
    spec = importlib.util.spec_from_file_location(f"v2_routine_{path.stem}", path)
    try:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 -- user code may fail in any way
        raise ConfigurationError(f"routine file {path.name} cannot be imported: {exc}") from exc
    return {
        name: value
        for name, value in vars(module).items()
        if callable(value) and not name.startswith("_") and getattr(value, "__module__", None) == module.__name__
    }
