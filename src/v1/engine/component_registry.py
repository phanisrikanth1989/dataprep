"""Decorator-based engine component registry.

Matches the converter registry pattern from
src/converters/talend_to_v1/components/registry.py.
Registration is triggered via __init__.py imports (D-03).
Phase 3 creates infrastructure only -- registry starts empty (D-04).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .base_component import BaseComponent

logger = logging.getLogger(__name__)


class ComponentRegistry:
    """Maps component type names to engine component classes.

    Supports both V1 names (PascalCase, no prefix) and Talend aliases
    (camelCase with 't' prefix). Both map to the same class.
    """

    def __init__(self) -> None:
        self._components: dict[str, type[BaseComponent]] = {}

    def register(self, *names: str):
        """Decorator to register a component class under one or more type names.

        Args:
            *names: Component type names (e.g., 'FileInputDelimited', 'tFileInputDelimited').

        Returns:
            Decorator function.

        Raises:
            ValueError: If a name is already registered to a different class.
        """
        def decorator(cls: type[BaseComponent]) -> type[BaseComponent]:
            for name in names:
                if name in self._components:
                    existing = self._components[name]
                    if existing is not cls:
                        raise ValueError(
                            f"Component type {name!r} already registered to "
                            f"{existing.__name__}, cannot register {cls.__name__}"
                        )
                    # Same class re-registered under same name -- idempotent, skip
                    continue
                self._components[name] = cls
                logger.debug("Registered component type %r -> %s", name, cls.__name__)
            return cls
        return decorator

    def get(self, name: str) -> Optional[type[BaseComponent]]:
        """Return the component class for name, or None if not registered."""
        return self._components.get(name)

    def list_types(self) -> list[str]:
        """Return sorted list of all registered component type names."""
        return sorted(self._components)

    def __len__(self) -> int:
        return len(self._components)

    def __contains__(self, name: str) -> bool:
        return name in self._components


REGISTRY = ComponentRegistry()
