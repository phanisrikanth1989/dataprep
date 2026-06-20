"""
Trigger manager for handling OnSubjobOk, OnComponentOk, OnSubjobError,
OnComponentError, and RunIf triggers between components and subjobs.

Fixes:
    - ENG-06: != operator no longer corrupted by ! -> not replacement
    - ENG-10: OnSubjobOk checks ALL subjob components, not just trigger source
    - NEW-04: Condition evaluation uses sandboxed eval (no builtins access)
    - NEW-05: All Java cast types handled (Integer, Boolean, String, Long, etc.)
"""
from typing import Dict, List, Any, Optional, Set
from enum import Enum
import logging
import re

from .exceptions import TriggerEvaluationError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cast type mapping: Java type name -> Python type converter
# ---------------------------------------------------------------------------

_JAVA_CAST_MAP: Dict[str, type] = {
    "Integer": int,
    "Long": int,
    "Short": int,
    "Byte": int,
    "Float": float,
    "Double": float,
    "Boolean": bool,
    "String": str,
}

# Pattern: ((Type)globalMap.get("key"))
_CAST_PATTERN = re.compile(r"""\(\((\w+)\)globalMap\.get\(['"]([^'"]+)['"]\)\)""")

# Safe globals for restricted eval -- no builtins, only basic type constructors
_SAFE_GLOBALS: Dict[str, Any] = {
    "__builtins__": {},
    "None": None,
    "True": True,
    "False": False,
    "int": int,
    "str": str,
    "float": float,
    "bool": bool,
}


def _to_python_scalar(value: Any) -> Any:
    """Convert numpy/pandas scalar types to native Python equivalents.

    NumPy >= 2.0 repr(numpy.int64(7)) produces 'np.int64(7)', which
    breaks eval() when 'np' is not in scope.  Calling .item() on any
    numpy scalar returns the equivalent native Python type (int, float,
    bool, str) so that repr() produces a safe literal.

    Non-numpy values are returned unchanged.
    """
    if hasattr(value, "item"):
        try:
            return value.item()
        except (AttributeError, ValueError):
            pass
    return value


class TriggerType(Enum):
    """Types of triggers between components/subjobs."""
    ON_SUBJOB_OK = "OnSubjobOk"
    ON_SUBJOB_ERROR = "OnSubjobError"
    ON_COMPONENT_OK = "OnComponentOk"
    ON_COMPONENT_ERROR = "OnComponentError"
    RUN_IF = "RunIf"


class Trigger:
    """Represents a trigger connection between components.

    ``output_id`` mirrors Talend Studio's ``<connection outputId="N">``
    attribute and records the visual fan-out order (OnComponentOk,
    OnSubjobOk, etc.). The TriggerManager iterates triggers from the
    same source in ascending ``output_id`` order, so multi-trigger chains
    (one branch writes globalMap, the next branch reads it) execute the
    same way Talend does. Default 0 makes single-trigger sources and
    data-flow connections sort first stably.
    """

    def __init__(self,trigger_type: str,from_component: str,to_component: str,
                 condition: Optional[str] = None,output_id: int = 0):
        self.type = TriggerType(trigger_type) if isinstance(trigger_type, str) else trigger_type
        self.from_component = from_component
        self.to_component = to_component
        self.condition = condition
        self.output_id = output_id

    def __repr__(self):
        return f"Trigger({self.type.value}: {self.from_component} -> {self.to_component})"

class TriggerManager:
    """
    Manages trigger execution flow between components and subjobs.

    Handles five trigger types:
        - OnSubjobOk: fires when ALL components in the source subjob complete ok
        - OnSubjobError: fires when any component in the source subjob errors
        - OnComponentOk: fires when a specific component completes ok
        - OnComponentError: fires when a specific component errors
        - RunIf: fires when a condition evaluates to True
    Condition evaluation uses sandboxed eval with restricted globals.
    """

    def __init__(self, global_map: Any = None, context_manager: Any = None):
        """
        Initialise the trigger manager.
        Args:
        global_map:The engine's GlobalMap, used by RunIf conditions that
                reference `globalMap.get(...)` /`((Type)globalMap.get(...))`.
        context_manager:The engine's ContextManager. Optional. When provided,
                RunIf conditions that reference Talend context variables
                (`${context.X}` or bare `context.X`) get those placeholders
                substituted with current values *before* the expression is
                handed to `eval()`.
                Without this wiring such placeholders reach `eval()`
                verbatim and raise `SyntaxError` (the converter does not
                rewrite trigger conditions, so the placeholders are still
                present at runtime).
        """
        self.global_map = global_map
        self.context_manager = context_manager
        self.triggers: List[Trigger] = []
        self.component_status: Dict[str, str] = {}
        self.subjob_components: Dict[str, List[str]] = {}
        self.component_to_subjob: Dict[str, str] = {}
        self.triggered_components: Set[str] = set()
    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

