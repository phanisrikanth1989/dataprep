"""Load a job config into the model the engine runs.

A job config is read in v1's shape, which is the reference, with v2's own
spellings accepted beside it. Everything v2 will not run with is collected
into one refusal report and raised together, before anything runs.
"""
from __future__ import annotations

import copy
import glob
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from ..components.base import BEFORE
from ..components.registry import REGISTRY, Registry
from .graph import bodies, loop, subjobs
from .keys import EXPRESSION, Key, Kind, has_context_reference, normalize_config
from .model import TYPE_NAMES, Column, ComponentSpec, Flow, Iterate, Job, Only, RunSettings, Trigger, typed
from ..engine.references import JAVA_MARK, parsed
from .refusal import Refusal, RefusalReport, of_child
from ..errors import JobRefusedError

JAVA_PREFIX = JAVA_MARK
JAVA_REASON = "Java expressions are not run by v2; rewrite it in Python"

_TRIGGER_KINDS = {
    "OnSubjobOk": "OnSubjobOk",
    "OnSubjobError": "OnSubjobError",
    "OnComponentOk": "OnComponentOk",
    "OnComponentError": "OnComponentError",
    "RunIf": "RunIf",
    # v2's own spellings
    "on_success": "OnSubjobOk",
    "on_failure": "OnSubjobError",
    "conditional": "RunIf",
}


def _not_empty(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be empty")
    return value


def _some(value: list) -> list:
    if not value:
        raise ValueError("the job has no components")
    return value


_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
_WRITTEN_REFERENCE = re.compile(r"\$\{context\.\w+\}")
# The kinds of place a row can be picked by, as a failure names a row's place.
PLACES = ("lines", "records", "rows")


def _level(value: str) -> str:
    if value.upper() not in _LEVELS:
        raise ValueError(f"{value!r} is not a log level; the levels are {', '.join(_LEVELS)}")
    return value.upper()


def _numbers(value: List[Any]) -> List[int]:
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int) or item < 1:
            raise ValueError(f"{item!r} is not the number of a row; rows are numbered from 1")
    if not value:
        raise ValueError("names no row")
    return list(value)


def _values(value: Dict[str, Any]) -> Dict[str, List[Any]]:
    """Each column with the values a picked row may hold in it; one value may be given bare."""
    if not value:
        raise ValueError("names no column")
    made: Dict[str, List[Any]] = {}
    for column, wanted in value.items():
        listed = wanted if isinstance(wanted, list) else [wanted]
        if not listed or any(isinstance(item, (list, dict)) or item is None for item in listed):
            raise ValueError(f"column '{column}': give the value a picked row holds, or a list of such values")
        made[column] = list(listed)
    return made


ONLY_KEYS: Tuple[Key, ...] = (
    Key("source", required=True, convert=_not_empty, doc="Id of the reader whose rows are picked."),
    Key("where", type=dict, default=None, nullable=True, convert=_values,
        doc="Column name to the value, or the values, a picked row holds in it."),
    Key("lines", type=list, default=None, nullable=True, convert=_numbers,
        doc="The picked rows by their line in a text file, as a failure names it."),
    Key("records", type=list, default=None, nullable=True, convert=_numbers,
        doc="The picked rows by their record number: a JSON document, or a delimited file read with `csv_option`."),
    Key("rows", type=list, default=None, nullable=True, convert=_numbers,
        doc="The picked rows by their row on a sheet of a workbook; `sheet` says which sheet."),
    Key("sheet", default=None, nullable=True, doc="The sheet `rows` are on."),
)

RUN_KEYS: Tuple[Key, ...] = (
    Key("log_level", default=None, nullable=True, convert=_level,
        doc="The lowest level of log line that is written: DEBUG, INFO, WARNING, ERROR or CRITICAL."),
    Key("row_counts", type=bool, default=None, nullable=True,
        doc="Whether the rows of every component are counted and logged. The run then takes about three times as long."),
    Key("summary_file", default=None, nullable=True, doc="A file the summary of the run is written to as well."),
    Key("only", type=dict, default=None, nullable=True, fields=ONLY_KEYS,
        doc="Run the job for a few rows of one reader and no others."),
    Key("trace", type=bool, default=None, nullable=True,
        doc="With `only`: have the result hold what every component did with the picked rows."),
)

