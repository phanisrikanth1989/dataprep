"""Py4J byte[] decoding must be C-speed and identical to Py4J's own decoder.

Py4J 0.10.9.x decodes every ``byte[]`` returned by Java with a Python-level
per-byte loop (``bytearray2([bytetoint(b) for b in ...])``). Every Arrow
payload the bridge returns (tMap output, tJavaRow output, preprocessing
results) goes through it: on a 1M-row tMap that loop alone took ~30 of the
component's 44 seconds. The bridge module replaces it with the equivalent
single C call. These tests pin that the replacement is installed and returns
exactly what Py4J's own implementation returns -- same type, same bytes.
"""
import base64
import os

import pytest
import py4j.protocol as py4j_protocol
from py4j.compat import bytearray2, bytetoint, strtobyte

from src.v1.java_bridge import bridge as bridge_mod


def _py4j_reference_decode(encoded):
    """Verbatim copy of py4j 0.10.9.x ``protocol.decode_bytearray``."""
    new_bytes = strtobyte(encoded)
    return bytearray2([bytetoint(b) for b in base64.standard_b64decode(new_bytes)])


def _encode(payload: bytes) -> str:
    return base64.standard_b64encode(payload).decode("ascii")


@pytest.mark.unit
class TestFastBytearrayDecoder:
    """The fast decoder is installed and byte-identical to Py4J's."""

    def test_installed_on_bridge_import(self):
        assert py4j_protocol.decode_bytearray is bridge_mod._fast_decode_bytearray

    def test_output_converter_resolves_to_fast_decoder(self):
        """Py4J's BYTES_TYPE converter looks the function up at call time."""
        converter = py4j_protocol.OUTPUT_CONVERTER[py4j_protocol.BYTES_TYPE]
        assert converter(_encode(b"\x00\xffabc"), None) == b"\x00\xffabc"

    @pytest.mark.parametrize(
        "payload",
        [b"", b"\x00", b"\xff\xfe", bytes(range(256)), os.urandom(100_003)],
        ids=["empty", "zero", "high", "all-bytes", "random-100k"],
    )
    def test_matches_py4j_reference(self, payload):
        encoded = _encode(payload)
        fast = bridge_mod._fast_decode_bytearray(encoded)
        reference = _py4j_reference_decode(encoded)
        assert type(fast) is type(reference)
        assert fast == reference == payload

    def test_install_is_idempotent(self):
        bridge_mod._install_fast_py4j_bytearray_decoder()
        bridge_mod._install_fast_py4j_bytearray_decoder()
        assert py4j_protocol.decode_bytearray is bridge_mod._fast_decode_bytearray
