import re
from pathlib import Path

# Biased framing (all case-insensitive): the old skill name `dataprep-recon`, "enrichment" anywhere,
# "reconciliation" anywhere (a plain substring -- the \brecon\b boundary MISSES it because a word char
# follows "recon"), "SmartStream", a standalone "TLM", and a word-boundary standalone "recon".
# "dataprep-recon" is caught by the first alternative regardless of the \b on the last one.
_BIAS = re.compile(
    r"dataprep-recon|enrichment|reconciliation|smartstream|\bTLM\b|\brecon\b", re.IGNORECASE
)


def _scan():
    offenders = {}
    for base in (Path(".github"), Path("agents")):   # docs/ is frozen history -> out of scope
        for f in base.rglob("*"):
            if not f.is_file() or f.suffix in (".pyc",) or "__pycache__" in f.parts:
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue  # skip binaries (e.g. a stale example .docx)
            hits = sorted({m.group(0).lower() for m in _BIAS.finditer(text)})
            if hits:
                offenders[str(f)] = hits
    return offenders


def test_no_dataprep_recon_string_remains():
    """Hard gate for THIS task: the mechanical skill rename left no `dataprep-recon` anywhere."""
    offenders = [f for f, hits in _scan().items() if "dataprep-recon" in hits]
    assert offenders == [], f"dataprep-recon must not remain: {offenders}"


def test_no_biased_framing_remains():
    """Whole-plan invariant: NO `enrichment` / `reconciliation` / standalone `recon` / `TLM` /
    `SmartStream` / `dataprep-recon` under .github or agents. Asserted empty in Final Verification
    (after Tasks 18-20 finish their owned-file scrubs)."""
    assert _scan() == {}, "biased framing (enrichment/recon/reconciliation/TLM/SmartStream) must not remain"
