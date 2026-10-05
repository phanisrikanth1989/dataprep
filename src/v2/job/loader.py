"""Load a job config into the model the engine runs.

A job config is read in v1's shape, which is the reference, with v2's own
spellings accepted beside it. Everything v2 will not run with is collected
into one refusal report and raised together, before anything runs.
"""
from __future__ import annotations

import copy
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from ..components.registry import REGISTRY, Registry
from .graph import loop, subjobs
from .keys import EXPRESSION, Key, Kind, normalize_config
from .model import TYPE_NAMES, Column, ComponentSpec, Flow, Job, Trigger
from .refusal import Refusal, RefusalReport

JAVA_PREFIX = "{{java}}"
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

COLUMN_KEYS: Tuple[Key, ...] = (
    Key("name", required=True, convert=_not_empty, doc="The column name."),
    Key("type", default="str", choices=tuple(TYPE_NAMES), doc="The column type."),
    Key("nullable", type=bool, default=True, doc="Whether missing values are allowed."),
    Key("key", type=bool, default=False, doc="Whether the column is part of the key."),
    Key("length", type=int, doc="Declared length."),
    Key("precision", type=int, doc="Declared number of decimal places."),
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
    if isinstance(source, (str, Path)):
        with open(source, encoding="utf-8") as handle:
            raw = json.load(handle)
    else:
        raw = copy.deepcopy(dict(source))
    return _Loader(raw, dict(context or {}), registry).load()


class _Loader:
    """Reads one job config, collecting refusals as it goes."""

    def __init__(self, raw: Dict[str, Any], overrides: Dict[str, Any], registry: Registry) -> None:
        self.raw = {key: value for key, value in raw.items() if not key.startswith("_")}
        self.overrides = overrides
        self.registry = registry
        self.report = RefusalReport(job_name=str(raw.get("job_name") or raw.get("name") or ""))
        # Components that lost an incoming flow to a refusal elsewhere; their input count proves nothing.
        self._starved: set = set()

    def load(self) -> Job:
        top, refusals = normalize_config(self.raw, JOB_KEYS, "job")
        self.report.extend(refusals)
        job = Job(name=top.get("name") or "")
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
        self._check_input_counts(job)
        stuck = loop(job)
        if stuck:
            self.report.add("job", "flows", f"the flows form a loop through: {', '.join(stuck)}")
        else:
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
        grouped = bool(declared) and all(
            isinstance(value, dict) and "value" not in value for value in declared.values()
        )
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
                values[name] = _typed(values[name], type_name)
            except (ValueError, InvalidOperation):
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

        java = _java_paths(raw_config)
        for path in java:
            self.report.add(where, path, JAVA_REASON)

        cls = self.registry.get(type_name)
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
        if fields["type"] == "iterate":
            self.report.add("job", prefix + "type", "iterate flows are not supported in v2")
            ok = False
        if not ok:
            self._starved.add(fields["target"])
            return None

        source = job.components[fields["source"]]
        port = fields["output"]
        if port is None:
            port = source.cls.port_for(fields["type"], fields["name"], source.config)
            if port is None:
                self.report.add(
                    "job", prefix + "type", f"a {source.type} has no '{fields['type']}' output"
                )
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

def _typed(value: Any, type_name: str) -> Any:
    """Convert a context value to its declared type."""
    kind = TYPE_NAMES.get(type_name, "str")
    if value is None or value == "":
        return value
    if kind == "int":
        if isinstance(value, bool):
            raise ValueError(value)
        return int(str(value).strip())
    if kind == "float":
        return float(str(value).strip())
    if kind == "Decimal":
        return Decimal(str(value).strip())
    if kind == "bool":
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in ("true", "1", "yes"):
            return True
        if text in ("false", "0", "no"):
            return False
        raise ValueError(value)
    if kind == "str":
        return str(value)
    return value


def _java_paths(value: Any, path: str = "") -> List[str]:
    """Paths of every string in a config that is still a Java expression."""
    if isinstance(value, str):
        return [path] if value.startswith(JAVA_PREFIX) else []
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