JOB_KEYS: Tuple[Key, ...] = (
    Key("name", required=True, aliases=("job_name",), convert=_not_empty, doc="The job's name."),
    Key("context", type=dict, default={}, doc="Context variables, flat or grouped by context name."),
    Key("default_context", doc="The context group to use when the context is grouped."),
    Key("components", type=list, required=True, convert=_some, doc="The components."),
    Key("flows", type=list, default=[], doc="The flows between components."),
    Key("triggers", type=list, default=[], doc="The triggers between subjobs."),
    Key("subjobs", kind=Kind.IGNORED, type=object, doc="v1's subjob listing; v2 derives subjobs from the flows."),
    Key("java_config", kind=Kind.IGNORED, type=object, doc="v1's Java bridge settings."),
    Key("python_config", type=dict, default=None, nullable=True, doc="Routine modules usable in expressions.",
        fields=(
            Key("enabled", type=bool, default=False, doc="Whether routines are loaded."),
            Key("routines_dir", default="src/python_routines", doc="The folder holding the routine files."),
            Key("routines", type=list, default=[], doc="Names of routines that must be there."),
        )),
    Key("run", type=dict, default=None, nullable=True, fields=RUN_KEYS,
        doc="How the job is run: what the command line could say too. The command line wins over it."),
    Key("engine_config", kind=Kind.IGNORED, type=object, doc="v1 engine settings for components v2 does not have."),
    Key("oracle_config", kind=Kind.IGNORED, type=object, doc="v1's Oracle settings."),
    Key("mssql_config", kind=Kind.IGNORED, type=object, doc="v1's SQL Server settings."),
    Key("job_type", kind=Kind.IGNORED, type=object, doc="Talend job type."),
    Key("version", kind=Kind.IGNORED, type=object, doc="Free-form version label."),
    Key("description", kind=Kind.IGNORED, type=object, doc="Free-form description."),
)

COMPONENT_KEYS: Tuple[Key, ...] = (
    Key("id", required=True, convert=_not_empty, doc="The component's id, unique in the job."),
    Key("type", required=True, convert=_not_empty, doc="The component type."),
    Key("config", type=dict, default={}, doc="The component's config."),
    Key("schema", type=object, default=None, doc="Declared columns: {input: [...], output: [...]}."),
    Key("inputs", type=list, default=[],
        doc="Names of the incoming flows, in the order the component takes them. The flows decide which arrive."),
    Key("outputs", kind=Kind.IGNORED, type=object, doc="v1's list of outgoing flow names; the flows decide."),
    Key("original_type", kind=Kind.IGNORED, type=object, doc="The Talend type the component was converted from."),
    Key("position", kind=Kind.IGNORED, type=object, doc="Canvas position."),
    Key("subjob_id", kind=Kind.IGNORED, type=object, doc="v1's subjob label; v2 derives subjobs from the flows."),
    Key("is_subjob_start", kind=Kind.IGNORED, type=object, doc="v1's subjob start marker."),
)

FLOW_KEYS: Tuple[Key, ...] = (
    Key("name", required=True, convert=_not_empty, doc="The flow's name, unique in the job."),
    Key("source", required=True, aliases=("from",), doc="Id of the component the rows come from."),
    Key("target", required=True, aliases=("to",), doc="Id of the component the rows go to."),
    Key("type", default="flow", doc="flow, main, reject, filter, unique or duplicate."),
    Key("output", doc="The output port of the source, when the type does not say."),
    Key("input", kind=Kind.IGNORED, type=object, doc="Old v2 input port name; the flow name is used instead."),
    Key("enable_parallel", type=bool, default=False,
        doc="On an iterate link: Talend's switch for running passes side by side. v2 runs them one after another."),
    Key("number_parallel", kind=Kind.IGNORED, type=object, doc="On an iterate link: how many passes Talend runs side by side."),
)

TRIGGER_KEYS: Tuple[Key, ...] = (
    Key("type", required=True, choices=tuple(_TRIGGER_KINDS), doc="When the trigger fires."),
    Key("source", required=True, aliases=("from", "from_component"),
        doc="Id of the component the trigger leaves from."),
    Key("target", required=True, aliases=("to", "to_component"), doc="Id of the component it starts."),
    Key("condition", type=EXPRESSION, doc="The condition a RunIf trigger fires on."),
    Key("order", type=int, default=0, aliases=("output_id",),
        doc="Where the trigger comes among those leaving the same subjob; lower first."),
)


