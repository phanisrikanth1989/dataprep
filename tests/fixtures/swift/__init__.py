"""Synthetic SWIFT MT fixtures for Phase 14-07.

The package houses a synthetic MT-message generator (``synthetic.py``) plus
YAML layout / transform / lookup fixtures and pipeline-job JSON fixtures used
by ``tests/v1/engine/components/transform/test_swift_block_formatter.py`` and
``test_swift_transformer.py``.

Per Phase 14 D-A5: NO production SWIFT samples are used. All MT messages are
synthesised per the SWIFT user-handbook spec; ASCII-only.
"""
