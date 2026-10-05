"""The shape of a job: its subjobs and the order components run in."""
from __future__ import annotations

from typing import Dict, List, Optional

from .model import Job


def subjobs(job: Job) -> List[List[str]]:
    """Group a job's components into subjobs.

    A subjob is a set of components connected to each other by flows. Each
    one is returned as its component ids in the order they run: a component
    comes after everything that feeds it, and job-config order breaks ties.
    Subjobs are returned in the job-config order of their first component.
    """
    position = {component_id: index for index, component_id in enumerate(job.components)}
    group: Dict[str, str] = {component_id: component_id for component_id in job.components}

    def find(component_id: str) -> str:
        while group[component_id] != component_id:
            group[component_id] = group[group[component_id]]
            component_id = group[component_id]
        return component_id

    for flow in job.flows:
        first, second = sorted((find(flow.source), find(flow.target)), key=position.get)
        group[second] = first

    members: Dict[str, List[str]] = {}
    for component_id in job.components:
        members.setdefault(find(component_id), []).append(component_id)
    return [_run_order(job, ids, position) for ids in members.values()]


def loop(job: Job) -> Optional[List[str]]:
    """The components caught in a loop of flows, or None when there is none."""
    position = {component_id: index for index, component_id in enumerate(job.components)}
    ordered = _run_order(job, list(job.components), position)
    stuck = [component_id for component_id in job.components if component_id not in ordered]
    return stuck or None


def _run_order(job: Job, ids: List[str], position: Dict[str, int]) -> List[str]:
    """Order components so each comes after its inputs; a loop's members are left out."""
    inside = set(ids)
    waiting = {
        component_id: sum(1 for flow in job.incoming(component_id) if flow.source in inside)
        for component_id in ids
    }
    ready = sorted((cid for cid, count in waiting.items() if count == 0), key=position.get)
    ordered: List[str] = []
    while ready:
        current = ready.pop(0)
        ordered.append(current)
        for flow in job.outgoing(current):
            if flow.target in inside:
                waiting[flow.target] -= 1
                if waiting[flow.target] == 0:
                    ready.append(flow.target)
                    ready.sort(key=position.get)
    return ordered
