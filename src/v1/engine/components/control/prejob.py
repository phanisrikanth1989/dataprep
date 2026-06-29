"""Engine component for Prejob (tPrejob).

tPrejob is an orchestration MARKER, not a data component. In Talend it anchors
the "pre-job" phase: the subjob it triggers (via OnSubjobOk / OnComponentOk) is
guaranteed to run BEFORE any main subjob.

This engine component is a deliberate no-op. It exists for two reasons:
    1. So the node is a registered type (not "Unknown component type") and
       actually executes -- without a successful execution its OnSubjobOk
       trigger would never fire (TriggerManager._check_subjob_ok requires every
       component in the source subjob to have an ok/success status), and the
       pre-job logic would never run.
    2. To carry the framework config keys the converter emits.

The "run first" GUARANTEE itself is NOT enforced here. Ordering lives in
ExecutionPlan (prejob subjobs are seeded before normal initial subjobs) and the
depth-first drain in Executor. See ExecutionPlan.prejob_subjobs.

Config keys consumed (framework only):
  tstatcatcher_stats  (bool, default False) -- framework param
  label               (str, default "")     -- framework param
"""
import logging
from typing import Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("Prejob", "tPrejob")
class Prejob(BaseComponent):
    """tPrejob engine implementation -- no-op execution marker.

    Produces no data (no input flow, no output flow). Executing it simply marks
    the node successful so its downstream trigger fires and the pre-job subjob
    runs. The "before everything" ordering is enforced by ExecutionPlan, not by
    this class.
    """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """No structural requirements -- tPrejob has only framework params."""
        return None

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Do nothing; return an empty result so the node completes successfully."""
        logger.info(f"[{self.id}] Prejob marker reached (pre-job phase start)")
        return {"main": None, "reject": None}
