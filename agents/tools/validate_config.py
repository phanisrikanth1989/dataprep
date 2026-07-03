"""Validate a component config dict against its curated schema (pre-engine gate)."""
from __future__ import annotations

from agents.tools.component_schema import BASE_KEYS, IGNORED_KEYS, load_schema, resolve_enum_ref

_PY_TYPES = {"str": str, "int": int, "float": (int, float), "bool": bool, "list": list, "dict": dict}


def _valid_values(spec: dict) -> set | None:
    if "enum" in spec:
        return set(spec["enum"])
    if "enum_ref" in spec:
        return resolve_enum_ref(spec["enum_ref"])
    return None


def _check_key(name: str, value, spec: dict, errors: list, strict: bool = False) -> None:
    expected = spec.get("type")
    # A bool must never satisfy an int/float field (isinstance(True, int) is True).
    if expected in ("int", "float") and isinstance(value, bool):
        errors.append(f"key {name!r}: expected {expected}, got bool")
        return
    py_type = _PY_TYPES.get(expected) if expected else None
    if py_type is not None and not isinstance(value, py_type):
        errors.append(f"key {name!r}: expected {expected}, got {type(value).__name__}")
        return
    allowed = _valid_values(spec)
    if allowed is not None:
        try:
            hash(value)  # unhashable (list/dict) values can never be a valid enum choice
        except TypeError:
            errors.append(f"key {name!r}: value is not a valid {sorted(allowed, key=str)} choice")
        else:
            if value not in allowed:
                errors.append(f"key {name!r}: value {value!r} not in allowed {sorted(allowed, key=str)}")
    if spec.get("type") == "list":
        if spec.get("non_empty") and len(value) == 0:
            errors.append(f"key {name!r}: must not be empty")
        item_keys = spec.get("item_keys")
        if item_keys:
            for i, item in enumerate(value):
                if not isinstance(item, dict):
                    errors.append(f"key {name!r}[{i}]: expected dict item")
                    continue
                for sub, subspec in item_keys.items():
                    if subspec.get("required") and sub not in item:
                        errors.append(f"key {name!r}[{i}]: missing required {sub!r}")
                    elif sub in item:
                        _check_key(f"{name}[{i}].{sub}", item[sub], subspec, errors, strict)
                if strict:
                    for sub in item:
                        if sub not in item_keys and sub not in BASE_KEYS and sub not in IGNORED_KEYS:
                            errors.append(f"key {name!r}[{i}]: unknown sub-key {sub!r}")


def _required(name: str, spec: dict, config: dict) -> bool:
    if spec.get("required"):
        return True
    cond = spec.get("required_when")
    return bool(cond) and all(config.get(k) == v for k, v in cond.items())


def validate_config(component_type: str, config: dict, strict: bool = True) -> list:
    """Return a list of config errors (empty = valid). strict flags unknown keys."""
    schema = load_schema(component_type)
    keys = schema["keys"]
    errors: list = []
    if strict:
        for name in config:
            if name not in keys and name not in BASE_KEYS and name not in IGNORED_KEYS:
                errors.append(f"unknown config key {name!r} for {component_type}")
    for name, spec in keys.items():
        if _required(name, spec, config) and name not in config:
            errors.append(f"missing required config key {name!r}")
        elif name in config:
            _check_key(name, config[name], spec, errors, strict)
    return errors


def main(argv=None) -> int:
    """CLI: validate a component config JSON file against its curated schema."""
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description="Validate a component config against its schema.")
    parser.add_argument("--type", required=True, help="component type (or alias)")
    parser.add_argument("--config", required=True, help="path to a JSON file holding the component config dict")
    parser.add_argument("--loose", action="store_true", help="strict=False (skip the unknown-key check)")
    args = parser.parse_args(argv)
    try:
        with open(args.config, encoding="utf-8") as fh:
            config = json.load(fh)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"cannot read config {args.config!r}: {exc}\n")
        return 2
    if not isinstance(config, dict):
        sys.stderr.write(f"config in {args.config!r} is not a JSON object\n")
        return 2
    errors = validate_config(args.type, config, strict=not args.loose)
    sys.stdout.write(json.dumps({"type": args.type, "valid": not errors, "errors": errors}) + "\n")
    return 0 if not errors else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
