"""Shared helpers for XML engine components.

Provides a hardened XMLParser factory (replaces deprecated defusedxml.lxml per
Phase 12 RESEARCH.md P-1) and threshold-switched DOM/iterparse helpers used by
every in-scope XML engine component.

Public API:
    secure_xml_parser(recover=False) -> etree.XMLParser
    parse_xml_strategy(filename, threshold_mb) -> tuple[str, object]
    iterparse_loop_query(filename, loop_tag) -> Iterator[etree._Element]
    log_strategy(component_id, strategy, size_mb, threshold_mb) -> None

Security: resolve_entities=False (XXE), no_network=True, load_dtd=False
(billion-laughs vector). recover=False fails loud on malformed XML so callers
can route to REJECT instead of silently passing partial trees.
"""
import logging
import os
from typing import Iterator, Tuple

from lxml import etree

logger = logging.getLogger(__name__)


def secure_xml_parser(*, recover: bool = False) -> etree.XMLParser:
    """Build a hardened XMLParser.

    Disables external entity expansion (XXE), DTD loading (billion-laughs vector),
    and network access. recover=False fails loud on malformed XML so callers
    can route to REJECT instead of silently passing partial trees.

    Args:
        recover: If True, the parser recovers from malformed XML by silently
            dropping invalid content. Default False (strict mode).

    Returns:
        An etree.XMLParser configured with secure flags.
    """
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        recover=recover,
    )


def parse_xml_strategy(filename: str, threshold_mb: int) -> Tuple[str, object]:
    """Decide DOM vs streaming based on file size.

    For files below the threshold, loads the full DOM with a secure parser.
    For files at or above the threshold, returns the filename so the caller
    can invoke iterparse_loop_query for constant-memory streaming.

    Args:
        filename: Absolute path to the XML file.
        threshold_mb: Size boundary in megabytes. Files strictly below this
            value use DOM; files at or above this value use streaming.

    Returns:
        ('dom', etree._ElementTree) when size_mb < threshold_mb (full parse).
        ('stream', filename) when size_mb >= threshold_mb (caller calls
            iterparse_loop_query).

    Raises:
        FileNotFoundError / OSError: if filename does not exist (propagated
            from os.stat -- caller decides REJECT vs raise).
    """
    size_mb = os.stat(filename).st_size / (1024 * 1024)
    if size_mb < threshold_mb:
        tree = etree.parse(filename, parser=secure_xml_parser())
        return ("dom", tree)
    return ("stream", filename)


def iterparse_loop_query(filename: str, loop_tag: str) -> Iterator[etree._Element]:
    """Yield each `loop_tag` end-event element; clear after consume.

    Memory-correct: clears the matched element AND walks back removing prior
    siblings so the prefix tree is released (Pitfall P-3 mitigation). The
    secure flags (resolve_entities, no_network, load_dtd) are forwarded as
    iterparse keyword args -- lxml iterparse cannot accept an XMLParser
    instance directly, so the flags must be passed separately.

    Args:
        filename: Absolute path to the XML file.
        loop_tag: Tag name to match at end-event. Only elements with this tag
            are yielded; all other end events are discarded.

    Yields:
        Each matched lxml _Element. The element is cleared (text, children,
        and attributes freed) immediately after yield, so callers must consume
        any desired data BEFORE continuing the iteration.
    """
    # iterparse cannot accept an XMLParser directly; the secure flags must be
    # passed as keyword args (lxml 4.x+).
    ctx = etree.iterparse(
        filename,
        events=("end",),
        tag=loop_tag,
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        recover=False,
    )
    # IN-01 fix: wrap the iteration loop in try/finally so del ctx runs on ALL exit
    # paths -- including when the caller breaks out of the generator (e.g. LIMIT cap),
    # which causes GeneratorExit to be thrown at the yield point, bypassing the
    # post-loop del ctx. In CPython, reference counting releases ctx when the frame
    # is torn down regardless, so this is correctness-by-intent rather than a resource
    # leak fix -- but it makes the documented cleanup explicit and reliable.
    try:
        for _event, element in ctx:
            yield element
            # 1. clear the matched element (free its subtree, preserve tail text)
            element.clear(keep_tail=True)
            # 2. drop preceding siblings to release the prefix of the parent
            while element.getprevious() is not None:
                del element.getparent()[0]
    finally:
        del ctx


def log_strategy(
    component_id: str,
    strategy: str,
    size_mb: float,
    threshold_mb: int,
) -> None:
    """Emit a single ASCII-only INFO line so tests can spy on which branch ran.

    Pitfall P-4 mitigation: the threshold-switched code path must be observable
    in logs so integration tests and production monitoring can confirm which
    strategy was actually executed.

    Args:
        component_id: The engine component ID (e.g. 'tFileInputXML_1').
        strategy: Either 'dom' or 'stream'.
        size_mb: Measured file size in megabytes (float, 2 decimal places).
        threshold_mb: Configured threshold in megabytes (integer).
    """
    logger.info(
        "[%s] XML strategy=%s size=%.2fMB threshold=%dMB",
        component_id,
        strategy,
        size_mb,
        threshold_mb,
    )
