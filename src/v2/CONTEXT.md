# v2 Engine

The pure-Python, Polars-based ETL engine in `src/v2/`. It runs v1 job configs at
Polars speed and refuses what it cannot run that way. (Map:
`.scratch/engine-v2/map.md`.)

## Language

### Job configs

**Job config**:
The JSON document that describes one job: its context, components, flows and
triggers.
_Avoid_: v1 JSON, v2 JSON, job file

**Config key**:
A named setting in a job config, at any level: the job, a component, a flow or
a schema column.
_Avoid_: tag, param, feature

**Supported config key**:
A config key v2 implements; setting it changes what the job does.

**Ignored config key**:
A config key v2 accepts and gives no effect, because it never affected the
data: a label, a canvas position.
_Avoid_: harmless key

**Refused config key**:
A config key whose presence stops a job at load: one Polars cannot honour at
speed, or one no component declares.
_Avoid_: unsupported feature

**Alias**:
A v1 spelling of a config key that v2 accepts in place of its own. v2's
spelling is the documented one.

**Refusal report**:
The single list, produced at load, of everything in a job config that v2
refuses.

### Running jobs

**Expression**:
A piece of Python inside a job config that computes a value. It is translated
into Polars once, when the job loads, and never run row by row.

**Subjob**:
A group of components connected to each other by flows. Triggers connect
subjobs.
_Avoid_: stage

**Answer key**:
v1's output for a job config. v2's output for the same job must equal it.
