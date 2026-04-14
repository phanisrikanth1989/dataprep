"""Talend-compatible globalMap -- key-value store for component statistics
and inter-component variables.

Rewritten from scratch to fix ENG-02 (get() NameError) and add
reset_component() for iterate support.
"""
from typing import Any
import logging

logger = logging.getLogger(__name__)


class GlobalMap:
    """Talend-compatible globalMap implementation.

    Stores arbitrary key-value pairs and per-component statistics.
    Component stats are accessible both via the structured
    ``get_component_stat()`` API and via flat keys of the form
    ``{component_id}_{stat_name}`` in the main store.

    Thread safety: single-threaded batch ETL -- no locking required.
    """

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._component_stats: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Core key-value operations
    # ------------------------------------------------------------------

    def put(self, key: str, value: Any) -> None:
        """Store a value in the global map.

        Args:
            key: The key to store under.
            value: Any value (including None).
        """
        self._store[key] = value
        logger.debug("GlobalMap: set %s = %s", key, value)

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from the global map.

        Args:
            key: The key to look up.
            default: Value to return if key is not present. Defaults to None.

        Returns:
            The stored value, or *default* if the key does not exist.
        """
        return self._store.get(key, default)

    def remove(self, key: str) -> None:
        """Remove a key from the global map. No error if key is absent.

        Args:
            key: The key to remove.
        """
        if key in self._store:
            del self._store[key]
            logger.debug("GlobalMap: removed %s", key)

    def contains(self, key: str) -> bool:
        """Check whether a key exists in the global map.

        Args:
            key: The key to check.

        Returns:
            True if the key is present, False otherwise.
        """
        return key in self._store

    # ------------------------------------------------------------------
    # Component statistics
    # ------------------------------------------------------------------

    def put_component_stat(self, component_id: str, stat_name: str, value: Any) -> None:
        """Store a component statistic (e.g. NB_LINE, NB_LINE_OK, NB_LINE_REJECT).

        The stat is stored in both the structured ``_component_stats`` dict
        and as a flat key ``{component_id}_{stat_name}`` in ``_store`` for
        backward-compatible access via ``get()``.

        Args:
            component_id: The component identifier (e.g. ``"tFileInputDelimited_1"``).
            stat_name: The stat name (e.g. ``"NB_LINE"``).
            value: The stat value.
        """
        if component_id not in self._component_stats:
            self._component_stats[component_id] = {}
        self._component_stats[component_id][stat_name] = value

        # Flat key for backward-compatible access
        flat_key = f"{component_id}_{stat_name}"
        self._store[flat_key] = value

    def get_component_stat(self, component_id: str, stat_name: str, default: Any = 0) -> Any:
        """Retrieve a component statistic.

        Checks the structured ``_component_stats`` dict first, then falls
        back to the flat key in ``_store``.

        Args:
            component_id: The component identifier.
            stat_name: The stat name.
            default: Value to return if the stat is not found. Defaults to 0.

        Returns:
            The stat value, or *default* if not found.
        """
        if component_id in self._component_stats:
            return self._component_stats[component_id].get(stat_name, default)
        return self._store.get(f"{component_id}_{stat_name}", default)

    def reset_component(self, component_id: str) -> None:
        """Clear all statistics for a single component.

        Used by iterate loops to reset a component's counters before
        re-execution. Removes both the structured stats and the
        corresponding flat keys from ``_store``.

        Args:
            component_id: The component whose stats should be cleared.
        """
        # Remove flat keys from _store
        if component_id in self._component_stats:
            for stat_name in self._component_stats[component_id]:
                flat_key = f"{component_id}_{stat_name}"
                self._store.pop(flat_key, None)
            del self._component_stats[component_id]
            logger.debug("GlobalMap: reset component %s", component_id)

    # ------------------------------------------------------------------
    # Convenience stat accessors
    # ------------------------------------------------------------------

    def get_nb_line(self, component_id: str) -> int:
        """Return NB_LINE for a component (0 if not set)."""
        return self.get_component_stat(component_id, "NB_LINE", 0)

    def get_nb_line_ok(self, component_id: str) -> int:
        """Return NB_LINE_OK for a component (0 if not set)."""
        return self.get_component_stat(component_id, "NB_LINE_OK", 0)

    def get_nb_line_reject(self, component_id: str) -> int:
        """Return NB_LINE_REJECT for a component (0 if not set)."""
        return self.get_component_stat(component_id, "NB_LINE_REJECT", 0)

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def get_all(self) -> dict[str, Any]:
        """Return a shallow copy of all key-value pairs.

        The returned dict is a *copy* -- mutating it does NOT affect
        the internal store. This prevents external components from
        accidentally corrupting GlobalMap state.

        Returns:
            A new dict containing all current entries.
        """
        return dict(self._store)

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Return a copy of all component statistics.

        Returns:
            A dict mapping component IDs to their stat dicts.
        """
        return {cid: dict(stats) for cid, stats in self._component_stats.items()}

    def clear(self) -> None:
        """Clear all stored values and component statistics."""
        self._store.clear()
        self._component_stats.clear()
        logger.debug("GlobalMap: cleared all values")

    # ------------------------------------------------------------------
    # Dunder methods
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"GlobalMap(items={len(self._store)}, components={len(self._component_stats)})"
