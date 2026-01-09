"""
Trigger manager for handling OnSubjobOk, OnComponentoOk, OnSubjobError triggers
"""
from typing import Dict, List, Any, Optional, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TriggerType(Enum):
    """Types of triggers"""
    ON_SUBJOB_OK = "OnSubjobOk"
    ON_SUBJOB_ERROR = "OnSubjobError"
    ON_COMPONENT_OK = "OnComponentOK"
    ON_COMPONENT_ERROR = "OnComponentError"
    RUN_IF = "RunIf"


class Trigger:
    """Represents a trigger connection between components"""

    def __init__(self, trigger_type: str, from_component: str, to_component: str,
                 condition: Optional[str] = None):
        self.type = TriggerType(trigger_type) if isinstance(trigger_type, str) else trigger_type
        self.from_component = from_component
        self.to_component = to_component
        self.condition = condition

    def __repr__(self):
        return f"Trigger({self.type.value}: {self.from_component} -> {self.to_component})"
    

class TriggerManager:
    """
    Manages trigger execution flow between components and subjobs
    """
    
    def __init__(self, global_map: Any = None):
        self.global_map = global_map
        self.triggers: List[Trigger] = []
        self.component_status: Dict[str, str] ={}  # component_id -> status
        self.subjob_components: Dict[str, List[str]] = {}  # subjob_id -> [component_ids]
        self.component_to_subjob: Dict[str, str] = {}  # component_id -> subjob_id
        self.triggered_components: Set[str] = set()  # Track triggered components
        self.subjob_source_components: Dict[str, List[str]] = {} # subjob_id -> [source component_ids with no inputs]

    def add_trigger(self, trigger_type: str, from_component: str,
                   to_component: str, condition: Optional[str] = None) -> None:
        """Add a trigger to the manager"""
        trigger = Trigger(trigger_type, from_component, to_component, condition)
        self.triggers.append(trigger)
        logger.debug(f"Added trigger: {trigger}")
        
    def register_subjob(self, subjob_id: str, components: List[str],
                       source_components: Optional[List[str]] = None) -> None:
        """
        Register a subjob and its components
        
        Args:
            subjob_id: The subjob identifiers
            components: List of all component IDs in this subjob
            source_components: List of component IDs with no inputs (source components)
        """
        self.subjob_components[subjob_id] = components
        for comp_id in components:
            self.component_to_subjob[comp_id] = subjob_id
            
        # Store source components (components with no inputs)
        if source_components:
            self.subjob_source_components[subjob_id] = source_components
            logger.debug(f"Registered subjob {subjob_id} with {len(components)} components, "
                        f"{len(source_components)} source components: {source_components}")
        else:
            logger.debug(f"Registered subjob {subjob_id} with components: {components}")
            
    def set_component_status(self, component_id: str, status: str) -> None:
        """Update component execution status"""
        self.component_status[component_id] = status
        logger.debug(f"component {component_id} status: {status}")
        
    def get_subjob_status(self, subjob_id: str) -> str:
        """
        Get subjob status based on its components
        Returns: 'success', 'error', 'running', 'pending'
        """
        if subjob_id not in self.subjob_components:
            return 'pending'
        
        components = self.subjob_components[subjob_id]
        statuses = [self.component_status.get(comp, 'pending') for comp in components]

        if 'error' in statuses:
            return 'error'
        elif 'running' in statuses:
            return 'running'
        elif all(status == 'success' for status in statuses):
            return 'success'
        else:
            return 'pending'
        
    def get_triggered_components(self, component_id: str, status: str) -> List[str]:
        """
        Get components that should be triggered based on component status

        Args:
            component_id: The component that just finished
            status: The completion status ('success' or 'error')

        Returns:
            List of component IDs to execute next
        """
        teriggered = []

        # Get subjob of the completed component
        subjob_id = self.component_to_subjob.get(component_id)

        for trigger in self.triggers:
            # For OnSubjob triggers, check if ANY component in the same subjob completed
            # Not just the specific from_component
            if trigger.type in [TriggerType.ON_SUBJOB_OK, TriggerType.ON_SUBJOB_ERROR]:
                #check if the completed component is in the same subjobas from_component
                from_subjob = self.component_to_subjob.get(trigger.from_component)
                if from_subjob != subjob_id:
                    continue
            else:
                # For other triggers, check specific from_component
                if trigger.from_component != component_id:
                    continue

            # check if already triggered
            if trigger.to_component in self.triggered_components:
                logger.debug(f"component {trigger.to_component} already triggered, skipping")
                continue

            should_trigger = False

            # check trigger type and status
            if trigger.type == TriggerType.ON_COMPONENT_OK and status == 'success':
                should_trigger = True

            elif trigger.type == TriggerType.ON_COMPONENT_ERROR and status == 'error':
                should_trigger = True

            elif trigger.type == TriggerType.ON_SUBJOB_OK and status == 'success':
                # check if entire subjob completed successfully
                if subjob_id:
                    subjob_status = self.get_subjob_status(subjob_id)
                    logger.debug(f"OnSubjobOk check: component {component_id} in subjob {subjob_id}, subjob status: {subjob_status}")
                    if subjob_status == 'success':
                        should_trigger = True
                else:
                    logger.debug(f"OnSubjobOk: component {component_id} has no subjob_id")

            elif trigger.type == TriggerType.ON_SUBJOB_ERROR and status == 'error':
                # subjob has error
                if subjob_id and self.get_subjob_status(subjob_id) == 'error':
                    should_trigger = True

            elif trigger.type == TriggerType.RUN_IF:
                # Evaluate condition
                if self._evaluate_condition(trigger.condition):
                    should_trigger = True

            if should_trigger:
                triggered.append(trigger.to_component)
                self.triggered_components.add(trigger.to_component)
                logger.info(f"Trigger activated: {trigger}")

                # When a component is triggered, also trigger all other source components
                #(components with no inputs) in the same subjob
                to_subjob_id = self.component_to_subjob.get(trigger.to_component)
                if to_subjob_id and to_subjob_id in self.subjob_source_components:
                    source_comps = self.subjob_source_components[to_subjob_id]
                    for source_comp in source_comp:
                        #Only add if not already triggered and not the same as target
                        if source_comp != trigger.to_component and source_comp not in self.triggered_components:
                            triggered.append(source_comp)
                            self.triggered_components.add(source_comp)
                            logger.info(f"Also triggering source component {source_comp} in subjob {to_subjob_id}")

        return teriggered
    
    def _evaluate_condition(self, condition: Optional[str]) -> bool:
        """
        Evaluate a RunIf condition

        Example conditions:
        - ((Integer)globalMap.get("tFileInput_1_NB_LINE")) > 0
        -globalMap.get("ERROR_MESSAGE") != null
        """
        if not condition or not self.global_map:
            return True
        
        try:
            # Convert Java-style condition to python
            python_condition = condition

            # Replace ((Integer)globalMap.get("key")) with globalMap.get("key")
            import re
            pattern = r'\(\(Integer\)globalMap\.get\("([^"]+)"\)\)'

            def replace_func(match):
                key = match.group(1)
                value = self.global_map.get(key, 0)
                return str(value)
            
            python_condition = re.sub(pattern, replace_func, python_condition)

            # Replace globalMap.get("key") with actual values
            pattern2 = r'globalMap\.get\("([^"]+"\)'
            
            def replace_func2(match):
                key = match.group(1)
                value = self.global_map.get(key)
                if value is None:
                    return 'None'
                elif isinstance(value, str):
                    return f'"{value}"'
                else:
                    return str(value)
                
            python_condition = re.sub(pattern2, replace_func2, python_condition)

            # Replace Java operators
            python_condition = python_condition.replace('&&', ' and ')
            python_condition = python_condition.replace('\\', 'or ')

        
        



       



