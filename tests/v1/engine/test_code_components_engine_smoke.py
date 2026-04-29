"""Engine-level smoke tests for the four Phase 8 code components.

Phase 8 Plan 05 Task 2 (TEST-07) -- verifies each rewritten component is
correctly wired into ``ETLEngine`` and runs end-to-end via
``ETLEngine.execute()`` against a tiny in-memory job configuration. These
tests catch integration regressions that pure-component unit tests miss
(REGISTRY decorator wiring, ``COMPONENT_REGISTRY`` static-dict drift,
``BaseComponent`` template-method lifecycle interactions).

Per revision-1 Warning 6 verification: ``src/v1/engine/engine.py:107`` uses
``REGISTRY.get(comp_type)`` exclusively (no static ``COMPONENT_REGISTRY``
dict on ``ETLEngine``). The legacy-static-dict test path is therefore
dropped; the decorator path is the only path.

Java-side assertions target ``engine.java_bridge_manager.bridge.global_map``
(the bridge's Python dict populated by ``_sync_from_java`` after every
Java call). There is no automatic engine-side mirror of bridge globalMap
writes -- the engine wires a ContextManager+JavaBridgeManager but does
not copy bridge.global_map into ``engine.global_map``. Python-side user
code mutates ``engine.global_map`` directly because the namespace exposes
``self.global_map`` (the GlobalMap instance) as ``globalMap``.

Run instructions:
    Unit / non-java:   pytest tests/v1/engine/test_code_components_engine_smoke.py -m "not java" -q
    With Java bridge:  pytest tests/v1/engine/test_code_components_engine_smoke.py -m java -q
"""
import pytest

from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.components.transform.java_component import JavaComponent
from src.v1.engine.components.transform.java_row_component import JavaRowComponent
from src.v1.engine.components.transform.python_component import PythonComponent
from src.v1.engine.components.transform.python_row_component import PythonRowComponent
from src.v1.engine.engine import ETLEngine


# ----------------------------------------------------------------
# Helper -- minimal job-config builders
# ----------------------------------------------------------------


def _one_shot_component_config(comp_id: str, comp_type: str, config: dict) -> dict:
    """Return the inner component dict for a one-shot (no upstream) component."""
    return {
        "id": comp_id,
        "type": comp_type,
        "config": config,
        "inputs": [],
        "outputs": [],
        "schema": {"input": [], "output": []},
        "subjob_id": "subjob_1",
        "is_subjob_start": True,
    }


def _build_job(components: list[dict], flows: list[dict] | None = None,
               java_enabled: bool = False) -> dict:
    """Build a minimal job_config dict for ``ETLEngine``."""
    job: dict = {
        "job_name": "smoke_job",
        "context": {"Default": {}},
        "components": components,
        "flows": flows or [],
        "triggers": [],
    }
    if java_enabled:
        job["java_config"] = {"enabled": True}
    return job


def _row_source_component_config(
    comp_id: str, csv_path: str, columns: list[dict], output_name: str
) -> dict:
    """File-input component feeding a downstream code-component test.

    Uses ``tFileInputDelimited`` as the only available pure-data source
    (verified Wave 0 -- only Delimited file-input is registered in the
    engine's REGISTRY).
    """
    return {
        "id": comp_id,
        "type": "tFileInputDelimited",
        "config": {
            "filepath": csv_path,
            "fieldseparator": ",",
            "encoding": "UTF-8",
            "header_rows": 1,
            "footer_rows": 0,
            "limit": 0,
            "remove_empty_row": True,
            "csv_option": False,
            "die_on_error": True,
            "check_fields_num": False,
            "check_date": False,
        },
        "inputs": [],
        "outputs": [output_name],
        "schema": {"input": [], "output": columns},
        "subjob_id": "subjob_1",
        "is_subjob_start": True,
    }


# ----------------------------------------------------------------
# TestRegistryWiring -- only the decorator path (engine.py uses
# REGISTRY.get exclusively, verified at planning time)
# ----------------------------------------------------------------


