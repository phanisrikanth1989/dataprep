"""Components of the v2 engine.

Importing this package imports every module below it, which registers each
component with the registry. A new component needs no line added here.
"""
import importlib
import pkgutil

for _module in pkgutil.walk_packages(__path__, prefix=__name__ + "."):
    importlib.import_module(_module.name)
