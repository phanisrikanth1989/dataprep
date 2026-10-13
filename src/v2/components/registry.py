"""Component registry: the type names a job config may use, and their classes."""
from __future__ import annotations

from typing import Dict, List, Optional, Type

from .base import Component


class Registry:
    """Maps every name of a component type to its class.

    A class registers under all its ``names``: v2's own name first, then the
    v1 names that job configs carry (``FileInputDelimited``,
    ``tFileInputDelimited``).
    """

    def __init__(self) -> None:
        self._classes: Dict[str, Type[Component]] = {}

    def register(self, cls: Type[Component]) -> Type[Component]:
        """Register a component class under each of its names. Usable as a decorator."""
        if not cls.names:
            raise ValueError(f"{cls.__name__} declares no names to register under")
        for name in cls.names:
            holder = self._classes.get(name)
            if holder is not None and holder is not cls:
                raise ValueError(
                    f"component name '{name}' is already registered to {holder.__name__}; "
                    f"cannot register it to {cls.__name__}"
                )
            self._classes[name] = cls
        return cls

    def get(self, name: str) -> Optional[Type[Component]]:
        """The class registered under a type name, or None."""
        return self._classes.get(name)

    def classes(self) -> List[Type[Component]]:
        """Every registered class, once each, in registration order."""
        seen: List[Type[Component]] = []
        for cls in self._classes.values():
            if cls not in seen:
                seen.append(cls)
        return seen

    def names(self) -> List[str]:
        """Every registered type name, sorted."""
        return sorted(self._classes)


REGISTRY = Registry()
