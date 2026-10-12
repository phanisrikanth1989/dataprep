"""Run job: another job run as one step of this one."""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Tuple

from ...errors import ConfigurationError
from ...job.keys import Key, Kind
from ...job.model import typed
from ..base import Action, one_line
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

_NO_EFFECT = "Taken and without effect: the child runs in the parent's process, which has no JVM."


def _named(value: str) -> str:
    if not value.strip():
        raise ValueError("there is no job named")
    if "/" in value or "\\" in value:
        # Looked for beside the parent, and nowhere else.
        raise ValueError(f"a job is named by its name, not by a path: '{value}'")
    return value


@REGISTRY.register
class RunJob(Action):
    """Run the job `process` names as one step of this job, and go on when it has ended.

    The child's job config is looked for beside the parent's: `<process>.json`,
    else the `<process>_<version>.json` of the highest version. It is found,
    loaded and checked when the parent is: what is wrong with it refuses
    the parent, and a job that would run itself is refused.

    The child runs in the parent's process, as a run of its own. It is
    given context values and nothing else: each `context_params` entry
    sets the child's context variable `param_name`, which the child has to
    declare, with the type the child declares it; `transmit_whole_context`
    gives it every variable of the parent that it declares as well, and a
    value given by name wins. Nothing of the child reaches the parent but
    how it ended: `<id>_CHILD_RETURN_CODE` (0, the exit code of the die
    that ended it, or 1) and, when it failed, why, in
    `<id>_CHILD_EXCEPTION_STACKTRACE`. The summary of its run is in the
    parent's, under `children`.

    A child that fails fails the parent at this step. With
    `die_on_child_error` off the parent goes on, with a warning, and why
    is in `<id>_ERROR_MESSAGE` too. It counts one row. No flow comes to it
    or leaves it.
    """

    names = ("run_job", "RunJob", "tRunJob")
    runs_job = True
    keys = (
        Key("process", required=True, convert=_named,
            doc="The job to run: the name of its job config, without `.json` and without a version."),
        Key("context_name", default="Default",
            doc="The context group the child reads. `Default` stands for the child's own when it has no group of that name."),
        Key("die_on_child_error", type=bool, default=True, doc="Whether a child that fails fails the parent."),
        Key("transmit_whole_context", type=bool, default=False,
            doc="Whether the child is given every context variable of the parent that it declares."),
        Key("context_params", type=list, default=[], doc="Context values given to the child by name.",
            items=(Key("param_name", required=True, doc="A context variable the child declares."),
                   Key("param_value", type=object, default=None, doc="Its value; it may be an item of globalMap."))),
        Key("use_dynamic_job", kind=Kind.REFUSED, type=bool,
            reason="the job to run has to be known when the parent loads: name it in `process`"),
        Key("use_dynamic_context", kind=Kind.REFUSED, type=bool,
            reason="the child's context group has to be known when the parent loads: name it in `context_name`"),
        Key("propagate_child_result", kind=Kind.REFUSED, type=bool,
            reason="v2 hands no rows from one job to another in memory: have the child write a file and the parent read it"),
        Key("context_job", kind=Kind.IGNORED, type=object, doc="The job a dynamic job is picked among; see `use_dynamic_job`."),
        Key("dynamic_context", kind=Kind.IGNORED, type=object, doc="The context of a dynamic job; see `use_dynamic_context`."),
        Key("use_independent_process", kind=Kind.IGNORED, type=object, doc=_NO_EFFECT),
        Key("jvm_arguments", kind=Kind.IGNORED, type=object, doc=_NO_EFFECT),
        Key("use_child_jvm_setting", kind=Kind.IGNORED, type=object, doc=_NO_EFFECT),
        Key("use_custom_jvm_setting", kind=Kind.IGNORED, type=object, doc=_NO_EFFECT),
        Key("use_extra_classpath", kind=Kind.IGNORED, type=object, doc=_NO_EFFECT),
        Key("extra_classpath", kind=Kind.IGNORED, type=object, doc=_NO_EFFECT),
        Key("load_context_from_file", kind=Kind.IGNORED, type=object, doc=_NO_EFFECT),
        Key("print_parameter", kind=Kind.IGNORED, type=object, doc="Talend prints the values given; v2 does not show them."),
        Key("transmit_original_context", kind=Kind.IGNORED, type=object,
            doc="Values are given with their types either way."),
        Key("die_on_error", kind=Kind.IGNORED, type=object, doc="`die_on_child_error` says it; v1 reads this on every component."),
    )

    def act(self) -> None:
        config, held = self.config, self.global_map
        child = self.run_context.child_jobs[self.id]
        given = self._given(child)
        logger.info(one_line(f"[{self.id}] running the job '{child.name}' ({os.path.basename(child.read_from)})"))
        started = time.perf_counter()
        result = self.run_context.run_child(self.id, given)
        took = time.perf_counter() - started
        failed = result.status != "success"
        code = 0
        if failed:
            # The exit code of the die that ended the child, when one did.
            died_with = result.global_map.get("JOB_EXIT_CODE")
            code = died_with if isinstance(died_with, int) and not isinstance(died_with, bool) and died_with else 1
        held.update({
            f"{self.id}_CHILD_RETURN_CODE": code,
            f"{self.id}_NB_LINE": 1, f"{self.id}_NB_LINE_OK": 0 if failed else 1, f"{self.id}_NB_LINE_REJECT": int(failed),
        })
        if not failed:
            # Not left from an earlier run of this step, in a loop, that failed.
            held.pop(f"{self.id}_CHILD_EXCEPTION_STACKTRACE", None)
            logger.info(one_line(f"[{self.id}] the job '{child.name}' finished in {took:.2f}s"))
            return
        held[f"{self.id}_CHILD_EXCEPTION_STACKTRACE"] = result.error
        where = f" at {result.failed_component}" if result.failed_component else ""
        said = f"the job '{child.name}' failed{where}: {result.error}"
        if config["die_on_child_error"]:
            raise ConfigurationError(said)
        held[f"{self.id}_ERROR_MESSAGE"] = said
        logger.warning(one_line(f"[{self.id}] {said}; the job goes on"))

    def _given(self, child: Any) -> Dict[str, Any]:
        """The context values the child is given, each as the child declares it.

        With `transmit_whole_context`, every variable of the parent that
        the child declares; then the values given by name, which win.
        """
        # For each variable: where its value is said, for a message, and the value.
        wanted: Dict[str, Tuple[str, Any]] = {}
        if self.config["transmit_whole_context"]:
            for name, value in self.context.items():
                if name in child.context:
                    wanted[name] = (f"the parent's context variable '{name}'", value)
        for at, entry in enumerate(self.config["context_params"]):
            wanted[entry["param_name"]] = (f"context_params[{at}].param_value", entry["param_value"])
        given: Dict[str, Any] = {}
        for name, (said_at, value) in wanted.items():
            declared = child.context_types.get(name)
            try:
                given[name] = typed(value, declared) if declared is not None else value
            except ValueError:
                raise ConfigurationError(
                    f"{said_at}: {value!r} is no {declared}, which the job '{child.name}' declares '{name}' to be"
                ) from None
        return given
