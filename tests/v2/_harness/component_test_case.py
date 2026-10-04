"""
Standard base class for all v2 component tests (HARN-02).

Every component's test class subclasses ``ComponentTestCase``, inheriting:

* **run_component()** -- creates the component, calls ``validate()`` before
  ``apply()``, and returns the output dict.  The validate-before-apply gate
  ensures that no component skips configuration validation at test time.
* **run_integration()** -- runs a full job through ``PyETLEngine.execute()``
  so integration-through-orchestrator coverage is built into every test class.
* **load_golden_cases()** -- discovers ``*.json`` files from a ``golden_dir``
  class attribute for data-driven parametric testing.
* **assert_frame_equal()** / **_dict_to_lazyframe()** -- assertion and
  conversion helpers for column-oriented golden-case dicts (D-12 format).
"""
from __future__ import annotations

import inspect
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

import polars as pl
import polars.testing

from src.v2.components.base import Component
from src.v2.components.registry import REGISTRY
from src.v2.engine import PyETLEngine

logger = logging.getLogger(__name__)


class ComponentTestCase:
    """Base class for v2 component standard tests.

    Subclasses set class attributes to configure behavior::

        component_type: str -- registry name (e.g. "filter_columns")
        component_class: Type[Component] -- direct class ref (alternative)
        golden_dir: str -- directory for golden-case JSON files
        default_config: dict -- default config passed to the component

    Provides:
        run_component(config, inputs, ...) -- create, validate, apply
        run_integration(job_config_dict) -- run through PyETLEngine.execute()
        load_golden_cases() -- classmethod that discovers *.json files
    """

    component_type: str = ""
    component_class: Optional[Type[Component]] = None
    golden_dir: str = ""
    default_config: Dict[str, Any] = {}

    # ---- component resolution ------------------------------------------------

    def _get_component_class(self) -> Type[Component]:
        """Resolve the component class from *component_class* or the registry."""
        if self.component_class is not None:
            return self.component_class
        cls = REGISTRY.get(self.component_type)
        assert cls is not None, (
            f"Component type '{self.component_type}' not found in registry. "
            f"Registered types: {REGISTRY.list_types()}"
        )
        return cls

    # ---- run_component (validate-before-apply) -------------------------------

    def run_component(
        self,
        config: Optional[Dict[str, Any]] = None,
        inputs: Optional[Dict[str, pl.LazyFrame]] = None,
        component_id: str = "test",
        context: Optional[Dict[str, Any]] = None,
        routine_registry: Optional[Any] = None,
        streaming: bool = False,
        expect_validation_errors: bool = False,
    ) -> Dict[str, pl.LazyFrame]:
        """Create component, validate, then apply.

        Parameters
        ----------
        config : dict, optional
            Component-specific config.  Merged on top of *default_config*.
        inputs : dict, optional
            Input LazyFrames.  Defaults to a single empty ``main`` frame.
        component_id : str
            ID passed to the component constructor.
        context : dict, optional
            Context variables.
        routine_registry : optional
            Routine registry instance.
        streaming : bool
            Whether to enable streaming mode.
        expect_validation_errors : bool
            When ``True``, assert that validation **fails** and return the
            error list under the ``_validation_errors`` key instead of
            calling ``apply()``.

        Returns
        -------
        Dict[str, pl.LazyFrame]
            Component outputs (or ``{"_validation_errors": list}`` when
            *expect_validation_errors* is ``True``).
        """
        merged_config = {**self.default_config, **(config or {})}
        comp_cls = self._get_component_class()
        component = comp_cls(
            component_id=component_id,
            config=merged_config,
            context=context,
            routine_registry=routine_registry,
            streaming=streaming,
        )

        # Validate-before-apply gate (D-14)
        errors = component.validate()

        if expect_validation_errors:
            assert errors, (
                "Expected validation errors but validate() returned an empty "
                f"list for config: {merged_config}"
            )
            return {"_validation_errors": errors}

        assert not errors, (
            f"Component validation failed with errors: {errors}"
        )

        if inputs is None:
            inputs = {"main": pl.DataFrame({"_empty": []}).lazy()}

        return component.apply(inputs)

    # ---- run_integration -----------------------------------------------------

    def run_integration(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Run a full job through PyETLEngine and return the result dict.

        The caller is responsible for asserting on ``status``, ``components``,
        and any output-specific expectations.
        """
        engine = PyETLEngine(job_config)
        return engine.execute()

    # ---- golden-case loading -------------------------------------------------

    @classmethod
    def load_golden_cases(cls) -> List[Dict[str, Any]]:
        """Discover and load golden-case JSON files from *golden_dir*.

        Each JSON file is loaded and returned as a dict with an extra
        ``case_id`` key set to the file stem.  Files are sorted by name
        for deterministic ordering.

        Returns an empty list if *golden_dir* is unset or the directory
        does not exist.
        """
        if not cls.golden_dir:
            return []

        test_dir = Path(inspect.getfile(cls)).parent
        golden_path = test_dir / cls.golden_dir
        if not golden_path.exists():
            return []

        cases: List[Dict[str, Any]] = []
        for json_file in sorted(golden_path.glob("*.json")):
            with open(json_file) as f:
                data = json.load(f)
            cases.append({"case_id": json_file.stem, **data})
        return cases

    # ---- assertion and conversion helpers ------------------------------------

    @staticmethod
    def _dict_to_lazyframe(data: Dict[str, list]) -> pl.LazyFrame:
        """Convert a column-oriented dict to a ``pl.LazyFrame`` (D-12 format)."""
        return pl.DataFrame(data).lazy()

    @staticmethod
    def assert_frame_equal(
        actual: pl.LazyFrame,
        expected_data: Dict[str, list],
        check_order: bool = True,
    ) -> None:
        """Assert that *actual* LazyFrame matches *expected_data*.

        Parameters
        ----------
        actual : pl.LazyFrame
            The LazyFrame to verify.
        expected_data : dict
            Column-oriented dict (``{col_name: [values]}``) representing
            the expected DataFrame.
        check_order : bool
            Whether row order must match (default ``True``).
        """
        actual_df = actual.collect()
        expected_df = pl.DataFrame(expected_data)
        pl.testing.assert_frame_equal(
            actual_df, expected_df, check_row_order=check_order,
        )
