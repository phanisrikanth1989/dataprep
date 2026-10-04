from __future__ import annotations

from typing import Type

from .base import ComponentConverter


class ConverterRegistry:
    """Registry that maps Talend component type names to converter classes."""

    def __init__(self) -> None:
        self._converters: dict[str, Type[ComponentConverter]] = {}

    def register(self, *names: str):
        """Decorator that registers a converter class under one or more Talend type names.

        Names are **case-sensitive** (Talend types like ``tFileInputDelimited``
        are case-sensitive).
        """

        def decorator(cls: Type[ComponentConverter]) -> Type[ComponentConverter]:
            for name in names:
                if name in self._converters:
                    raise ValueError(
                        f"Talend type {name!r} is already registered to "
                        f"{self._converters[name].__name__}"
                    )
                self._converters[name] = cls
            return cls

        return decorator

    def get(self, name: str) -> Type[ComponentConverter] | None:
        """Return the converter class for *name*, or ``None`` if not registered."""
        return self._converters.get(name)

    def list_types(self) -> list[str]:
        """Return a sorted list of all registered Talend type names."""
        return sorted(self._converters)


REGISTRY = ConverterRegistry()
