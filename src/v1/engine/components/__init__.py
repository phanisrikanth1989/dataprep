# Auto-import sub-packages to trigger decorator-based registry registration.
# Each component module uses @REGISTRY.register() which registers on import.

from . import file  # noqa: F401
from . import transform  # noqa: F401
