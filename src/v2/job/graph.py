"""The shape of a job: its subjobs and the order components run in.

Both are worked out exactly as v1 does, so components with side effects
(printing rows, loading context) run in the order a v1 user has seen.
"""
from __future__ import annotations

from collections import deque
from graphlib import CycleError, TopologicalSorter
from typing import List, Optional

from .model import Job


def subjobs(job: Job) -> List[List[str]]:
    """Group a job's components into subjobs.

    A subjob is a set of components connected to each other by flows. Each
    one is returned as its component ids in the order they run: every
    component with nothing feeding it first, then what those feed, one layer
    at a time. Subjobs are returned in the job-config order of their first
    component.
    """
    return [_run_order(job, members) for members in _groups(job)]


def loop(job: Job) -> Optional[List[str]]:
    """The components caught in a loop of flows, or None when there is none."""
    stuck: List[str] = []
    for members in _groups(job):
        ordered = _run_order(job, members)
        stuck += [component_id for component_id in members if component_id not in ordered]
    return stuck or None


def _groups(job: Job) -> List[List[str]]:
    """Components connected by flows, each group in the order it is discovered."""
    seen = set()
    groups: List[List[str]] = []
    for start in job.components:
        if start in seen:
            continue
        group: List[str] = []
        queue = deque([start])
        while queue:
            current = queue.popleft()
            if current in seen:
                continue
            seen.add(current)
            group.append(current)
            for flow in job.flows:
                if flow.source == current and flow.target not in seen:
                    queue.append(flow.target)
                elif flow.target == current and flow.source not in seen:
                    queue.append(flow.source)
        groups.append(group)
    return groups


def _run_order(job: Job, members: List[str]) -> List[str]:
    """Order components so each comes after its inputs; a loop's members are left out."""
    inside = set(members)
    sorter: TopologicalSorter = TopologicalSorter()
    for component_id in members:
        sorter.add(component_id)
    for flow in job.flows:
        if flow.source in inside and flow.target in inside:
            sorter.add(flow.target, flow.source)
    try:
        return list(sorter.static_order())
    except CycleError:
        return _outside_loops(job, members)


def _outside_loops(job: Job, members: List[str]) -> List[str]:
    """The members that can still be ordered when some of them form a loop."""
    inside = set(members)
    waiting = {
        component_id: sum(1 for flow in job.incoming(component_id) if flow.source in inside)
        for component_id in members
    }
    ready = [component_id for component_id in members if waiting[component_id] == 0]
    ordered: List[str] = []
    while ready:
        current = ready.pop(0)
        ordered.append(current)
        for flow in job.outgoing(current):
            if flow.target in inside:
                waiting[flow.target] -= 1
                if waiting[flow.target] == 0:
                    ready.append(flow.target)
    return ordered
