import re
from pathlib import Path

# Biased framing: the old skill name, "enrichment" anywhere (case-insensitive), and a word-boundary
# standalone "recon". The \b boundary EXCLUDES reconcile/reconciliation/reconstruct (a word char follows
# "recon"); "dataprep-recon" is caught by the first alternative regardless.
_BIAS = re.compile(r"dataprep-recon|enrichment|\brecon\b", re.IGNORECASE)


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
    """Whole-plan invariant: NO `enrichment` / standalone `recon` / `dataprep-recon` under .github or
    agents. Asserted empty in Final Verification (after Tasks 18-20 finish their owned-file scrubs)."""
    assert _scan() == {}, "biased framing (enrichment/recon) must not remain"
