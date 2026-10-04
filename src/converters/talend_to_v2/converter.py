"""Orchestrator: converts a Talend .item XML file to a V2 JSON config."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from .type_mapping import convert_context_type
from .validator import ValidationReport, validate_v2_config
from .trigger_mapper import map_triggers
from .xml_parser import TalendJob, XmlParser

# Trigger registration of all component converters
from .components import (  # noqa: F401
    aggregate,
    context_load,
    file_input,
    file_input_excel,
    java_row,
    map,
    transform,
)
from .components.registry import REGISTRY

logger = logging.getLogger(__name__)


@dataclass
class ConversionResult:
    """Result of converting a Talend job to V2 format."""

    config: Dict[str, Any]
    report: ValidationReport = field(default_factory=lambda: ValidationReport(valid=True, issues=[], summary=""))
    warnings: List[str] = field(default_factory=list)
    needs_review: List[Dict[str, Any]] = field(default_factory=list)


class TalendToV2Converter:
    """Converts a Talend .item XML file into a V2 engine configuration dict."""

    def __init__(self, xml_path: str) -> None:
        self._xml_path = xml_path

    def convert(self) -> ConversionResult:
        """Run the full conversion pipeline and return a :class:`ConversionResult`."""
        job = XmlParser().parse(self._xml_path)

        all_warnings: List[str] = []
        all_needs_review: List[Dict[str, Any]] = []
        components: List[Dict[str, Any]] = []
        flows: List[Dict[str, Any]] = []

        # --- Context variables ---
        context = self._convert_context(job)

        # --- Components ---
        for node in job.nodes:
            converter_cls = REGISTRY.get(node.component_type)

            if converter_cls is None:
                # Unsupported component -> placeholder
                msg = (
                    f"Unsupported component type {node.component_type!r} "
                    f"(id={node.component_id!r}) — added as placeholder"
                )
                logger.warning(msg)
                all_warnings.append(msg)
                components.append(
                    {
                        "id": node.component_id,
                        "type": node.component_type,
                        "_unsupported": True,
                    }
                )
                continue

            result = converter_cls().convert(node, job.connections, context)
            components.append(result.component)
            flows.extend(result.flows)
            all_warnings.extend(result.warnings)
            all_needs_review.extend(result.needs_review)

        # --- Deduplicate flows ---
        flows = self._deduplicate_flows(flows)

        # --- Triggers ---
        trigger_result = map_triggers(job.connections)
        triggers = trigger_result.triggers
        all_warnings.extend(trigger_result.warnings)
        all_needs_review.extend(trigger_result.needs_review)

        # --- Assemble config ---
        config: Dict[str, Any] = {
            "name": job.job_name,
            "version": "2.0",
            "context": context,
            "components": components,
            "flows": flows,
            "triggers": triggers,
            "_conversion_metadata": {
                "source": "talend_xml",
                "warnings": all_warnings,
                "needs_review": all_needs_review,
            },
        }

        # --- Validate ---
        report = validate_v2_config(config)

        return ConversionResult(
            config=config,
            report=report,
            warnings=all_warnings,
            needs_review=all_needs_review,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_context(job: TalendJob) -> Dict[str, Dict[str, str]]:
        """Convert Talend context parameters to V2 typed context variables."""
        result: Dict[str, Dict[str, str]] = {}
        for name, param in job.context.items():
            result[name] = {
                "value": param.value,
                "type": convert_context_type(param.type),
            }
        return result

    @staticmethod
    def _deduplicate_flows(flows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate flows, preferring the version with more metadata.

        Two flows with the same (name, source, target) are considered duplicates.
        When duplicates exist, the flow with input/output routing info is kept.
        """
        by_key: Dict[Tuple[str, ...], Dict[str, Any]] = {}
        for flow in flows:
            key = (
                flow.get("name", ""),
                flow.get("source", ""),
                flow.get("target", ""),
            )
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = flow
            else:
                # Prefer the flow with more routing metadata (input/output)
                new_has = bool(flow.get("input") or flow.get("output"))
                old_has = bool(existing.get("input") or existing.get("output"))
                if new_has and not old_has:
                    by_key[key] = flow
        return list(by_key.values())
