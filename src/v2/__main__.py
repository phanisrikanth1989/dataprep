"""Entry point of the v2 engine's command line.

    python -m src.v2 job.json                 from the project's folder
    python /opt/dataprep/src/v2 job.json      from any folder, by the engine's own path
"""
import sys

if __package__:
    from .cli import main
else:
    # Started by its path. Python then looks for modules in this folder first, where `types.py` and others
    # would be taken for the standard library's; it has to look in the project's folder instead.
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    sys.path[:] = [entry for entry in sys.path if os.path.abspath(entry or os.getcwd()) != here]
    sys.path.insert(0, os.path.dirname(os.path.dirname(here)))
    from src.v2.cli import main

if __name__ == "__main__":
    sys.exit(main())