def add_trigger(self, trigger_type: str, from_component: str,
                to_component: str, condition: Optional[str] = None,
                output_id: int = 0) -> None:
    """
    Add a trigger to the manager.
    Args:
        trigger_type: One of the TriggerType values (e.g. "OnSubjobOk").
        from_component: Source component ID.
        to_component: Target component ID to trigger.
        condition: Optional condition expression (for RunIf triggers).
        output_id: Talend Studio visual fan-out order from the XML
            ``<connection outputId="N">`` attribute. Within a single
            source's trigger group, triggers fire in ascending
            ``output_id`` order (see ``get_triggered_components``).
            Default 0 keeps single-trigger sources and data-flow
            connections sorting first.
    """
    trigger = Trigger(trigger_type, from_component, to_component, condition, output_id)
    self.triggers.append(trigger)
    logger.debug(f"Added trigger: {trigger} (output_id={output_id})")

    def register_subjob(self, subjob_id: str, component_ids: List[str]) -> None:
        """Register a subjob and its member components.

        Args:
            subjob_id: The subjob identifier.
            component_ids: List of all component IDs belonging to this subjob.
        """
        self.subjob_components[subjob_id] = component_ids
        for comp_id in component_ids:
            self.component_to_subjob[comp_id] = subjob_id
        logger.debug(f"Registered subjob {subjob_id} with components: {component_ids}")

    # ------------------------------------------------------------------
    # Status tracking
    # ------------------------------------------------------------------

    def set_component_status(self, component_id: str, status: str) -> None:
        """Record a component's execution status.

        Args:
            component_id: The component that completed.
            status: Completion status ('ok', 'success', 'error').
        """
        self.component_status[component_id] = status
        logger.debug(f"Component {component_id} status: {status}")

    # ------------------------------------------------------------------
    # Trigger evaluation
    # ------------------------------------------------------------------

    def get_triggered_components(self, component_id: str) -> List[str]:
        """
        Get components that should be triggered by this component completing.

        Evaluates all registered triggers to determine which downstream
        components should execute next.

        Triggers from the same source are evaluated in ascending
        ``output_id`` order (Talend Studio visual fan-out, OnComponentOk1,
        OnComponentOk2, ...). This matters when one branch writes a
        ``globalMap`` key, the next branch consumes it -- firing the branches
        out of order would let the consumer see a stale / missing value.

        Args:
            component_id: The component that just finished.

        Returns:
            List of component IDs to execute next, ordered by output_id
            within the same source. Triggers from different sources
            preserve their relative registration order.
        """
        triggered: List[str] = []
        # Stable sort by output_id keeps triggers from the same source
        # in Talend's visual fan-out order, even if the JSON was hand-edited
        # and the converter's sort was bypassed. Triggers whose component
        # IDs differ are evaluated independently, so the sort only
        # affects the targets we actually emit. The converter already sorts
        # by (from, output_id) so in the common path this is a no-op.
        sorted_triggers = sorted(
            self.triggers,
            key=lambda t: getattr(t, "output_id", 0),
        )
        for trigger in sorted_triggers:
            # Skip already-triggered components (idempotency)
            
            if trigger.to_component in self.triggered_components:
                continue

            if self.should_fire_trigger(trigger, component_id):
                triggered.append(trigger.to_component)
                self.triggered_components.add(trigger.to_component)
                logger.info(f"Trigger activated: {trigger}")

        return triggered

    def should_fire_trigger(self, trigger: Trigger, component_id: str) -> bool:
        """Determine whether a trigger should fire given a component completion.

        Args:
            trigger: The trigger to evaluate.
            component_id: The component that just completed.

        Returns:
            True if the trigger should fire.
        """
        status = self.component_status.get(component_id, "")
        is_ok = status in ("ok", "success")
        is_error = status == "error"

        if trigger.type == TriggerType.ON_SUBJOB_OK:
            return self._check_subjob_ok(trigger, component_id)

        elif trigger.type == TriggerType.ON_SUBJOB_ERROR:
            return self._check_subjob_error(trigger, component_id)

        elif trigger.type == TriggerType.ON_COMPONENT_OK:
            return trigger.from_component == component_id and is_ok

        elif trigger.type == TriggerType.ON_COMPONENT_ERROR:
            return trigger.from_component == component_id and is_error

        elif trigger.type == TriggerType.RUN_IF:
            if trigger.from_component != component_id:
                return False
            return self._evaluate_condition(trigger.condition)

        return False

    def _check_subjob_ok(self, trigger: Trigger, component_id: str) -> bool:
        """Check OnSubjobOk: ALL components in the source subjob must be ok/success.

        ENG-10 fix: checks every component in the subjob, not just from_component.
        """
        # The completing component must be in the same subjob as the trigger source
        from_subjob = self.component_to_subjob.get(trigger.from_component)
        comp_subjob = self.component_to_subjob.get(component_id)

        if not from_subjob or from_subjob != comp_subjob:
            return False

        # Check ALL components in the subjob have ok/success status
        components = self.subjob_components.get(from_subjob, [])
        return all(
            self.component_status.get(c) in ("ok", "success")
            for c in components
        )

    def _check_subjob_error(self, trigger: Trigger, component_id: str) -> bool:
        """Check OnSubjobError: any component in the source subjob has error status."""
        from_subjob = self.component_to_subjob.get(trigger.from_component)
        comp_subjob = self.component_to_subjob.get(component_id)

        if not from_subjob or from_subjob != comp_subjob:
            return False

        # Check if ANY component in the subjob has error status
        components = self.subjob_components.get(from_subjob, [])
        return any(
            self.component_status.get(c) == "error"
            for c in components
        )

    # ------------------------------------------------------------------
    # Condition evaluation (sandboxed)
    # ------------------------------------------------------------------

    def _evaluate_condition(self, condition: Optional[str]) -> bool:
        """Evaluate a trigger condition expression safely.

        Converts Java-style condition syntax to Python and evaluates
        with restricted globals (no builtins access).

        Handles:
            - Talend context variable placeholders: ${context.X} or context.X
            (substituted with python literal values if context_manager is provided)
            - Java cast types: ((Integer)...), ((Boolean)...), etc.
            - globalMap.get("key") lookups
            - Java operators: &&, ||, !, !=, ==, null, true, false

        Args:
            condition: Java-style condition string, or None.

        Returns:
            True if condition passes (or is None/empty).

        Raises:
            TriggerEvaluationError: If condition cannot be evaluated.
        """
        if not condition or not condition.strip():
            return True

        if not self.global_map:
            return True

        try:
            python_condition = condition

            # Step 0: Resolve Talend context placeholders (${context.X} and
            # bare context.X) with Python literals (repr) so they survive
            # eval(). The converter leaves these placeholders in trigger
            # conditions because trigger configs are not walked by
            # ContextManager.resolve() (which only descends component
            # configs before the eval invokes on the
            # literal '${' and bare 'context.X' identifier).
            python_condition = self._resolve_context_refs(python_condition)

            # Step 1: Replace all ((CastType)globalMap.get("key")) patterns
            python_condition = self._resolve_casts(python_condition)

            # Step 2: Replace remaining globalMap.get("key") (without cast)
            python_condition = self._resolve_global_map_refs(python_condition)

            # Step 3: Convert Java operators to Python (order matters!)
            python_condition = self._convert_operators(python_condition)

            # Step 4: Evaluate with restricted globals
            local_vars: Dict[str, Any] = {}
            result = eval(python_condition,_SAFE_GLOBALS,local_vars)  # noqa: S307
            logger.debug(f"Condition '{condition}' evaluated to {result}")
            return bool(result)

        except TriggerEvaluationError:
            raise
        except Exception as e:
            raise TriggerEvaluationError(
                trigger_type="condition",
                condition=condition,
                message=str(e),
                cause=e,
            ) from e

    def _resolve_context_refs(self, condition: str) -> str:
        """
        Replace "${context.X}" and bare "context.X" with Python literals.

        Mirrors the two regex shapes used by
        ``ContextManager.resolve_string`` but, unlike that method which
        substitutes ``str(value)`` (suitable for textual config values),
        this one substitutes ``repr(value)`` so the resulting expression is
        a valid Python literal once handed to ``eval()``.

        For example with ``context.OUTPUT_OK_FILE_FLG = "Y"``::
            "Y".lower() == str(${context.OUTPUT_OK_FILE_FLG})
            or
            "Y".lower() == str('Y')
        When ``self.context_manager`` is ``None`` or the variable is not
        defined, the original placeholder is left in place so the existing
        downstream error path surfaces a meaningful message rather than a
        silent False. Bare ``context.X`` references whose name is also not
        defined are likewise left untouched.
        """
        if self.context_manager is None:
            return condition
        _MISSING = object()
        def _dollar_brace(match: re.Match) -> str:
            var_name = match.group(1)
            value = self.context_manager.get(var_name, _MISSING)

            if value is _MISSING:
                # Leave the placeholder so eval() raises a cleaner error
                # and callers can see it matches resolve_string semantics.
                return match.group(0)
            return repr(_to_python_scalar(value))

        def _bare(match: re.Match) -> str:
            var_name = match.group(1)
            value = self.context_manager.get(var_name, _MISSING)

            if value is _MISSING:
                return match.group(0)
            return repr(_to_python_scalar(value))

        condition = re.sub(r"\$\{context\.(\w+)\}",_dollar_brace,condition )
        condition = re.sub(r"\bcontext\.(\w+)\b",_bare,condition )
        return condition
    
    def _resolve_casts(self, condition: str) -> str:
        """Replace ((CastType)globalMap.get("key")) with cast Python value.

        NEW-05 fix: handles Integer, Boolean, String, Long, Float, Double,
        Short, and Byte cast types.
        """
        def _cast_replacer(match: re.Match) -> str:
            cast_type = match.group(1)
            key = match.group(2)
            raw_value = self.global_map.get(key)

            converter = _JAVA_CAST_MAP.get(cast_type)
            if converter is None:
                # Unknown cast type -- return raw value repr
                logger.warning(f"Unknown cast type: {cast_type}")
                return repr(raw_value)

            try:
                if raw_value is None:
                    # Default for missing keys
                    if converter in (int, float):
                        return "0"
                    elif converter is bool:
                        return "False"
                    else:
                        return '"None"'
                converted = converter(raw_value)
                return repr(converted)
            except (ValueError, TypeError):
                if converter in (int, float):
                    return "0"
                elif converter is bool:
                    return "False"
                else:
                    return repr(str(raw_value))

        return _CAST_PATTERN.sub(_cast_replacer, condition)

    def _resolve_global_map_refs(self, condition: str) -> str:
        """Replace globalMap.get("key") / globalMap.get('key') (without cast) with Python value literals."""
        pattern = re.compile(r"globalMap\.get\(['\"]([^'\"]+)['\"]\)")

        def _ref_replacer(match: re.Match) -> str:
            key = match.group(1)
            value = self.global_map.get(key)
            if value is None:
                return "None"
            return repr(_to_python_scalar(value))

        return pattern.sub(_ref_replacer, condition)

    @staticmethod
    def _convert_operators(condition: str) -> str:
        """Convert Java operators to Python equivalents.

        ENG-06 fix: uses regex negative lookahead to prevent != corruption.
        Order of operations:
            1. && -> and
            2. || -> or
            3. != is preserved (regex skips it)
            4. ! (standalone boolean negation) -> not
            5. null -> None
            6. true/false -> True/False
        """
        # Multi-character operators first
        condition = condition.replace("&&", " and ")
        condition = condition.replace("||", " or ")

        # ENG-06: Use negative lookahead to only replace standalone !
        # !(?!=) matches ! that is NOT followed by =
        condition = re.sub(r"!(?!=)", " not ", condition)

        # Literal conversions -- use word boundaries to avoid partial matches
        condition = re.sub(r"\bnull\b", "None", condition)
        condition = re.sub(r"\btrue\b", "True", condition)
        condition = re.sub(r"\bfalse\b", "False", condition)

        return condition

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset trigger manager state for re-execution."""
        self.component_status.clear()
        self.triggered_components.clear()
        logger.debug("Trigger manager reset")
