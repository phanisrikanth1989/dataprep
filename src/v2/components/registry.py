"""
Component auto-registration system.

Provides a registry that maps type names (as used in job configs)
to component classes. Components register themselves via decorator:

    from src.v2.components.registry import REGISTRY

    @REGISTRY.register("file_input_delimited")
    class FileInputDelimited(SourceComponent):
        ...

The global REGISTRY instance is the single source of truth for
component type resolution at runtime.
"""
from typing import Dict, List, Optional, Type

from .base import Component


class ComponentRegistry:
    """Registry mapping type names to component classes."""

    def __init__(self):
        self._registry: Dict[str, Type[Component]] = {}

    def register(self, *names: str):
        """
        Decorator to register a component class under one or more names.

        Names are stored in lowercase for case-insensitive lookup.

        Registering a DIFFERENT class under an existing name raises
        ``ValueError`` rather than silently overwriting the incumbent
        (PITFALLS #7 prevention rule; AUD-REG-01 regression guard).
        Re-registering the SAME class under the SAME name is a no-op so
        that test reloads and import-side-effect idempotency still work.

        Usage:
            @registry.register("my_component", "my_alias")
            class MyComponent(TransformComponent):
                def apply(self, inputs):
                    ...
        """
        def decorator(cls: Type[Component]) -> Type[Component]:
            for name in names:
                lname = name.lower()
                existing = self._registry.get(lname)
                if existing is not None and existing is not cls:
                    raise ValueError(
                        f"Component name {lname!r} is already registered to "
                        f"{existing.__name__}; cannot re-register it to "
                        f"{cls.__name__}. Per PITFALLS #7, duplicate "
                        f"registration is a silent-overwrite footgun and "
                        f"must be loud. Pick a different alias or unify "
                        f"the two classes."
                    )
                self._registry[lname] = cls
            return cls
        return decorator

    def get(self, name: str) -> Optional[Type[Component]]:
        """Look up a component class by type name. Returns None if not found."""
        return self._registry.get(name.lower())

    def list_types(self) -> List[str]:
        """Return a sorted list of all registered type names."""
        return sorted(set(self._registry.keys()))


# Global registry instance
REGISTRY = ComponentRegistry()