@pytest.mark.unit
class TestRegistryWiring:
    """REGISTRY decorator wires all 4 components and their Talend aliases.

    Revision-1 Warning 6: legacy static-dict tests dropped --
    ``src/v1/engine/engine.py:107`` uses ``REGISTRY.get(comp_type)``
    exclusively, so the decorator path is the only path the engine ever
    consults.
    """

    def test_python_component_registered_via_decorator(self):
        """REGISTRY resolves ``PythonComponent`` and both Talend aliases."""
        assert REGISTRY.get("PythonComponent") is PythonComponent
        assert REGISTRY.get("tPython") is PythonComponent
        assert REGISTRY.get("tPythonComponent") is PythonComponent

    def test_python_row_component_registered_via_decorator(self):
        """REGISTRY resolves ``PythonRowComponent`` and the Talend alias."""
        assert REGISTRY.get("PythonRowComponent") is PythonRowComponent
        assert REGISTRY.get("tPythonRow") is PythonRowComponent

    def test_java_component_registered_via_decorator(self):
        """REGISTRY resolves ``JavaComponent`` and the Talend alias."""
        assert REGISTRY.get("JavaComponent") is JavaComponent
        assert REGISTRY.get("tJava") is JavaComponent

    def test_java_row_component_registered_via_decorator(self):
        """REGISTRY resolves ``JavaRowComponent`` and the Talend alias."""
        assert REGISTRY.get("JavaRowComponent") is JavaRowComponent
        assert REGISTRY.get("tJavaRow") is JavaRowComponent


# ----------------------------------------------------------------
# TestPythonComponentEngineEnd2End -- Python one-shot via the engine
# ----------------------------------------------------------------


@pytest.mark.unit
class TestPythonComponentEngineEnd2End:
    """tPython runs end-to-end via ETLEngine, exercising BaseComponent
    Steps 1-8 (config deepcopy, validate, resolve, mode, process, schema
    enforcement, stats, globalMap update).
    """

    def test_globalmap_write_visible_in_engine_global_map(self):
        """Engine-wide ``globalMap.put`` from user code is visible on
        ``engine.global_map`` after execute (the namespace exposes
        ``self.global_map`` directly, no sync layer needed).
        """
        config = _build_job(components=[
            _one_shot_component_config("tPython_1", "tPython", {
                "python_code": 'globalMap.put("smoke", "test")',
            }),
        ])
        engine = ETLEngine(config)

        stats = engine.execute()

        assert stats.get("status") != "error", f"Job failed: {stats.get('error')}"
        assert engine.global_map.get("smoke") == "test"


# ----------------------------------------------------------------
# TestPythonRowComponentEngineEnd2End -- per-row Python via the engine
# ----------------------------------------------------------------


@pytest.mark.unit
class TestPythonRowComponentEngineEnd2End:
    """tPythonRow runs end-to-end via ETLEngine.

    Verifies BaseComponent Step 8 auto-counts NB_LINE_OK from
    ``result['main']`` (AP-3 verification: no manual ``_update_stats``
    call inside the rewritten component).
    """

    def test_per_row_doubles_value_with_nb_line_ok(self, tmp_path):
        """Pipeline: 3-row CSV -> tPythonRow (output_row['doubled'] =
        input_row['a'] * 2) -> NB_LINE_OK == 3 in stats."""
        # Source CSV
        csv = tmp_path / "in.csv"
        csv.write_text("a\n1\n2\n3\n")

        components = [
            _row_source_component_config(
                "tFileInput_1", str(csv),
                columns=[{"name": "a", "type": "int", "nullable": False, "key": False}],
                output_name="row1",
            ),
            {
                "id": "tPythonRow_1",
                "type": "tPythonRow",
                "config": {
                    "python_code": 'output_row["doubled"] = input_row["a"] * 2',
                    "die_on_error": True,
                },
                "inputs": ["row1"],
                "outputs": [],
                "schema": {
                    "input": [{"name": "a", "type": "int", "nullable": False, "key": False}],
                    "output": [
                        {"name": "doubled", "type": "int", "nullable": False, "key": False},
                    ],
                },
                "subjob_id": "subjob_1",
                "is_subjob_start": False,
            },
        ]
        flows = [{"name": "row1", "from": "tFileInput_1", "to": "tPythonRow_1", "type": "flow"}]
        config = _build_job(components=components, flows=flows)

        engine = ETLEngine(config)
        stats = engine.execute()

        assert stats.get("status") != "error", f"Job failed: {stats.get('error')}"
        # NB_LINE_OK populated automatically by BaseComponent step 8.
        assert engine.global_map.get_nb_line_ok("tPythonRow_1") == 3


