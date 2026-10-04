"""V1-to-V2 config converter.

Usage::

    from src.converters.v1_to_v2 import V1ToV2Converter

    v2_config = V1ToV2Converter(v1_config).convert()

CLI::

    python -m src.converters.v1_to_v2 input.json output.json
"""
from .converter import V1ToV2Converter

__all__ = ["V1ToV2Converter"]
