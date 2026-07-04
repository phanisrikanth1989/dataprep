"""Engine component for Postjob (tPostjob).

tPostjob is an orchestration MARKER, not a data component. In Talend it anchors
the "post-job" phase: the subjob it triggers (via OnSubjobOk / OnComponentOk) is
guaranteed to run AFTER the main job.

This engine component is a deliberate no-op. It exists for two reasons:
    1. So the node is a registered type (not "Unknown component type") and
       actually executes -- without a successful execution its OnSubjobOk
       trigger would never fire (TriggerManager._check_subjob_ok requires every
       component in the source subjob to have an ok/success status), and the
       post-job logic would never run.
    2. To carry the framework config keys the converter emits.

The "run last" ordering and the success-gate (post-job runs only when no
component failed -- a deliberate divergence from Talend's always-run cleanup
semantics, chosen for this engine) are NOT enforced here:
    - Ordering: ExecutionPlan seeds postjob subjobs after all normal initial
      subjobs; the depth-first drain in Executor keeps the whole post-job chain
      at the very back. See ExecutionPlan.postjob_subjobs.
    - Success-gate: Executor._drain_pending_subjobs skips postjob subjobs when
      any component has failed (or the job was terminated by tDie).

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


@REGISTRY.register("Postjob", "tPostjob")
class Postjob(BaseComponent):
    """tPostjob engine implementation -- no-op execution marker.

    Produces no data (no input flow, no output flow). Executing it simply marks
    the node successful so its downstream trigger fires and the post-job subjob
    runs. The "after everything" ordering and the skip-on-failure gate are
    enforced by ExecutionPlan and Executor, not by this class.
    """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """No structural requirements -- tPostjob has only framework params."""
        return None

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Do nothing; return an empty result so the node completes successfully."""
        logger.info(f"[{self.id}] Postjob marker reached (post-job phase start)")
        return {"main": None, "reject": None}