# ----------------------------------------------------------------
# TestJavaComponentEngineEnd2End -- Java one-shot via the engine
# ----------------------------------------------------------------


@pytest.mark.java
class TestJavaComponentEngineEnd2End:
    """tJava runs end-to-end via ETLEngine with the real Java bridge.

    Asserts on ``engine.java_bridge_manager.bridge.global_map`` (the
    bridge's Python dict, populated by ``_sync_from_java``). The engine
    has no automatic mirror from bridge globalMap into ``engine.global_map``.

    NB: ``ETLEngine.execute()`` calls ``_cleanup`` in its happy path, which
    invokes ``JavaBridgeManager.stop()`` and nulls the bridge handle. We
    snapshot the bridge object BEFORE ``execute()`` so the post-execute
    assertion can still read the bridge's globalMap dict (the JVM is gone
    but the Python-side dict holding the last sync survives on the
    snapshotted reference).
    """

    def test_globalmap_write_visible_in_bridge_global_map(self):
        """``globalMap.put`` from Java user code surfaces in
        ``bridge.global_map`` after execute()."""
        config = _build_job(
            components=[
                _one_shot_component_config("tJava_1", "tJava", {
                    "java_code": 'globalMap.put("smoke", "test");',
                }),
            ],
            java_enabled=True,
        )
        engine = ETLEngine(config)
        try:
            # Snapshot the bridge BEFORE execute()._cleanup() nulls it.
            bridge = engine.java_bridge_manager.bridge
            stats = engine.execute()

            assert stats.get("status") != "error", f"Job failed: {stats.get('error')}"
            assert bridge.global_map.get("smoke") == "test"
        finally:
            # Defensive cleanup -- engine.execute() already runs _cleanup
            # in its happy path, but be safe on any earlier raise.
            if engine.java_bridge_manager and engine.java_bridge_manager.is_running:
                engine.java_bridge_manager.stop()


# ----------------------------------------------------------------
# TestJavaRowComponentEngineEnd2End -- per-row Java via the engine
# ----------------------------------------------------------------


@pytest.mark.java
class TestJavaRowComponentEngineEnd2End:
    """tJavaRow runs end-to-end via ETLEngine with the real Java bridge.

    Source CSV -> tJavaRow (sets ``output_row.set("a", input_row.get("a"))``
    + ``globalMap.put("count", input_row.get("a"))`` to demonstrate per-row
    sync). NB_LINE_OK == row count.
    """

    def test_per_row_java_passes_through_with_nb_line_ok(self, tmp_path):
        """3-row CSV -> tJavaRow passthrough -> NB_LINE_OK == 3 in stats
        AND bridge.global_map['count'] == 3 (last row's 'a' value)."""
        csv = tmp_path / "in.csv"
        csv.write_text("a\n1\n2\n3\n")

        components = [
            _row_source_component_config(
                "tFileInput_1", str(csv),
                columns=[{"name": "a", "type": "int", "nullable": False, "key": False}],
                output_name="row1",
            ),
            {
                "id": "tJavaRow_1",
                "type": "tJavaRow",
                "config": {
                    "java_code": (
                        'output_row.set("a", input_row.get("a"));\n'
                        'globalMap.put("count", input_row.get("a"));'
                    ),
                    "output_schema": {"a": "int"},
                    "die_on_error": True,
                },
                "inputs": ["row1"],
                "outputs": [],
                "schema": {
                    "input": [{"name": "a", "type": "int", "nullable": False, "key": False}],
                    "output": [{"name": "a", "type": "int", "nullable": False, "key": False}],
                },
                "subjob_id": "subjob_1",
                "is_subjob_start": False,
            },
        ]
        flows = [{"name": "row1", "from": "tFileInput_1", "to": "tJavaRow_1", "type": "flow"}]
        config = _build_job(components=components, flows=flows, java_enabled=True)

        engine = ETLEngine(config)
        try:
            bridge = engine.java_bridge_manager.bridge
            stats = engine.execute()

            assert stats.get("status") != "error", f"Job failed: {stats.get('error')}"
            assert engine.global_map.get_nb_line_ok("tJavaRow_1") == 3
            # Last row's 'a' value lands in bridge.global_map["count"].
            assert bridge.global_map.get("count") == 3
        finally:
            if engine.java_bridge_manager and engine.java_bridge_manager.is_running:
                engine.java_bridge_manager.stop()
