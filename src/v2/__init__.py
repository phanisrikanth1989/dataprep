"""The v2 engine: pure Python on Polars, running v1 job configs.

Usage::

    from src.v2 import run_job

    result = run_job("job.json", context={"in_dir": "/data"})
    result.raise_for_status()
"""
from . import components  # noqa: F401 -- importing it registers every component
from .engine import JobResult, run_job
from .errors import ConfigurationError, ExpressionError, JobFailedError, JobRefusedError, V2Error
from .job.loader import load_job

__all__ = [
    "ConfigurationError",
    "ExpressionError",
    "JobFailedError",
    "JobRefusedError",
    "JobResult",
    "V2Error",
    "load_job",
    "run_job",
]
