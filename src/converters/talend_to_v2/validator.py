"""Post-conversion validator for Talend-to-V2 converted configs.

Validates reference integrity, tMap-specific rules, expression quality,
and conversion quality markers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

# Java methods that should not appear in V2 expressions
_JAVA_METHOD_PATTERN = re.compile(
    r"\.\b(substring|equals|equalsIgnoreCase|indexOf|toLowerCase|toUpperCase"
    r"|trim|length|charAt|startsWith|endsWith|replace|replaceAll|matches"
    r"|compareTo|contains|isEmpty|split|valueOf|parseInt|parseLong"
    r"|parseFloat|parseDouble|toString)\b\s*\("
)

# Uppercase Var. prefix (should be lowercase var. in V2)
_UPPERCASE_VAR_PATTERN = re.compile(r"\bVar\.")


@dataclass
class ValidationIssue:
    """A single validation finding."""

    severity: str  # "error" | "warning" | "info"
    component_id: str  # Component that has the issue, or "" for global
    field: str  # Field name with the issue
    message: str


@dataclass
class ValidationReport:
    """Result of validating a V2 config."""

    valid: bool  # True if no errors (warnings OK)
    issues: List[ValidationIssue]
    summary: str  # Human-readable summary


def validate_v2_config(config: Dict[str, Any]) -> ValidationReport:
    """Run all validation layers on a V2 config dict and return a report."""
    issues: List[ValidationIssue] = []

    _validate_reference_integrity(config, issues)
    _validate_tmap(config, issues)
    _validate_expressions(config, issues)
    _validate_conversion_quality(config, issues)
    _validate_triggers(config, issues)

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

    if parts:
        summary = f"Validation: {', '.join(parts)}"
    else:
        summary = "Validation passed with no issues"

    return ValidationReport(valid=valid, issues=issues, summary=summary)


# ---------------------------------------------------------------------------
# Layer 1: Reference Integrity
# ---------------------------------------------------------------------------


def _validate_reference_integrity(
    config: Dict[str, Any],
    issues: List[ValidationIssue],
) -> None:
    components = config.get("components", [])
    flows = config.get("flows", [])

    component_ids = {c["id"] for c in components if "id" in c}

    # Check flow source/target references
    for flow in flows:
        source = flow.get("source", "")
        target = flow.get("target", "")
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

    # Check for orphan components (no flows or triggers)
    referenced_ids = set()
    for flow in flows:
        referenced_ids.add(flow.get("source", ""))
        referenced_ids.add(flow.get("target", ""))

    for trigger in config.get("triggers", []):
        referenced_ids.add(trigger.get("source", ""))
        referenced_ids.add(trigger.get("target", ""))

    for comp in components:
        comp_id = comp.get("id", "")
        if comp_id and comp_id not in referenced_ids:
            issues.append(ValidationIssue(
                severity="warning",
                component_id=comp_id,
                field="flows",
                message=f"Orphan component '{comp_id}' has no flows or triggers",
            ))


def _validate_triggers(
    config: Dict[str, Any],
    issues: List[ValidationIssue],
) -> None:
    """Validate trigger source/target reference existing components."""
    triggers = config.get("triggers", [])
    if not triggers:
        return

    component_ids = {c["id"] for c in config.get("components", []) if "id" in c}

    for trigger in triggers:
        source = trigger.get("source", "")
        target = trigger.get("target", "")
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


# ---------------------------------------------------------------------------
# Layer 2: tMap-Specific
# ---------------------------------------------------------------------------


def _validate_tmap(
    config: Dict[str, Any],
    issues: List[ValidationIssue],
) -> None:
    flows = config.get("flows", [])

    for comp in config.get("components", []):
        if comp.get("type") != "map":
            continue

        comp_id = comp.get("id", "")
        comp_config = comp.get("config", {})
        lookups = comp_config.get("lookups", [])

        # Collect input flow names targeting this component
        input_flow_names = {
            f.get("input") or f.get("name", "")
            for f in flows
            if f.get("target") == comp_id
        }

        for lookup in lookups:
            lookup_name = lookup.get("name", "")

            # Check join keys are non-empty
            for key in lookup.get("keys", []):
                if not key.get("main", "").strip():
                    issues.append(ValidationIssue(
                        severity="error",
                        component_id=comp_id,
                        field=f"lookups.{lookup_name}.keys",
                        message=f"Lookup '{lookup_name}' has empty main join key",
                    ))
                if not key.get("lookup", "").strip():
                    issues.append(ValidationIssue(
                        severity="error",
                        component_id=comp_id,
                        field=f"lookups.{lookup_name}.keys",
                        message=f"Lookup '{lookup_name}' has empty lookup join key",
                    ))

            # Check lookup has a matching input flow
            if lookup_name not in input_flow_names:
                issues.append(ValidationIssue(
                    severity="warning",
                    component_id=comp_id,
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
    for comp in config.get("components", []):
        if comp.get("type") != "map":
            continue

        comp_id = comp.get("id", "")
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
                    component_id=comp_id,
                    field=field_path,
                    message=f"Possible leftover Java method in expression: {expr!r}",
                ))

            # Check for uppercase Var. prefix
            if _UPPERCASE_VAR_PATTERN.search(expr):
                issues.append(ValidationIssue(
                    severity="warning",
                    component_id=comp_id,
                    field=field_path,
                    message=f"Uppercase 'Var.' should be lowercase 'var.' in V2: {expr!r}",
                ))


# ---------------------------------------------------------------------------
# Layer 4: Conversion Quality
# ---------------------------------------------------------------------------


def _validate_conversion_quality(
    config: Dict[str, Any],
    issues: List[ValidationIssue],
) -> None:
    for comp in config.get("components", []):
        comp_id = comp.get("id", "")

        # Top-level _unsupported marker
        if comp.get("_unsupported"):
            issues.append(ValidationIssue(
                severity="info",
                component_id=comp_id,
                field="type",
                message=f"Component '{comp_id}' is unsupported (type={comp.get('type', '?')})",
            ))

        # Config-level markers
        comp_config = comp.get("config", {})
        if isinstance(comp_config, dict):
            if comp_config.get("_needs_rewrite"):
                issues.append(ValidationIssue(
                    severity="info",
                    component_id=comp_id,
                    field="config._needs_rewrite",
                    message=f"Component '{comp_id}' needs manual rewrite",
                ))

            if comp_config.get("_review"):
                issues.append(ValidationIssue(
                    severity="info",
                    component_id=comp_id,
                    field="config._review",
                    message=f"Component '{comp_id}' flagged for review: {comp_config['_review']}",
                ))
