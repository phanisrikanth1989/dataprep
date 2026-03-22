"""Talend-to-V1 converter orchestrator.

Implements the 12-step pipeline that transforms a Talend .item XML file
into a V1 engine JSON configuration.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Handle running as standalone script: add parent directories to path
if __name__ == "__main__":
    current_dir = Path(__file__).parent
    talend_to_v1_dir = current_dir
    converters_dir = talend_to_v1_dir.parent
    src_dir = converters_dir.parent
    
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    
    from converters.talend_to_v1.components.base import ComponentResult, TalendConnection, TalendNode
    from converters.talend_to_v1.components.registry import REGISTRY
    from converters.talend_to_v1.expression_converter import ExpressionConverter
    from converters.talend_to_v1.trigger_mapper import TriggerResult, map_triggers
    from converters.talend_to_v1.type_mapping import convert_type
    from converters.talend_to_v1.validator import ValidationReport, validate_config
    from converters.talend_to_v1.xml_parser import TalendJob, XmlParser
    from converters.talend_to_v1 import components as _components  # noqa: F401
else:
    from .components.base import ComponentResult, TalendConnection, TalendNode
    from .components.registry import REGISTRY
    from .expression_converter import ExpressionConverter
    from .trigger_mapper import TriggerResult, map_triggers
    from .type_mapping import convert_type
    from .validator import ValidationReport, validate_config
    from .xml_parser import TalendJob, XmlParser
    # Import components package to trigger auto-registration of all converters
    from . import components as _components  # noqa: F401

logger = logging.getLogger(__name__)

# Connection types that represent data flows (not triggers)
_FLOW_CONNECTOR_TYPES = frozenset({
    "FLOW", "MAIN", "REJECT", "FILTER",
    "UNIQUE", "DUPLICATE", "ITERATE",
})

# Talend component types that require Java execution
_JAVA_COMPONENT_TYPES = frozenset({
    "tJavaRow", "tJava", "JavaRowComponent",
    "JavaComponent", "JavaRow", "Java",
})


class TalendToV1Converter:
    """Main converter that orchestrates the Talend-to-V1 pipeline."""

    def __init__(self) -> None:
        self._parser = XmlParser()
        self._expr_converter = ExpressionConverter()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def convert_file(self, filepath: str) -> Dict[str, Any]:
        """Convert a Talend .item XML file to a V1 engine config dict.

        Implements the 12-step pipeline:
         1. Parse XML
         2. Convert context variables
         3. Convert components (registry lookup)
         4. Error handling per component
         5. Parse flows from connections
         6. Update component inputs/outputs from flows
         7. Parse triggers
         8. (trigger_mapper already filters skipped components)
         9. Detect subjobs
        10. Detect Java requirement
        11. Validate
        12. Assemble and return config
        """
        # Step 1: Parse XML
        job = self._parser.parse(filepath)
        logger.info("Parsed job '%s' with %d nodes, %d connections",
                     job.job_name, len(job.nodes), len(job.connections))

        # Step 2: Convert context variables (type mapping already done by parser)
        context = self._convert_context(job.context)

        # Steps 3-4: Convert components with error handling
        components_list: List[Dict[str, Any]] = []
        components_map: Dict[str, Dict[str, Any]] = {}
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        for node in job.nodes:
            try:
                converter_cls = REGISTRY.get(node.component_type)
                if converter_cls is not None:
                    converter = converter_cls()
                    result: ComponentResult = converter.convert(
                        node, job.connections, context,
                    )
                    comp = result.component
                    warnings.extend(result.warnings)
                    needs_review.extend(result.needs_review)
                else:
                    comp = self._unsupported(node)
                    logger.info("No converter for '%s' — using unsupported placeholder",
                                node.component_type)
            except Exception as exc:
                logger.error(
                    "Converter error for '%s' (%s) — using unsupported placeholder",
                    node.component_id, node.component_type,
                    exc_info=True,
                )
                comp = self._unsupported(node)
                warnings.append(
                    f"Component '{node.component_id}' ({node.component_type}) "
                    f"failed conversion: {exc}"
                )

            components_list.append(comp)
            components_map[comp["id"]] = comp

        # Step 5: Parse flows from connections
        flows = self._parse_flows(job.connections)

        # Step 6: Update component inputs/outputs from flows
        for flow in flows:
            self._update_component_connections(components_map, flow)

        # Step 7-8: Parse triggers (trigger_mapper filters skipped components)
        component_ids: Set[str] = set(components_map.keys())
        trigger_result: TriggerResult = map_triggers(job.connections, component_ids)
        triggers = trigger_result.triggers
        warnings.extend(trigger_result.warnings)
        needs_review.extend(trigger_result.needs_review)

        # Step 9: Detect subjobs
        subjobs = self._detect_subjobs(components_map, flows)

        # Step 10: Detect Java requirement
        java_required = self._detect_java_requirement(components_list)

        # Assemble config
        config: Dict[str, Any] = {
            "job_name": job.job_name,
            "job_type": job.job_type,
            "default_context": job.default_context,
            "context": context,
            "components": components_list,
            "flows": flows,
            "triggers": triggers,
            "subjobs": subjobs,
            "java_config": {
                "enabled": java_required,
                "routines": job.routines,
                "libraries": job.libraries,
            },
        }

        # Step 11: Validate
        report: ValidationReport = validate_config(config)
        config["_validation"] = {
            "valid": report.valid,
            "summary": report.summary,
            "issues": [
                {
                    "severity": issue.severity,
                    "component_id": issue.component_id,
                    "field": issue.field,
                    "message": issue.message,
                }
                for issue in report.issues
            ],
        }

        if warnings:
            config["_warnings"] = warnings
        if needs_review:
            config["_needs_review"] = needs_review

        logger.info("Conversion complete: %d components, %d flows, %d triggers, "
                     "%d subjobs, java=%s, validation=%s",
                     len(components_list), len(flows), len(triggers),
                     len(subjobs), java_required, report.summary)

        return config

    # ------------------------------------------------------------------
    # Step 2: Context conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_context(
        context: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        """Ensure context parameter types are mapped to Python types.

        The XmlParser already applies convert_type during parsing, so
        this is a pass-through.  Kept as a hook for any future
        post-processing.
        """
        return context

    # ------------------------------------------------------------------
    # Step 3-4: Unsupported placeholder
    # ------------------------------------------------------------------

    @staticmethod
    def _unsupported(node: TalendNode) -> Dict[str, Any]:
        """Create an unsupported placeholder component dict."""
        return {
            "id": node.component_id,
            "type": node.component_type,
            "original_type": node.component_type,
            "position": node.position,
            "config": {},
            "schema": {},
            "inputs": [],
            "outputs": [],
            "_unsupported": True,
        }

    # ------------------------------------------------------------------
    # Step 5: Flow parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_flows(
        connections: List[TalendConnection],
    ) -> List[Dict[str, Any]]:
        """Parse data-flow connections into v1 flow dicts."""
        flows: List[Dict[str, Any]] = []

        for conn in connections:
            if conn.connector_type not in _FLOW_CONNECTOR_TYPES:
                continue
            if not conn.source or not conn.target:
                continue

            flows.append({
                "name": conn.name or conn.source,
                "from": conn.source,
                "to": conn.target,
                "type": conn.connector_type.lower(),
            })

        return flows

    # ------------------------------------------------------------------
    # Step 6: Update component inputs/outputs
    # ------------------------------------------------------------------

    @staticmethod
    def _update_component_connections(
        components_map: Dict[str, Dict[str, Any]],
        flow: Dict[str, Any],
    ) -> None:
        """Add flow name to source's outputs and target's inputs."""
        from_comp = flow["from"]
        to_comp = flow["to"]
        flow_name = flow["name"]

        if from_comp in components_map:
            if flow_name not in components_map[from_comp]["outputs"]:
                components_map[from_comp]["outputs"].append(flow_name)

        if to_comp in components_map:
            if flow_name not in components_map[to_comp]["inputs"]:
                components_map[to_comp]["inputs"].append(flow_name)

    # ------------------------------------------------------------------
    # Step 9: Subjob detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_subjobs(
        components_map: Dict[str, Dict[str, Any]],
        flows: List[Dict[str, Any]],
    ) -> Dict[str, List[str]]:
        """Detect subjobs via DFS on flow adjacency graph."""
        subjobs: Dict[str, List[str]] = {}
        visited: Set[str] = set()
        subjob_counter = 1

        # Build adjacency lists (undirected)
        connections: Dict[str, List[str]] = {}
        for flow in flows:
            from_comp = flow["from"]
            to_comp = flow["to"]

            if from_comp not in connections:
                connections[from_comp] = []
            connections[from_comp].append(to_comp)

            if to_comp not in connections:
                connections[to_comp] = []

        # Find connected components via DFS
        for comp_id in components_map:
            if comp_id in visited:
                continue

            subjob_components: List[str] = []
            stack = [comp_id]

            while stack:
                current = stack.pop()
                if current in visited:
                    continue

                visited.add(current)
                subjob_components.append(current)

                # Forward edges
                if current in connections:
                    for neighbor in connections[current]:
                        if neighbor not in visited:
                            stack.append(neighbor)

                # Reverse edges
                for from_comp, to_comps in connections.items():
                    if current in to_comps and from_comp not in visited:
                        stack.append(from_comp)

            if subjob_components:
                subjob_id = f"subjob_{subjob_counter}"
                subjobs[subjob_id] = subjob_components
                subjob_counter += 1

        return subjobs

    # ------------------------------------------------------------------
    # Step 10: Java detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_java_requirement(components: List[Dict[str, Any]]) -> bool:
        """Detect if Java/Groovy execution is required.

        Checks for:
        - Java-specific component types
        - ``{{java}}`` markers anywhere in component config
        """
        for component in components:
            component_type = component.get("type", "")

            # Check for Java component types
            if component_type in _JAVA_COMPONENT_TYPES:
                logger.info("Java required: found %s component", component_type)
                return True

            # Check for {{java}} markers in config (recursive scan)
            config = component.get("config", {})
            if TalendToV1Converter._has_java_expressions(config):
                logger.info(
                    "Java required: component '%s' contains {{java}} expressions",
                    component.get("id"),
                )
                return True

        return False

    @staticmethod
    def _has_java_expressions(obj: Any) -> bool:
        """Recursively check if *obj* contains ``{{java}}`` markers."""
        if isinstance(obj, dict):
            for value in obj.values():
                if TalendToV1Converter._has_java_expressions(value):
                    return True
        elif isinstance(obj, list):
            for item in obj:
                if TalendToV1Converter._has_java_expressions(item):
                    return True
        elif isinstance(obj, str):
            if "{{java}}" in obj:
                return True
        return False


# ------------------------------------------------------------------
# Convenience function
# ------------------------------------------------------------------


def convert_job(
    input_path: str,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Convert a Talend .item file and optionally write JSON output.

    Parameters
    ----------
    input_path:
        Path to the Talend ``.item`` XML file.
    output_path:
        If provided, the resulting config is written as JSON to this path.

    Returns
    -------
    dict
        The V1 engine configuration dict.
    """
    converter = TalendToV1Converter()
    config = converter.convert_file(input_path)

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        logger.info("Wrote V1 config to %s", out)

    return config


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python converter.py <input_path> [output_path]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        result = convert_job(input_file, output_file)
        if not output_file:
            print(json.dumps(result, indent=2))
    except Exception as e:
        logger.exception("Conversion failed")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