def _places(value: int) -> Optional[int]:
    """Declared decimal places; a negative number is Talend's way to say none are declared."""
    return value if value >= 0 else None


COLUMN_KEYS: Tuple[Key, ...] = (
    Key("name", required=True, convert=_not_empty, doc="The column name."),
    Key("type", default="str", choices=tuple(TYPE_NAMES), doc="The column type."),
    Key("nullable", type=bool, default=True, doc="Whether missing values are allowed."),
    Key("key", type=bool, default=False, doc="Whether the column is part of the key."),
    Key("length", type=int, doc="Declared length."),
    Key("precision", type=int, convert=_places,
        doc="Declared number of decimal places. A negative number, as Talend writes for none, means none."),
    Key("date_pattern", aliases=("pattern",), doc="strftime pattern for dates."),
    Key("default", kind=Kind.IGNORED, type=object, doc="Talend default value."),
    Key("comment", kind=Kind.IGNORED, type=object, doc="Free-form comment."),
    Key("original_type", kind=Kind.IGNORED, type=object, doc="The Talend type."),
)


def load_job(
    source: Union[Mapping[str, Any], str, Path],
    context: Optional[Mapping[str, Any]] = None,
    registry: Registry = REGISTRY,
) -> Job:
    """Load a job config.

    Args:
        source: The job config, as a dict or as the path of a JSON file.
        context: Context values that override the job config's own.
        registry: Where component types are looked up.

    Returns:
        The loaded job.

    Raises:
        JobRefusedError: When the job config holds anything v2 will not run
            with. Its report lists every problem found.
    """
    read_from = None
    if isinstance(source, (str, Path)):
        read_from = os.path.abspath(source)
        with open(source, encoding="utf-8") as handle:
            raw = json.load(handle)
        if not isinstance(raw, dict):
            report = RefusalReport(job_name="")
            report.add("job", "job config", f"expected an object, found {type(raw).__name__}")
            report.raise_if_refused()
    else:
        raw = copy.deepcopy(dict(source))
    return _Loader(raw, dict(context or {}), registry, read_from=read_from).load()


def run_settings(block: Optional[Dict[str, Any]], written: Any = None) -> Tuple[RunSettings, List[Refusal]]:
    """Run settings from a ``run`` block that was checked against ``RUN_KEYS``, with what they cannot be run with.

    Args:
        block: The block as ``normalize_config`` hands it on.
        written: The block as it was written, to tell a way of picking rows
            that was not given from one that was given and refused.
    """
    block = block or {}
    written_only = written.get("only") if isinstance(written, dict) else None
    refusals: List[Refusal] = []
    for name, value in block.items():
        if has_context_reference(value) or _asks_for_context(value):
            refusals.append(Refusal("job", f"run.{name}", "a context variable is not read in a run setting"))
    settings = RunSettings(
        log_level=block.get("log_level"), row_counts=block.get("row_counts"),
        summary_file=block.get("summary_file"), trace=block.get("trace"),
    )
    picked = block.get("only")
    if picked is not None and picked.get("source"):
        places = [(kind, picked[kind]) for kind in PLACES if picked.get(kind)]
        given = written_only if isinstance(written_only, dict) else picked
        ways = sum(given.get(way) is not None for way in ("where",) + PLACES)
        if ways != 1:
            refusals.append(Refusal(
                "job", "run.only", "say which rows in one way: `where`, or one of " + ", ".join(f"`{kind}`" for kind in PLACES)
            ))
        elif picked.get("sheet") is not None and given.get("rows") is None:
            refusals.append(Refusal("job", "run.only.sheet", "a sheet is named together with `rows`"))
        elif places or picked.get("where"):
            settings.only = Only(
                source=picked["source"], where=picked.get("where") or {},
                places=places[0] if places else None, sheet=picked.get("sheet"),
            )
    return settings, refusals


def _asks_for_context(value: Any) -> bool:
    """Whether a text inside a setting that holds several values is written as ``${context.name}``.

    What rows are picked by is data, and data may hold any text: there only
    the spelling that can be nothing but a reference is taken for one.
    """
    if isinstance(value, dict):
        return any(_asks_for_context(item) for item in value.values())
    if isinstance(value, list):
        return any(_asks_for_context(item) for item in value)
    return isinstance(value, str) and bool(_WRITTEN_REFERENCE.search(value))


