"""Post-conversion validator for Talend-to-V1 converted configs.

Validates reference integrity, component-specific rules, expression quality,
and conversion quality markers.
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Java methods that should not appear in converted expressions
_JAVA_METHOD_PATTERN = re.compile(
    r"\.\b(substring|equals|equalsIgnoreCase|indexOf|toLowerCase|toUpperCase"
    r"|trim|length|charAt|startsWith|endsWith|replace|replaceAll|matches"
    r"|compareTo|contains|isEmpty|split|valueOf|parseInt|parseLong"
    r"|parseFloat|parseDouble|toString)\b\s*\("
)


@dataclass
class ValidationIssue:
    """A single validation finding."""

    severity: str  # "error" | "warning" | "info"
    component_id: str  # Component with the issue, or "" for global
    field: str  # Field name with the issue
    message: str


@dataclass
class ValidationReport:
    """Result of validating a v1 config."""

    valid: bool  # True if no errors (warnings OK)
    issues: List[ValidationIssue]
    summary: str  # Human-readable summary


def validate_config(config: Dict[str, Any]) -> ValidationReport:
    """Run all validation layers on a v1 config dict and return a report."""
    issues: List[ValidationIssue] = []

    _validate_reference_integrity(config, issues)
    _validate_tmap(config, issues)
    _validate_expressions(config, issues)
    _validate_conversion_quality(config, issues)

    error_count = sum(1 for i in issues if i.severity == "error")
    warning_count = sum(1 for i in issues if i.severity == "warning")
    info_count = sum(1 for i in issues if i.severity == "info")

    valid = error_count == 0

    parts: List[str] = []
    if error_count:
        parts.append(f"{error_count} error(s)")
    if warning_count:
        parts.append(f"{warning_count} warning(s)")
    if info_count:
        parts.append(f"{info_count} info(s)")

    summary = f"Validation: {', '.join(parts)}" if parts else "Validation passed with no issues"

    return ValidationReport(valid=valid, issues=issues, summary=summary)


# ---------------------------------------------------------------------------
# Layer 1: Reference Integrity
# ---------------------------------------------------------------------------


def _validate_reference_integrity(
    config: Dict[str, Any],
    issues: List[ValidationIssue],
) -> None:
    """Check that flow/trigger from/to references point to existing components."""
    components = config.get("components", [])
    flows = config.get("flows", [])

    component_ids = {c["id"] for c in components if "id" in c}

    # Check flow from/to references (v1 uses "from"/"to" keys)
    for flow in flows:
        source = flow.get("from", "")
        target = flow.get("to", "")
        flow_name = flow.get("name", "?")

        if source and source not in component_ids:
            issues.append(ValidationIssue(
                severity="error",
                component_id="",
                field="flows",
                message=f"Flow '{flow_name}' references non-existent source '{source}'",
            ))

        if target and target not in component_ids:
            issues.append(ValidationIssue(
                severity="error",
                component_id="",
                field="flows",
                message=f"Flow '{flow_name}' references non-existent target '{target}'",
            ))

    # Check trigger from/to references (v1 uses "from"/"to" keys)
    for trigger in config.get("triggers", []):
        source = trigger.get("from", "")
        target = trigger.get("to", "")
        trigger_type = trigger.get("type", "?")

        if source and source not in component_ids:
            issues.append(ValidationIssue(
                severity="error",
                component_id="",
                field="triggers",
                message=(
                    f"Trigger ({trigger_type}) references non-existent "
                    f"source '{source}'"
                ),
            ))

        if target and target not in component_ids:
            issues.append(ValidationIssue(
                severity="error",
                component_id="",
                field="triggers",
                message=(
                    f"Trigger ({trigger_type}) references non-existent "
                    f"target '{target}'"
                ),
            ))

    # Check for orphan components (no flows or triggers reference them)
    referenced_ids: set[str] = set()
    for flow in flows:
        if flow.get("from"):
            referenced_ids.add(flow["from"])
        if flow.get("to"):
            referenced_ids.add(flow["to"])

    for trigger in config.get("triggers", []):
        if trigger.get("from"):
            referenced_ids.add(trigger["from"])
        if trigger.get("to"):
            referenced_ids.add(trigger["to"])

    for comp in components:
        component_id = comp.get("id", "")
        if component_id and component_id not in referenced_ids:
            issues.append(ValidationIssue(
                severity="warning",
                component_id=component_id,
                field="flows",
                message=f"Orphan component '{component_id}' has no flows or triggers",
            ))


# ---------------------------------------------------------------------------
# Layer 2: tMap-Specific (v1 type is "Map")
# ---------------------------------------------------------------------------


def _validate_tmap(
    config: Dict[str, Any],
    issues: List[ValidationIssue],
) -> None:
    """Validate Map components: join keys and lookup input flows."""
    flows = config.get("flows", [])

    for comp in config.get("components", []):
        if comp.get("type") != "Map":
            continue

        component_id = comp.get("id", "")
        comp_config = comp.get("config", {})
        lookups = comp_config.get("lookups", [])

        # Collect input flow names targeting this component (v1 uses "to")
        input_flow_names = {
            f.get("input") or f.get("name", "")
            for f in flows
            if f.get("to") == component_id
        }

        for lookup in lookups:
            lookup_name = lookup.get("name", "")

            # Check join keys are non-empty
            for key in lookup.get("keys", []):
                if not key.get("main", "").strip():
                    issues.append(ValidationIssue(
                        severity="error",
                        component_id=component_id,
                        field=f"lookups.{lookup_name}.keys",
                        message=f"Lookup '{lookup_name}' has empty main join key",
                    ))
                if not key.get("lookup", "").strip():
                    issues.append(ValidationIssue(
                        severity="error",
                        component_id=component_id,
                        field=f"lookups.{lookup_name}.keys",
                        message=f"Lookup '{lookup_name}' has empty lookup join key",
                    ))

            # Check lookup has a matching input flow
            if lookup_name not in input_flow_names:
                issues.append(ValidationIssue(
                    severity="warning",
                    component_id=component_id,
                    field=f"lookups.{lookup_name}",
                    message=f"Lookup '{lookup_name}' has no matching input flow",
                ))


# ---------------------------------------------------------------------------
# Layer 3: Expression Validation
# ---------------------------------------------------------------------------


def _validate_expressions(
    config: Dict[str, Any],
    issues: List[ValidationIssue],
) -> None:
    """Scan Map component expressions for leftover Java method calls."""
    for comp in config.get("components", []):
        if comp.get("type") != "Map":
            continue

        component_id = comp.get("id", "")
        comp_config = comp.get("config", {})

        # Collect all expressions from outputs and variables
        expressions: List[tuple[str, str]] = []  # (field_path, expr)

        for output in comp_config.get("outputs", []):
            out_name = output.get("name", "")
            for col in output.get("columns", []):
                expr = col.get("expression", "")
                if expr:
                    expressions.append(
                        (f"outputs.{out_name}.columns.{col.get('name', '')}", expr)
                    )
            filt = output.get("filter", "")
            if filt:
                expressions.append((f"outputs.{out_name}.filter", filt))

        for var in comp_config.get("variables", []):
            expr = var.get("expression", "")
            if expr:
                expressions.append((f"variables.{var.get('name', '')}", expr))

        for field_path, expr in expressions:
            # Check for leftover Java methods
            if _JAVA_METHOD_PATTERN.search(expr):
                issues.append(ValidationIssue(
                    severity="warning",
                    component_id=component_id,
                    field=field_path,
                    message=f"Possible leftover Java method in expression: {expr!r}",
                ))


# ---------------------------------------------------------------------------
# Layer 4: Conversion Quality
# ---------------------------------------------------------------------------


def _validate_conversion_quality(
    config: Dict[str, Any],
    issues: List[ValidationIssue],
) -> None:
    """Flag unsupported components, missing config, and empty schemas."""
    for comp in config.get("components", []):
        component_id = comp.get("id", "")

        # Top-level _unsupported marker
        if comp.get("_unsupported"):
            issues.append(ValidationIssue(
                severity="info",
                component_id=component_id,
                field="type",
                message=f"Component '{component_id}' is unsupported (type={comp.get('type', '?')})",
            ))

        # Empty or missing config
        comp_config = comp.get("config")
        if not comp_config:
            issues.append(ValidationIssue(
                severity="warning",
                component_id=component_id,
                field="config",
                message=f"Component '{component_id}' has empty or missing config",
            ))

        # Missing schema
        if not comp.get("schema"):
            issues.append(ValidationIssue(
                severity="warning",
                component_id=component_id,
                field="schema",
                message=f"Component '{component_id}' has missing schema",
            ))

        # Config-level markers
        if isinstance(comp_config, dict):
            if comp_config.get("_needs_rewrite"):
                issues.append(ValidationIssue(
                    severity="info",
                    component_id=component_id,
                    field="config._needs_rewrite",
                    message=f"Component '{component_id}' needs manual rewrite",
                ))

            if comp_config.get("_review"):
                issues.append(ValidationIssue(
                    severity="info",
                    component_id=component_id,
                    field="config._review",
                    message=f"Component '{component_id}' flagged for review: {comp_config['_review']}",
                ))
