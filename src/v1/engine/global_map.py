"""
GlobalMap Implementation for storing component statistics and variables 
similar to talend's globalMap.
"""
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class GlobalMap:
    """
    Talend like global storage for component statistics and variables.
    Used for sharing data between different components and tracking execution stats.
    """

    def __init__(self):
        self._storage: Dict[str, Any] = {}
        self._component_stats: Dict[str, Dict[str, int]] = {}

    def put(self, key: str, value: Any) -> None:
        """Store a value in the global map"""
        self._map[key] = value
        logger.debug(f"GlobalMap: Set {key} = {value}")

    def get(self, key: str) -> Optional[Any]:
        """ Retrieve a value from the global map """
        return self._map.get(key, default)
    
    def remove(self, key: str) -> None:
        """ Remove a value from the global map """
        if key in self._map:
            del self._map[key]
            logger.debug(f"GlobalMap: Removed key {key}")
    
    def contains(self, key: str) -> bool:
        """ Check if a key exists in the global map """
        return key in self._map
    
    def put_component_stat(self, component_id: str, stat_name: str, value: int) -> None:
        """ Store a component statistics (NB_LINE, NB_LINE_OK, NB_LINE_REJECT) """
        if component_id not in self._component_stats:
            self._component_stats[component_id] = {}

        self._component_stats[component_id][stat_name] = value

        #Also store in main map for backward compatibility
        key = f"{component_id}_{stat_name}"
        self.put(key, value)

    def get_component_stat(self, component_id: str, stat_name: str, default: int = 0) -> int:
        """ Retrieve a component statistic """
        if component_id in self._component_stats:
            return self._component_stats[component_id].get(stat_name, default)
        
        #Fallback to main map
        key = f"{component_id}_{stat_name}"
        return self.get(key, default)
    
    def get_nb_line(self, component_id: str) -> int:
        """ Get number of lines processed by a component """
        return self.get_component_stat(component_id, "NB_LINE", 0)
    
    def get_nb_line_ok(self, component_id: str) -> int:
        """ Get number of lines successfully processed by a component """
        return self.get_component_stat(component_id, "NB_LINE_OK", 0)   
    
    def get_nb_line_reject(self, component_id: str) -> int:
        """ Get number of lines rejected by a component """
        return self.get_component_stat(component_id, "NB_LINE_REJECT", 0)
    
    def clear(self) -> None:
        """ Clear all stored values"""
        self._map.clear()
        self._component_stats.clear()
        logger.debug("GlobalMap: Cleared all entries")

    def get_all_stats(self) -> Dict[str, Dict[str, int]]:
        """ Get all component statistics """
        return self._component_stats.copy()
    
    def get_all(self) -> Dict[str, Any]:
        """ Get all key-value pairs in the global map """
        return self._map.copy()
    
    def __repr__(self) -> str:
        return f"GlobalMap(items={self._map}, component_stats={self._component_stats})"