def caller_settings(asked: Optional[Mapping[str, Any]]) -> Tuple[RunSettings, List[Refusal]]:
    """Run settings as a caller of the engine hands them over: checked like a job config's ``run`` block."""
    if asked is not None and not isinstance(asked, Mapping):
        return RunSettings(), [Refusal("job", "run", f"expected an object, got {asked!r}")]
    block, refusals = normalize_config(dict(asked or {}), RUN_KEYS, "job", _prefix="run.")
    settings, more = run_settings(block, asked)
    return settings, refusals + more


class _Loader:
    """Reads one job config, collecting refusals as it goes."""

    def __init__(
        self,
        raw: Dict[str, Any],
        overrides: Dict[str, Any],
        registry: Registry,
        read_from: Optional[str] = None,
        running: Tuple[str, ...] = (),
    ) -> None:
        self.raw = {key: value for key, value in raw.items() if not key.startswith("_")}
        self.overrides = overrides
        self.registry = registry
        # The file this job config was read from, and the files of the jobs that run it, the first of them first:
        # a job that is among them would run itself.
        self.read_from = read_from
        self.running = running
        self.report = RefusalReport(job_name=str(raw.get("job_name") or raw.get("name") or ""))
        # Components that lost an incoming flow to a refusal elsewhere; their input count proves nothing.
        self._starved: set = set()
        # Where each iterate link names its target in the job config, by the link's name: for a refusal.
        self._iterate_ends: Dict[str, str] = {}

    def load(self) -> Job:
        top, refusals = normalize_config(self.raw, JOB_KEYS, "job")
        self.report.extend(refusals)
        job = Job(name=top.get("name") or "", read_from=self.read_from)
        job.run, refusals = run_settings(top.get("run"), self.raw.get("run"))
        self.report.extend(refusals)
        job.context, job.context_types = self._context(top)
        for index, raw_component in enumerate(top.get("components") or []):
            spec = self._component(index, raw_component, job)
            if spec is not None:
                job.components[spec.id] = spec
        for index, raw_flow in enumerate(top.get("flows") or []):
            flow = self._flow(index, raw_flow, job)
            if flow is not None:
                job.flows.append(flow)
        for index, raw_trigger in enumerate(top.get("triggers") or []):
            trigger = self._trigger(index, raw_trigger, job)
            if trigger is not None:
                job.triggers.append(trigger)
        job.routines = top.get("python_config")
        self._children(job)
        self._check_input_counts(job)
        stuck = loop(job)
        if stuck:
            self.report.add("job", "flows", f"the flows form a loop through: {', '.join(stuck)}")
        else:
            self._check_iterates(job)
            self._check_triggers(job)
        self.report.raise_if_refused()
        return job

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------

    def _context(self, top: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """The context values, converted to their declared types, and those types."""
        declared = top.get("context") or {}
        group_name = top.get("default_context")
        grouped = _groups(declared, group_name) is not None
        if grouped:
            if group_name is None:
                group_name = "Default" if "Default" in declared else next(iter(declared))
            if group_name not in declared:
                self.report.add("job", "default_context", f"there is no context group named '{group_name}'")
                declared = {}
            else:
                declared = declared[group_name]

        types: Dict[str, str] = {}
        values: Dict[str, Any] = {}
        for name, entry in declared.items():
            if isinstance(entry, dict) and "value" in entry:
                types[name] = str(entry.get("type") or "str")
                values[name] = entry.get("value")
            else:
                values[name] = entry
        values.update(self.overrides)

        for name, type_name in types.items():
            try:
                values[name] = typed(values[name], type_name)
            except ValueError:
                self.report.add("job", f"context.{name}", f"{values[name]!r} is not a valid {type_name}")
        return values, types

    # ------------------------------------------------------------------
    # Components
    # ------------------------------------------------------------------

    def _component(self, index: int, raw: Any, job: Job) -> Optional[ComponentSpec]:
        prefix = f"components[{index}]."
        if not isinstance(raw, dict):
            self.report.add("job", f"components[{index}]", "expected an object")
            return None
        component_id, type_name = raw.get("id"), raw.get("type")
        named = isinstance(component_id, str) and component_id.strip() and isinstance(type_name, str) and type_name.strip()
        where = f"component {component_id} ({type_name})" if named else "job"
        fields, refusals = normalize_config(raw, COMPONENT_KEYS, where, _prefix="" if named else prefix)
        self.report.extend(refusals)
        if not named:
            return None
        if component_id in job.components:
            self.report.add("job", f"{prefix}id", f"the id '{component_id}' is used by more than one component")
            return None

        raw_config = dict(fields.get("config") or {})
        schema_value = fields.get("schema")
        if schema_value is None and "schema" in raw_config:
            schema_value = raw_config.pop("schema")
        schemas = self._schema(schema_value, where)

        cls = self.registry.get(type_name)
        # Java left under a key the component does not read (a filter that is switched off) is harmless.
        unread = set(cls.unread_paths(raw_config)) if cls is not None else set()
        java = _java_paths(raw_config)
        for path in java:
            if path not in unread:
                self.report.add(where, path, JAVA_REASON)
        if cls is None:
            self.report.add(where, "type", f"component type '{type_name}' is not supported in v2")
            return None
        config, refusals = normalize_config(raw_config, cls.all_keys(), where)
        self.report.extend(r for r in refusals if not _under(r.key, java))
        return ComponentSpec(
            id=component_id,
            type=type_name,
            cls=cls,
            raw_config=raw_config,
            config=config,
            schema=schemas["output"],
            input_schema=schemas["input"],
            reject_schema=schemas["reject"],
            input_schemas=schemas["inputs"],
            input_order=[name for name in fields.get("inputs") or [] if isinstance(name, str)],
        )

    def _schema(self, value: Any, where: str) -> Dict[str, Any]:
        """The schema blocks of a component: output, input, reject and per-flow inputs."""
        schemas: Dict[str, Any] = {"output": [], "input": [], "reject": [], "inputs": {}}
        if value is None:
            return schemas
        if isinstance(value, list):
            schemas["output"] = self._columns(value, where, "schema")
            return schemas
        if not isinstance(value, dict):
            self.report.add(where, "schema", "expected a list of columns, or {input: [...], output: [...]}")
            return schemas
        for name in sorted(set(value) - set(schemas) - {"outputs"}):
            self.report.add(where, f"schema.{name}", "unknown config key")
        for name in ("output", "input", "reject"):
            schemas[name] = self._columns(value.get(name) or [], where, f"schema.{name}")
        per_flow = value.get("inputs") or {}
        if not isinstance(per_flow, dict):
            self.report.add(where, "schema.inputs", "expected an object of flow name to columns")
            return schemas
        for flow_name, columns in per_flow.items():
            schemas["inputs"][flow_name] = self._columns(columns or [], where, f"schema.inputs.{flow_name}")
        return schemas

    def _columns(self, raw_columns: Any, where: str, path: str) -> List[Column]:
        if not isinstance(raw_columns, list):
            self.report.add(where, path, "expected a list of columns")
            return []
        columns: List[Column] = []
        for index, raw in enumerate(raw_columns):
            if not isinstance(raw, dict):
                self.report.add(where, f"{path}[{index}]", "expected an object")
                continue
            fields, refusals = normalize_config(raw, COLUMN_KEYS, where, _prefix=f"{path}[{index}].")
            self.report.extend(refusals)
            if refusals:
                continue
            columns.append(
                Column(
                    name=fields["name"],
                    type=TYPE_NAMES[fields["type"]],
                    nullable=fields["nullable"],
                    key=fields["key"],
                    length=fields["length"],
                    precision=fields["precision"],
                    date_pattern=fields["date_pattern"] or None,
                )
            )
        return columns

    # ------------------------------------------------------------------
    # The jobs this one runs
    # ------------------------------------------------------------------

    def _children(self, job: Job) -> None:
        """Find and load the job of every component that runs one: a child is known when its parent loads.

        What is wrong with a child refuses the parent, and is said under
        the component that runs it.
        """
        for spec in job.components.values():
            process = spec.config.get("process")
            if not spec.cls.runs_job or not isinstance(process, str) or not process:
                continue
            if has_context_reference(process):
                self.report.add(spec.where, "process", f"the job to run has to be known when the parent loads, and "
                                                       f"'{process}' is known only when it runs")
                continue
            path = self._child_file(spec, process)
            if path is None:
                continue
            read = (*self.running, self.read_from) if self.read_from else self.running
            if os.path.realpath(path) in [os.path.realpath(known) for known in read]:
                chain = " -> ".join(os.path.basename(known) for known in (*read, path))
                self.report.add(spec.where, "process", f"the job would run itself: {chain}")
                continue
            try:
                with open(path, encoding="utf-8") as handle:
                    raw = json.load(handle)
                if not isinstance(raw, dict):
                    raise ValueError(f"expected an object, found {type(raw).__name__}")
            except (OSError, ValueError) as exc:
                self.report.add(spec.where, "process", f"'{os.path.basename(path)}' is no job config that can be read: {exc}")
                continue
            name = str(raw.get("job_name") or raw.get("name") or process)
            if not self._child_group(spec, raw, name):
                continue
            try:
                child = _Loader(raw, {}, self.registry, read_from=path, running=read).load()
            except JobRefusedError as refused:
                self.report.extend(of_child(spec.where, name, refusal) for refusal in refused.report)
                continue
            for at, given in enumerate(spec.config.get("context_params") or []):
                wanted = given.get("param_name")
                if isinstance(wanted, str) and wanted not in child.context:
                    has = f"it has: {', '.join(child.context)}" if child.context else "it has none"
                    self.report.add(spec.where, f"context_params[{at}].param_name",
                                    f"the job '{child.name}' has no context variable '{wanted}'; {has}")
            job.children[spec.id] = child

    def _child_file(self, spec: ComponentSpec, process: str) -> Optional[str]:
        """The job config of a child: `<process>.json` beside the parent, else the highest `<process>_<version>.json`."""
        settings = self.raw.get("engine_config")
        folder = os.path.dirname(self.read_from) if self.read_from else None
        if folder is None and isinstance(settings, dict) and settings.get("jobs_dir"):
            folder = os.path.abspath(str(settings["jobs_dir"]))
        if folder is None:
            self.report.add(spec.where, "process", f"the job config was not read from a file, so there is no folder to "
                                                   f"look for '{process}' in: name one in `engine_config.jobs_dir`")
            return None
        exact = os.path.join(folder, f"{process}.json")
        if os.path.isfile(exact):
            return exact
        # A converted job config is named after its job and the job's version, and a run job names the job alone.
        versions = []
        for path in glob.glob(os.path.join(glob.escape(folder), glob.escape(f"{process}_") + "*.json")):
            version = os.path.basename(path)[len(process) + 1:-len(".json")]
            if re.fullmatch(r"\d+(\.\d+)*", version):
                versions.append((tuple(int(part) for part in version.split(".")), path))
        if not versions:
            self.report.add(spec.where, "process", f"there is no job config for '{process}' in '{folder}': neither "
                                                   f"{process}.json nor a {process}_<version>.json")
            return None
        return max(versions)[1]

    def _child_group(self, spec: ComponentSpec, raw: Dict[str, Any], name: str) -> bool:
        """Have a child read the context group its parent names for it; said in the report when it has no such group."""
        wanted = spec.config.get("context_name")
        groups = _groups(raw.get("context"), raw.get("default_context"))
        if not isinstance(wanted, str) or not wanted:
            return True
        if has_context_reference(wanted):
            self.report.add(spec.where, "context_name", f"the child's context group has to be known when the parent loads, "
                                                        f"and '{wanted}' is known only when it runs")
            return False
        if groups is not None and wanted in groups:
            raw["default_context"] = wanted
        elif wanted != "Default":
            # `Default` is what the converter writes when the job named no group: the child then has its own.
            has = f"it has: {', '.join(groups)}" if groups else "its context is not in groups"
            self.report.add(spec.where, "context_name", f"the job '{name}' has no context group '{wanted}'; {has}")
            return False
        return True

    # ------------------------------------------------------------------
    # Flows and triggers
    # ------------------------------------------------------------------

    def _flow(self, index: int, raw: Any, job: Job) -> Optional[Flow]:
        prefix = f"flows[{index}]."
        if not isinstance(raw, dict):
            self.report.add("job", f"flows[{index}]", "expected an object")
            return None
        fields, refusals = normalize_config(raw, FLOW_KEYS, "job", _prefix=prefix)
        self.report.extend(refusals)
        if refusals:
            return None
        ok = True
        for end, v1_name in (("source", "from"), ("target", "to")):
            if fields[end] not in job.components:
                spelling = v1_name if v1_name in raw else end
                if not _was_refused(self.report, fields[end]):
                    self.report.add("job", prefix + spelling, f"there is no component '{fields[end]}'")
                ok = False
        if not ok:
            self._starved.add(fields["target"])
        if any(flow.name == fields["name"] for flow in job.flows):
            self.report.add("job", prefix + "name", f"the flow name '{fields['name']}' is used more than once")
            ok = False
        if not ok:
            self._starved.add(fields["target"])
            return None

        source = job.components[fields["source"]]
        if fields["type"] == "iterate":
            # No flow: no rows go by it. It is kept apart, and the two ends are different subjobs.
            self._iterate(fields, raw, prefix, job)
            return None
        port = fields["output"]
        if port is None:
            port = source.cls.port_for(fields["type"], fields["name"], source.config)
            if port is None:
                reason = source.cls.no_port_reason(fields["type"], fields["name"], source.config)
                self.report.add("job", prefix + "type", f"a {source.type} {reason}")
                self._starved.add(fields["target"])
                return None
        return Flow(name=fields["name"], source=fields["source"], target=fields["target"], kind=fields["type"], port=port)

    def _trigger(self, index: int, raw: Any, job: Job) -> Optional[Trigger]:
        prefix = f"triggers[{index}]."
        if not isinstance(raw, dict):
            self.report.add("job", f"triggers[{index}]", "expected an object")
            return None
        fields, refusals = normalize_config(raw, TRIGGER_KEYS, "job", _prefix=prefix)
        self.report.extend(refusals)
        if refusals:
            return None
        ok = True
        for end, v1_name in (("source", "from"), ("target", "to")):
            if fields[end] not in job.components:
                spelling = v1_name if v1_name in raw else end
                if not _was_refused(self.report, fields[end]):
                    self.report.add("job", prefix + spelling, f"there is no component '{fields[end]}'")
                ok = False
        if ok and not self._may_lead_to(fields["target"], prefix + ("to" if "to" in raw else "target"), job):
            ok = False
        kind = _TRIGGER_KINDS[fields["type"]]
        condition = fields["condition"]
        if kind == "RunIf":
            if not condition or not condition.strip():
                self.report.add("job", prefix + "condition", "a RunIf trigger needs a condition")
                ok = False
            elif condition.startswith(JAVA_PREFIX):
                self.report.add("job", prefix + "condition", JAVA_REASON)
                ok = False
        if not ok:
            return None
        return Trigger(
            kind=kind,
            source=fields["source"],
            target=fields["target"],
            condition=condition or None,
            order=fields["order"],
        )

    def _may_lead_to(self, target: str, where: str, job: Job) -> bool:
        """Whether a trigger or an iterate link may lead to a component; said in the report when it may not."""
        marked = job.components[target].cls
        if marked.part is None:
            return True
        what = "set-up" if marked.part == BEFORE else "clean-up"
        self.report.add(
            "job", where, f"'{target}' is a {marked.names[0]}: it is where a job's {what} starts, and nothing leads to it")
        return False

    def _iterate(self, fields: Dict[str, Any], raw: Dict[str, Any], prefix: str, job: Job) -> None:
        """Keep an iterate link, or say why it cannot be one."""
        source, target = job.components[fields["source"]], fields["target"]
        ends = {end: (v1_name if v1_name in raw else end) for end, v1_name in (("source", "from"), ("target", "to"))}
        if not self._may_lead_to(target, prefix + ends["target"], job):
            return
        if not source.cls.loops:
            self.report.add(
                "job", prefix + "type",
                f"a {source.type} starts no loop: an iterate link leaves a component that makes a list of items",
            )
            return
        already = next((link for link in job.iterates if link.source == source.id), None)
        if already is not None:
            self.report.add(
                "job", prefix + ends["source"],
                f"'{source.id}' has an iterate link already, to '{already.target}': a loop has one body",
            )
            return
        taken = next((link for link in job.iterates if link.target == target), None)
        if taken is not None:
            self.report.add("job", prefix + ends["target"], f"'{target}' is the start of the loop of '{taken.source}' already")
            return
        job.iterates.append(Iterate(fields["name"], source.id, target, side_by_side=fields["enable_parallel"]))
        self._iterate_ends[fields["name"]] = prefix + ends["target"]

    def _check_iterates(self, job: Job) -> None:
        """Refuse an iterate link that leads into the middle of a subjob, and triggers that cross a loop's edge."""
        subjob_of = {component_id: index for index, members in enumerate(subjobs(job)) for component_id in members}
        for link in job.iterates:
            arriving = job.incoming(link.target)
            if arriving:
                self.report.add(
                    "job", self._iterate_ends[link.name],
                    f"an iterate link leads to the start of a subjob, and '{link.target}' takes rows from "
                    f"'{arriving[0].source}'",
                )
        for started_by, body in bodies(job).items():
            link = next(link for link in job.iterates if link.source == started_by)
            for index, trigger in enumerate(job.triggers):
                source, target = subjob_of[trigger.source], subjob_of[trigger.target]
                if target == subjob_of[started_by] and source in body:
                    self.report.add(
                        "job", f"triggers[{index}]",
                        f"'{trigger.target}' starts the loop that runs '{trigger.source}': a trigger from inside the "
                        "loop cannot set it off again",
                    )
                elif target in body and source not in body:
                    self.report.add(
                        "job", f"triggers[{index}]",
                        f"'{trigger.target}' is run by the loop of '{link.source}', once for each item: a trigger "
                        f"from '{trigger.source}', which is not, cannot set it off",
                    )

    def _check_triggers(self, job: Job) -> None:
        """Refuse triggers that stay inside one subjob and triggers that go round in a loop."""
        subjob_of = {
            component_id: index for index, members in enumerate(subjobs(job)) for component_id in members
        }
        after: Dict[int, List[int]] = {}
        for index, trigger in enumerate(job.triggers):
            source, target = subjob_of[trigger.source], subjob_of[trigger.target]
            if source == target:
                self.report.add(
                    "job",
                    f"triggers[{index}]",
                    f"'{trigger.source}' and '{trigger.target}' are in the same subjob; "
                    "a trigger starts another subjob",
                )
            else:
                after.setdefault(source, []).append(target)

        state: Dict[int, int] = {}

        def loops(node: int) -> bool:
            if state.get(node) == 1:
                return True
            if state.get(node) == 2:
                return False
            state[node] = 1
            found = any(loops(following) for following in after.get(node, []))
            state[node] = 2
            return found

        if any(loops(node) for node in list(after)):
            self.report.add("job", "triggers", "the triggers form a loop")

    def _check_input_counts(self, job: Job) -> None:
        for spec in job.components.values():
            arriving = len(job.incoming(spec.id))
            flows = "1 flow arrives" if arriving == 1 else f"{arriving} flows arrive"
            limit = spec.cls.max_inputs
            if limit is not None and arriving > limit:
                takes = "takes no input" if limit == 0 else f"takes at most {limit} input(s)"
                self.report.add(spec.where, "inputs", f"{takes}, but {flows}")
            elif arriving < spec.cls.min_inputs and spec.id not in self._starved:
                self.report.add(spec.where, "inputs", f"needs {spec.cls.min_inputs} input(s), but {flows}")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _groups(declared: Any, group_name: Any) -> Optional[Dict[str, Any]]:
    """The context groups of a job config by their names; None when its context is not in groups."""
    if not isinstance(declared, dict) or not declared:
        return None
    if group_name is not None and isinstance(declared.get(group_name), dict):
        # v1's shape: default_context names the group to use, whatever its variables are called.
        return declared
    if all(isinstance(value, dict) and not _is_entry(value) for value in declared.values()):
        return declared
    return None


def _is_entry(value: Dict[str, Any]) -> bool:
    """Whether a context object is one variable (``{"value": ..., "type": ...}``) and not a group of them."""
    return "value" in value and set(value) <= {"value", "type"} and not isinstance(value["value"], dict)


def _java_paths(value: Any, path: str = "") -> List[str]:
    """Paths of every string in a config that is still a Java expression."""
    if isinstance(value, str):
        # A lookup and a join under the mark are not Java: the engine reads them when the component is built.
        return [path] if value.startswith(JAVA_PREFIX) and parsed(value[len(JAVA_PREFIX):]) is None else []
    found: List[str] = []
    if isinstance(value, dict):
        for name, item in value.items():
            found += _java_paths(item, f"{path}.{name}" if path else name)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found += _java_paths(item, f"{path}[{index}]")
    return found


def _under(key: str, paths: List[str]) -> bool:
    return any(key == path for path in paths)


def _was_refused(report: RefusalReport, component_id: str) -> bool:
    """Whether a component is missing because it was itself refused."""
    return any(refusal.where.startswith(f"component {component_id} (") for refusal in report)
