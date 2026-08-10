"""Stage adapters: the interface tickets 17/18/19 implement against
(defined by ticket 16; the conductor sequences, stages produce).

A stage adapter does exactly three kinds of thing, all through its context:
stream model calls (the observed specialist window), write artifacts on the
bus (produce-don't-mutate; the artifact event IS the canvas event), and
report machine facts back in its StageResult. Stages NEVER raise questions
-- the conductor owns the sole question channel (ticket 02) -- and never
sequence; hub-and-spoke means a specialist cannot invoke another specialist
(ticket 05).

Slots (both doors):
  code:  explode, normalize_validate, intake_build, materialize, test_run
  LLM:   doc_normalize, interpret, design, configure, assemble, diagnose
Ticket 17 replaces the LLM stubs stage by stage; ticket 19 makes test_run
drive the real harness as a core subprocess.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .bus import ArtifactBus
from .llm import LlmCall, StreamRunner, ToolHandler
from .port import ChatOptions, ModelInfo, ToolDecl


@dataclass
class RunInfo:
    """The run facts a stage may read. Mutated only by the conductor."""

    run_id: str
    job: str
    door: str  # "brd" | "typed"
    request: Dict[str, Any] = field(default_factory=dict)  # start_run payload
    tier: Optional[str] = None  # frozen by the materializer
    draft: int = 1  # requirement-spec draft number
    feedback: str = ""  # latest directed-iteration feedback
    data_present: bool = False  # sample/expected data available
    gap_resolutions: List[Dict[str, Any]] = field(default_factory=list)
    rig: Dict[str, Any] = field(default_factory=dict)  # stub-rig knobs


@dataclass
class StageResult:
    """status: ok | shape_error | needs_human | fail. ``data`` carries the
    slot's machine facts (gaps, tier, report, feedback...)."""

    status: str = "ok"
    data: Dict[str, Any] = field(default_factory=dict)


class StageContext:
    """Everything a stage may touch, journal-idempotence included."""

    def __init__(
        self,
        *,
        run: RunInfo,
        bus: ArtifactBus,
        runner: StreamRunner,
        stage: str,  # UI-stage key this slot reports under
        iteration: int,
        model: Optional[ModelInfo],
        emit_artifact: Callable[..., Awaitable[None]],
        emit_progress: Callable[[str, str], Awaitable[None]],
        emit_loop_attempt: Callable[..., Awaitable[None]],
        sleep: Callable[[float], Awaitable[None]],
        repair: Optional[Dict[str, Any]] = None,
    ):
        self.run = run
        self.bus = bus
        self.stage = stage
        self.iteration = iteration
        self.model = model
        # Set when the conductor re-invokes this slot inside the repair loop:
        # the diagnostician's feedback.json content. A repairing stage reads
        # it first (04) and keeps its pass quiet -- no full re-walk.
        self.repair = repair
        self._runner = runner
        self._emit_artifact = emit_artifact
        self._emit_progress = emit_progress
        self._emit_loop_attempt = emit_loop_attempt
        self.sleep = sleep

    async def stream(
        self,
        who: str,
        label: str,
        prompt: str = "",
        *,
        source: Optional[str] = None,
        stage_label: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        tools: Optional[Dict[str, ToolHandler]] = None,
        tool_decls: Optional[List[ToolDecl]] = None,
        options: Optional[ChatOptions] = None,
    ) -> str:
        """One model call through the port, forwarded per-part; returns
        finish_reason. Backoff and the tool loop are the runner's."""
        return await self._runner.run(
            LlmCall(
                source=source or f"specialist:{self.stage}",
                who=who,
                label=label,
                prompt=prompt,
                stage_label=stage_label,
                in_reply_to=in_reply_to,
                tools=dict(tools or {}),
                tool_decls=list(tool_decls or []),
                model=self.model,
                options=options or ChatOptions(),
            )
        )

    async def write_artifact(
        self,
        name: str,
        payload: Any,
        *,
        kind: str,
        fields: Optional[Dict[str, Any]] = None,
        note: Optional[str] = None,
        text: Optional[str] = None,
    ) -> None:
        """Bus write + ``stage.artifact_written`` in one move (both
        journal-idempotent). ``fields`` is the renderable subset riding the
        event; ``payload`` is the full artifact on the bus. Pass ``text``
        instead of ``payload`` for data files."""
        await self._emit_artifact(
            name, payload, kind=kind, fields=fields, note=note, text=text,
            stage=self.stage, iteration=self.iteration,
        )

    async def progress(self, node_id: str, state: str) -> None:
        await self._emit_progress(node_id, state)

    async def loop_attempt(self, k: int, n: int, note: str) -> None:
        """A stage-owned bounded loop's attempt marker (e.g. the
        configurator's inner validate loop -- its counter, the conductor's
        event authorship)."""
        await self._emit_loop_attempt(self.stage, k, n, note)


class StageAdapter(ABC):
    """One slot of the pipeline. Instances are stateless between runs; all
    run state lives on the bus and in the conductor."""

    key: str = ""

    @abstractmethod
    async def run(self, ctx: StageContext) -> StageResult:
        raise NotImplementedError
