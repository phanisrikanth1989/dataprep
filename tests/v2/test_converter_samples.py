"""What the converter emits for a component v2 has, v2 must accept.

Every converted sample job and every v1 fixture job is walked. For each
component whose type v2 knows, each config key must be declared (supported,
ignored or refused): an undeclared key would refuse every real job that
carries it. Java expressions are left out of the check: the loader refuses
those on its own, and a user rewrites them.
"""
import glob
import json
from pathlib import Path

import pytest

from src.v2 import components  # noqa: F401 -- registers every component
from src.v2.components.registry import REGISTRY
from src.v2.job.keys import normalize_config

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = sorted(
    glob.glob(str(ROOT / "tests" / "talend_xml_samples" / "converted_jsons" / "*.json"))
    + glob.glob(str(ROOT / "tests" / "fixtures" / "jobs" / "**" / "*.json"), recursive=True)
)


def without_java(value):
    """A config with every Java expression blanked, so only the keys are judged."""
    if isinstance(value, str):
        return "" if value.startswith("{{java}}") else value
    if isinstance(value, dict):
        return {name: without_java(item) for name, item in value.items()}
    if isinstance(value, list):
        return [without_java(item) for item in value]
    return value


def known_components():
    found = []
    for path in SAMPLES:
        try:
            job = json.loads(Path(path).read_text())
        except ValueError:
            continue
        for component in job.get("components") or []:
            if REGISTRY.get(component.get("type")) is not None:
                found.append(pytest.param(component, id=f"{Path(path).stem}:{component.get('id')}"))
    return found


COMPONENTS = known_components()


def test_the_samples_hold_components_v2_knows():
    assert len(COMPONENTS) > 50


@pytest.mark.parametrize("component", COMPONENTS)
def test_every_config_key_the_converter_emits_is_declared(component):
    cls = REGISTRY.get(component["type"])
    config = without_java(component.get("config") or {})
    _, refusals = normalize_config(config, cls.all_keys(), component["id"])
    undeclared = [refusal.key for refusal in refusals if refusal.reason.startswith("unknown config key")]
    assert undeclared == []
