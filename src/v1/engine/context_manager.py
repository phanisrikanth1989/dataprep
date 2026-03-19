"""
Context Manager for handling job context variables
"""
from typing import Any, Dict, Optional
from decimal import Decimal
import re
import logging
import os
import sys

logger = logging.getLogger(__name__)    


class ContextManager:
    """
    Manages context variables for ETL jobs.
    Handles variable resolution, type conversion, and context loading.

    Note: Java Bridge lifecycle is now managed separately by JavaBridgeManager.
    """

    def __init__(self, initial_context: Optional[Dict[str, Dict[str, Any]]] = None, default_context='Default', java_bridge_manager=None):
        self.context: Dict[str, Any] = {}
        self.context_types: Dict[str, str] = {} #Store variable types
        self.java_bridge_manager = java_bridge_manager #reference to manager, not owner

        if initial_context:
            context_dict_to_load = initial_context.get(default_context, initial_context)
            self.load_context(context_dict_to_load)
        
    def load_context(self, context_dict: Dict[str, Any]) -> None:
        """ Load context variables from a dictionary (from JSON config)"""
        for key, value_dict in context_dict.items():
            if isinstance(value_dict, dict):
                self.set(key, value_dict.get('value'), value_dict.get('type'))
            else:
                self.set(key, value_dict)
            
    def load_from_file(self, file_path: str, delimiter: str = '=') -> None:
        """ 
        Load context variables from a file (key=value format)
        Used by tCOntextLoad component
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if delimiter in line:
                            key, value = line.split(delimiter, 1)
                            self.set(key.strip(), value.strip())
                        
            logger.info(f"Loaded context from file: {file_path}: {len(self.context)} variables")
        except Exception as e:
            logger.error(f"Error loading context from file {file_path}: {e}")   
            raise
        
    def set(self, key: str, value: Any, value_type: Optional[str] = None) -> None:
        """ Set a context variable with optional type conversion"""
        if value_type:
            value = self._convert_type(value, value_type)
            #Store the type for later lookup
            self.context_types[key] = value_type
    
        self.context[key] = value
        logger.debug(f"Context: Set {key} = {value} (type: {value_type})")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a context variable"""
        return self.context.get(key, default)
    
    def get_type(self, key: str) -> Optional[str]:
        """ Get the type of a context variable """
        return self.context_types.get(key)  
    
    def resolve_string(self, value: str) -> str:
        """ 
        Resolve context variables in a string 
        Replaces ${context.variable} or context.variable with actual values
        Also handles expressions like ${context.var} + "/file.csv"

        Special handling for Java code
        """
        if not isinstance(value, str):
            return value

        # check for {{java}} marker - indicates Java code 
        if value.startswith('{{java}}'):
                return value
        
        #First, check if this is an expression with concatenation
        if '+' in value and '${context.' in value:
            #This is an expression like : ${context.output_dir} + "/file.csv"
            #Extract and evaluate each part
            parts = []
            for part in value.split('+'):
                part = part.strip()

                #Handle context variable references
                if '${context.' in part:
                    pattern = r'\$\{context\.(\w+)\}'
                    def replace_func(match):
                        var_name = match.group(1)
                        var_value = self.get(var_name, '')
                        return str(var_value) if var_value is not None else match.group(0)
                    part = re.sub(pattern, replace_func, part)

                #Remove quotes from string literals
                if part.startswith('"') and part.endswith('"'):
                    part = part[1:-1]
                elif part.startswith("'") and part.endswith("'"):
                    part = part[1:-1]
                
                parts.append(part)

            # Concatenate all parts
            return ''.join(parts)
        
        # Pattern 1 : ${context.variable}
        pattern1 = r'\$\{context\.(\w+)\}'

        def replace_func1(match):
            var_name = match.group(1)
            var_value = self.get(var_name)
            return str(var_value) if var_value is not None else match.group(0)
        
        value = re.sub(pattern1, replace_func1, value)

        # Pattern 2 : context.variable (without ${})
        pattern2 = r'\bcontext\.(\w+)\b'

        def replace_func2(match):
            var_name = match.group(1)
            var_value = self.get(var_name)
            return str(var_value) if var_value is not None else match.group(0)

        value = re.sub(pattern2, replace_func2, value)

        return value
    
    def resolve_dict(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """ 
        Resolve context variables in a configuration dictionary 
        
        Special handling for Java code
        """
        resolved = {}
        for key, value in config.items():
            #skip java code fields -they access context at Java runtime
            if key in ['java_code', 'imports']:
                resolved[key] = value # no context resolution for java code
            elif isinstance(value, str):
                resolved[key] = self.resolve_string(value)  
            elif isinstance(value, dict):
                resolved[key] = self.resolve_dict(value)
            elif isinstance(value, list):
                resolved[key] = [self.resolve_string(v) if isinstance(v, str) else v for v in value]
            else:
                resolved[key] = value
        return resolved
    
    def _convert_type(self, value: Any, value_type: str) -> Any:
        """ Convert a value to the specified type """
        if value is None or value == '':
            return value
        
        # Support both Talend types (id_integer) and Python types (Int) 
        type_mapping = {
            #talend types
            'id_String': 'str',
            'id_Integer': 'int',
            'id_Long': 'int',
            'id_Float': 'float',
            'id_Double': 'float',
            'id_Boolean': lambda v: str(v).lower() in ('true', '1', 'yes'),
            'id_Date': 'str',  # Keep as strings for now
            'id_BigDecimal': 'Decimal',
            #python types
            'str': 'str',
            'int': 'int',
            'float': 'float', 
            'bool': lambda v: str(v).lower() in ('true', '1', 'yes'),
            'Decimal': 'Decimal', 
            'datetime': str,
            'object': str
        }

        converter = type_mapping.get(value_type, str)   
        
        try:
            return converter(value)
        except (ValueError, TypeError):
            logger.warning(f"ContextManager: Failed to convert value '{value}' to type '{value_type}'")
            return value
        
    def contains(self, key: str) -> bool:
        """ Check if a context variable exists """
        return key in self.context
    
    def remove(self, key: str) -> None:
        """ Remove a context variable """
        if key in self.context:
            del self.context[key]
            if key in self.context_types:
                del self.context_types[key]
    
    def clear(self) -> None:
        """ Clear all context variables """
        self.context.clear()
        self.context_types.clear()

    def get_all(self) -> Dict[str, Any]:
        """ Get all context variables """
        return self.context.copy()
    
    #================================================
    #Java Bridge Integration (Delegated to Manager )
    #================================================

    def get_java_bridge(self):
        """ Get the Java Bridge instance from the manager """
        if self.java_bridge_manager:
            return self.java_bridge_manager.get_bridge()
        return None
    
    def is_java_enabled(self) -> bool:
        """ Check if Java Bridge is enabled """
        if self.java_bridge_manager:
            return self.java_bridge_manager.is_available()
        return False
    
    def __repr__(self) -> str:
        java_status = "enabled" if self.is_java_enabled() else "disabled"
        return f"ContextManager(variables={len(self.context)}, java_bridge={java_status})"