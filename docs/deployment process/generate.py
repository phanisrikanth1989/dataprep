#!/usr/bin/env python3
"""DataPrep "Generate" tooling.

Reads a job JSON authored in DataPrepUI and scaffolds its supporting artifacts
(config skeleton, Autosys JIL, optional per-job script) from the templates in
this folder, following the RecTran deployment design.

The config keys are auto-derived from the job's ``context.*`` references. Values
are left empty for ops to fill per environment; secrets come from server env
vars at run time, never from here.

Design references: sections 5.2, 6, 9.4 of RecTran-Deployment-Design.md.
ASCII-only output (RHEL); files are written with LF newlines.

Usage:
    python generate.py fcc/json/customer_load.json --lob fcc \\
        --machine batch01 --owner etluser \\
        --days-of-week "mo,tu,we,th,fr" --start-times "02:00" \\
        --depends fcc_upstream_a --depends fcc_upstream_b \\
        [--envs dev uat prod] [--repo-root .] [--force-jil] [--with-script]

Requires Jinja2 (pip install jinja2).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Dict, List, Tuple

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    sys.stderr.write("ERROR: this tool needs Jinja2 (pip install jinja2)\n")
    raise

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ENVS = ["dev", "uat", "prod"]
DEFAULT_RUN_SCRIPT = "/app/dataprep/artifacts/scripts/run_job.sh"

# Matches context.var and ${context.var}; the lookbehind avoids matching a
# "context." that is part of a larger identifier (e.g. globalContext.foo).
_CTX_RE = re.compile(r"(?<![A-Za-z0-9_])context\.([A-Za-z_][A-Za-z0-9_]*)")


# ------------------------------------------------------------------
# Core helpers
# ------------------------------------------------------------------
def extract_context_vars(job_json_text: str) -> List[str]:
    """Return the sorted, de-duplicated context variables a job references."""
    return sorted(set(_CTX_RE.findall(job_json_text)))


def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(HERE),
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _write(path: str, text: str) -> None:
    """Write text with LF newlines; json.dump keeps content ASCII-safe."""
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


# ------------------------------------------------------------------
# Config (merge-safe: add new keys, never clobber filled values)
# ------------------------------------------------------------------
def build_config(context_vars: List[str], existing: Dict[str, str]) -> Dict[str, str]:
    rendered = _jinja_env().get_template("config.template.json").render(
        context_vars=context_vars
    )
    skeleton = json.loads(rendered) if rendered.strip() else {}
    merged: Dict[str, str] = {}
    for key in skeleton:
        merged[key] = existing.get(key, "")           # keep filled value, else empty
    for key, val in existing.items():
        merged.setdefault(key, val)                    # preserve extra existing keys
    return merged


def write_config_files(repo_root: str, lob: str, context_vars: List[str],
                       envs: List[str]) -> List[str]:
    cfg_dir = os.path.join(repo_root, lob, "config")
    os.makedirs(cfg_dir, exist_ok=True)
    written = []
    for env_name in envs:
        path = os.path.join(cfg_dir, f"config.{env_name}.json")
        existing: Dict[str, str] = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                existing = json.load(fh)
        merged = build_config(context_vars, existing)
        _write(path, json.dumps(merged, indent=2) + "\n")
        written.append(path)
    return written


# ------------------------------------------------------------------
# JIL (skip if present unless --force-jil, to preserve hand-tuning)
# ------------------------------------------------------------------
def render_jil(meta: Dict) -> str:
    return _jinja_env().get_template("job.template.jil").render(**meta)


def write_jil(repo_root: str, lob: str, job_name: str, meta: Dict,
              force: bool) -> Tuple[str, bool]:
    jil_dir = os.path.join(repo_root, lob, "jil")
    os.makedirs(jil_dir, exist_ok=True)
    path = os.path.join(jil_dir, f"{lob}_{job_name}.jil")
    if os.path.exists(path) and not force:
        return path, False                             # preserve tuned schedule/deps
    _write(path, render_jil(meta))
    return path, True


# ------------------------------------------------------------------
# Optional per-job script
# ------------------------------------------------------------------
def write_script(repo_root: str, lob: str, job_name: str, meta: Dict) -> str:
    script_dir = os.path.join(repo_root, lob, "scripts")
    os.makedirs(script_dir, exist_ok=True)
    path = os.path.join(script_dir, f"{lob}_{job_name}.sh")
    _write(path, _jinja_env().get_template("run.template.sh").render(**meta))
    return path


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------
def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Generate config/JIL/script for a DataPrep job JSON."
    )
    p.add_argument("job_json", help="Path to the authored job JSON (under <lob>/json/).")
    p.add_argument("--lob", required=True, help="Line of business (e.g. fcc).")
    p.add_argument("--repo-root", default=".", help="RecTran repo root (default: .).")
    p.add_argument("--envs", nargs="+", default=DEFAULT_ENVS,
                   help="Environments for config files (default: dev uat prod).")
    # JIL form inputs (section 5.2)
    p.add_argument("--machine", default="REPLACE_ME", help="Autosys target machine.")
    p.add_argument("--owner", default="REPLACE_ME", help="Autosys job owner.")
    p.add_argument("--days-of-week", default="mo,tu,we,th,fr")
    p.add_argument("--start-times", default="02:00")
    p.add_argument("--depends", action="append", default=[],
                   help="Upstream job name (repeatable).")
    p.add_argument("--max-run-alarm", type=int, default=60)
    p.add_argument("--description", default="")
    p.add_argument("--run-script", default=DEFAULT_RUN_SCRIPT)
    p.add_argument("--force-jil", action="store_true",
                   help="Overwrite existing JIL (loses hand-tuning).")
    p.add_argument("--with-script", action="store_true",
                   help="Also generate a per-job wrapper script.")
    args = p.parse_args(argv)

    job_name = os.path.splitext(os.path.basename(args.job_json))[0]
    with open(args.job_json, "r", encoding="utf-8") as fh:
        job_text = fh.read()
    context_vars = extract_context_vars(job_text)

    cfg_paths = write_config_files(args.repo_root, args.lob, context_vars, args.envs)

    condition_expr = " and ".join(f"success({dep})" for dep in args.depends)
    meta = {
        "lob": args.lob,
        "job_name": job_name,
        "machine": args.machine,
        "owner": args.owner,
        "days_of_week": args.days_of_week,
        "start_times": args.start_times,
        "dependencies": args.depends,
        "condition_expr": condition_expr,
        "max_run_alarm": args.max_run_alarm,
        "description": args.description or f"{args.lob} {job_name}",
        "run_script": args.run_script,
        "pre_hook": "# (none)",
        "post_hook": "# (none)",
    }
    jil_path, jil_written = write_jil(args.repo_root, args.lob, job_name, meta, args.force_jil)

    script_path = None
    if args.with_script:
        script_path = write_script(args.repo_root, args.lob, job_name, meta)

    # ---- report ----
    print(f"Job: {args.lob}/{job_name}")
    print(f"Context vars ({len(context_vars)}): {', '.join(context_vars) or '(none)'}")
    for cfg in cfg_paths:
        print(f"  config: {cfg}")
    jil_note = "(written)" if jil_written else "(kept existing - use --force-jil to overwrite)"
    print(f"  jil:    {jil_path} {jil_note}")
    if script_path:
        print(f"  script: {script_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
