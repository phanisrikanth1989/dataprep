"""Config dataclasses + validation for the Map component.

Mirrors the JSON shape produced by the converter (verified from
tests/fixtures/jobs/transform/map_with_lookup.json and
tests/talend_xml_samples/converted_jsons/Job_tMap_0.1.json).

See docs/superpowers/specs/2026-05-18-tmap-rewrite-design.md Section 11
for the full contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.v1.engine.exceptions import ConfigurationError


_JAVA_MARKER = "{{java}}"


@dataclass
class ColumnCfg:
    name: str
    expression: str
    type: str
    nullable: bool = True
    length: int = -1
    precision: int = -1
    date_pattern: str = ""


@dataclass
class JoinKeyCfg:
    lookup_column: str
    expression: str
    type: str
    nullable: bool = True
    operator: str = "="


@dataclass
class MainInputCfg:
    name: str
    filter: str = ""
    activate_filter: bool = False
    matching_mode: str = "UNIQUE_MATCH"
    lookup_mode: str = "LOAD_ONCE"


@dataclass
class LookupCfg:
    name: str
    join_keys: list[JoinKeyCfg]
    join_mode: str = "LEFT_OUTER_JOIN"
    matching_mode: str = "UNIQUE_MATCH"
    lookup_mode: str = "LOAD_ONCE"
    filter: str = ""
    activate_filter: bool = False


@dataclass
class VariableCfg:
    name: str
    expression: str
    type: str
    nullable: bool = True


@dataclass
class OutputCfg:
    name: str
    columns: list[ColumnCfg]
    is_reject: bool = False
    inner_join_reject: bool = False
    catch_output_reject: bool = False
    filter: str = ""
    activate_filter: bool = False


@dataclass
class MapConfig:
    main: MainInputCfg
    lookups: list[LookupCfg]
    variables: list[VariableCfg]
    outputs: list[OutputCfg]
    die_on_error: bool = True
    enable_auto_convert_type: bool = False
    label: str = ""


def parse_config(raw: dict[str, Any]) -> MapConfig:
    """Parse the raw JSON config dict into MapConfig dataclasses.

    Does NOT validate semantics -- only constructs the typed shape. Use
    validate_config() for semantic checks.
    """
    inputs = raw.get("inputs") or {}
    main_raw = inputs.get("main") or {}
    main = MainInputCfg(
        name=main_raw.get("name", ""),
        filter=main_raw.get("filter", ""),
        activate_filter=bool(main_raw.get("activate_filter", False)),
        matching_mode=main_raw.get("matching_mode", "UNIQUE_MATCH"),
        lookup_mode=main_raw.get("lookup_mode", "LOAD_ONCE"),
    )

    lookups: list[LookupCfg] = []
    for lk in inputs.get("lookups") or []:
        join_keys = [
            JoinKeyCfg(
                lookup_column=jk.get("lookup_column", ""),
                expression=jk.get("expression", ""),
                type=jk.get("type", "str"),
                nullable=bool(jk.get("nullable", True)),
                operator=jk.get("operator", "="),
            )
            for jk in lk.get("join_keys") or []
        ]
        lookups.append(LookupCfg(
            name=lk.get("name", ""),
            join_keys=join_keys,
            join_mode=lk.get("join_mode", "LEFT_OUTER_JOIN"),
            matching_mode=lk.get("matching_mode", "UNIQUE_MATCH"),
            lookup_mode=lk.get("lookup_mode", "LOAD_ONCE"),
            filter=lk.get("filter", ""),
            activate_filter=bool(lk.get("activate_filter", False)),
        ))

    variables = [
        VariableCfg(
            name=v.get("name", ""),
            expression=v.get("expression", ""),
            type=v.get("type", "str"),
            nullable=bool(v.get("nullable", True)),
        )
        for v in raw.get("variables") or []
    ]

    outputs = []
    for o in raw.get("outputs") or []:
        cols = [
            ColumnCfg(
                name=c.get("name", ""),
                expression=c.get("expression", ""),
                type=c.get("type", "str"),
                nullable=bool(c.get("nullable", True)),
                length=int(c.get("length", -1)),
                precision=int(c.get("precision", -1)),
                date_pattern=c.get("date_pattern", ""),
            )
            for c in o.get("columns") or []
        ]
        outputs.append(OutputCfg(
            name=o.get("name", ""),
            columns=cols,
            is_reject=bool(o.get("is_reject", False)),
            inner_join_reject=bool(o.get("inner_join_reject", False)),
            catch_output_reject=bool(o.get("catch_output_reject", False)),
            filter=o.get("filter", ""),
            activate_filter=bool(o.get("activate_filter", False)),
        ))

    return MapConfig(
        main=main,
        lookups=lookups,
        variables=variables,
        outputs=outputs,
        die_on_error=bool(raw.get("die_on_error", True)),
        enable_auto_convert_type=bool(raw.get("enable_auto_convert_type", False)),
        label=raw.get("label", ""),
    )


def has_any_java_marker(cfg: MapConfig) -> bool:
    """Return True if any expression-bearing field has a {{java}} prefix."""
    if cfg.main.filter.startswith(_JAVA_MARKER):
        return True
    for lk in cfg.lookups:
        if lk.filter.startswith(_JAVA_MARKER):
            return True
        for jk in lk.join_keys:
            if jk.expression.startswith(_JAVA_MARKER):
                return True
    for v in cfg.variables:
        if v.expression.startswith(_JAVA_MARKER):
            return True
    for o in cfg.outputs:
        if o.filter.startswith(_JAVA_MARKER):
            return True
        for c in o.columns:
            if c.expression.startswith(_JAVA_MARKER):
                return True
    return False


def validate_config(cfg: MapConfig, java_bridge_available: bool) -> None:
    """Semantic validation of the parsed config.

    Args:
        cfg: Parsed config.
        java_bridge_available: True if a JavaBridge instance is attached
            to the component. Required if any {{java}} marker present.

    Raises:
        ConfigurationError: on any structural / semantic problem.
    """
    if not cfg.main.name:
        raise ConfigurationError("Missing inputs.main.name")
    if not cfg.outputs:
        raise ConfigurationError("At least one output is required")
    for i, out in enumerate(cfg.outputs):
        if not out.name:
            raise ConfigurationError(f"Output [{i}] missing 'name'")
        if not out.columns:
            raise ConfigurationError(
                f"Output '{out.name}' has no columns"
            )
    for i, lk in enumerate(cfg.lookups):
        if not lk.name:
            raise ConfigurationError(f"Lookup [{i}] missing 'name'")
        for j, jk in enumerate(lk.join_keys):
            if not jk.lookup_column:
                raise ConfigurationError(
                    f"Lookup '{lk.name}' join_key [{j}] missing 'lookup_column'"
                )
            if not jk.expression:
                raise ConfigurationError(
                    f"Lookup '{lk.name}' join_key [{j}] missing 'expression'"
                )

    if has_any_java_marker(cfg) and not java_bridge_available:
        raise ConfigurationError(
            "Config contains {{java}} expressions but Java bridge is "
            "unavailable. Set java_config.enabled=true in the job config "
            "or remove Java expressions."
        )
