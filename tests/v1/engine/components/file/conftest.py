"""Shared pytest fixtures for engine file-component tests.

Provides synthetic_60mb_xml: a programmatically generated ~60 MB XML file
used by streaming-path tests across plans 12-02 (this) and 12-03..12-07.
The fixture is built fresh per session in tmp_path; nothing persists in
the repo.
"""
import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def synthetic_60mb_xml(tmp_path_factory) -> Path:
    """Build a ~60 MB XML file once per pytest session.

    Structure: <root><item><id>N</id><payload>{1KB}</payload></item> * ~60_000</root>
    Used by streaming-path tests across plans 12-02..12-07.

    The file is written to a session-scoped temp directory and is never
    committed to the repo. Each test session gets a fresh copy.

    Returns:
        Path to the generated XML file (guaranteed 55-65 MB).
    """
    path = tmp_path_factory.mktemp("xml_streaming") / "synthetic_60mb.xml"
    payload = "x" * 1000  # 1 KB per item
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<root>\n')
        for i in range(60_000):  # ~60_000 KB == ~60 MB
            f.write(
                "<item>"
                "<id>" + str(i) + "</id>"
                "<payload>" + payload + "</payload>"
                "</item>\n"
            )
        f.write("</root>\n")
    size_mb = os.stat(path).st_size / (1024 * 1024)
    assert 55 <= size_mb <= 65, (
        "synthetic XML size %.2fMB outside 55-65 MB band" % size_mb
    )
    return path
