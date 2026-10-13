"""What the tests of file exist, file copy and file delete share: one action alone in a job, run in a folder."""
import os

from src.v2 import run_job
from tests.v2.components.kit import job


def action(component_id, kind, **config):
    return {"id": component_id, "type": kind, "config": config, "inputs": [], "outputs": [],
            "schema": {"input": [], "output": []}}


def filled(folder, files):
    """Make a folder with files in it; a name that ends in / is a folder."""
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        target = folder / name
        if name.endswith("/"):
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return folder


def tree(folder):
    """Every file under a folder with its bytes, and every folder with None."""
    return {path.relative_to(folder).as_posix() + ("/" if path.is_dir() else ""): None if path.is_dir() else path.read_bytes()
            for path in sorted(folder.rglob("*"))}


def on_v2(made, folder):
    previous = os.getcwd()
    os.chdir(folder)
    try:
        return run_job(made)
    finally:
        os.chdir(previous)


def on_v1(made, folder):
    """Run on v1 in a folder; returns (whether it finished, its globalMap)."""
    from src.v1.engine.engine import ETLEngine
    previous = os.getcwd()
    os.chdir(folder)
    try:
        engine = ETLEngine(made)
        return engine.execute().get("status") == "success", engine.global_map
    finally:
        os.chdir(previous)


def both(component, files, tmp_path):
    """Run one action on both engines, each in its own folder with the same files. Returns (v1's, v2's) results
    and asserts that the two folders hold the same afterwards."""
    made = job([component], [])
    one, two = filled(tmp_path / "v1", files), filled(tmp_path / "v2", files)
    finished, held = on_v1(made, one)
    result = on_v2(made, two)
    assert (result.status == "success") is finished, result.error
    assert tree(two) == tree(one)
    return held, result
