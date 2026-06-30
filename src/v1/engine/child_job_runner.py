"""ChildJobRunner -- runs a child job (tRunJob) in-process as a nested ETLEngine.

See docs/superpowers/specs/2026-06-30-trunjob-component-design.md.
"""
from __future__ import annotations

import logging
import os
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@dataclass
class RunContext:
    """Recursion/resolution state threaded through nested tRunJob calls."""
    base_dir: Optional[str]
    jobs_dir: Optional[str]
    call_stack: List[str]
    depth: int
    max_depth: int = 2


@dataclass
class ChildResult:
    """Outcome of one child-job run."""
    status: str
    return_code: int
    stacktrace: Optional[str] = None
