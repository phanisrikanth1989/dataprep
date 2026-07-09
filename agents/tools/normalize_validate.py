"""Deterministic validator: resolve exploder handles, derive a rung from handle TYPE, and merge located handles into exact row-dicts."""
from __future__ import annotations

import csv
import io
import json
import logging
import re
from pathlib import Path

from agents.tools.extract_doc import compute_derived_facts

logger = logging.getLogger(__name__)

_EXACT_RUNGS = ("1", "2")  # only file/table exactness earns "verified"; everything else fails closed
_VALID_RULE_KINDS = frozenset({"join", "schema_validate", "filter", "aggregate", "sort", "derive"})
_STATUS_EXIT = {"ok": 0, "shape_error": 3, "needs_human": 4}  # validator status -> process exit code


class NeedsHuman(Exception):
    """Raised when a merge/reorder cannot be reconciled deterministically; the caller routes to needs_human."""


def _resolve(handle_id, inventory) -> dict | None:
    """Return the inventory handle dict whose id matches handle_id, or None when it is not a member."""
    for handle in inventory.get("handles", []):
        if handle.get("id") == handle_id:
            return handle
    return None


def _derive_rung(handle_id, inventory) -> str:
    """Grade a handle into "1"|"2"|"3a"|"needs_human" from its type alone; fail-closed catch-all is needs_human."""
    handle = _resolve(handle_id, inventory)
    if handle is None:
        return "needs_human"  # unresolved -> cannot grade
    htype = handle.get("type")
    ref = (handle.get("path") or handle.get("id") or "").lower()  # path when extracted, else id (both carry the ext)
    if htype in ("embed", "sibling"):
        if ref.endswith((".xlsx", ".xls")):
            return "needs_human"  # Phase 2 adds the xlsx reader
        if ref.endswith(".csv") and handle.get("csv_dialect") is not None:
            return "1"
    if htype == "table":
        return "2"
    if htype in ("image", "prose"):
        return "3a"
    return "needs_human"  # fail-closed default: null-dialect CSV, unrecognized handle -> never a silent grade


# ------------------------------------------------------------------
# Exact-byte readers: located handle -> list of raw-string row-dicts.
# ------------------------------------------------------------------
def _read_csv_handle(handle) -> list[dict]:
    """Read a rung-1 CSV at handle['path'] with the recorded dialect; first row = header, cells emitted as str."""
    dialect = handle.get("csv_dialect") or {}
    delimiter = dialect.get("delimiter") or ","
    quotechar = dialect.get("quotechar") or '"'
    with open(handle["path"], "r", encoding="utf-8", errors="replace", newline="") as fh:
        raw = list(csv.reader(fh, delimiter=delimiter, quotechar=quotechar))
    if not raw:
        return []
    header = [str(cell) for cell in raw[0]]
    rows: list[dict] = []
    for record in raw[1:]:
        rows.append({header[i]: (str(record[i]) if i < len(record) else "") for i in range(len(header))})
    return rows


def _read_table_handle(handle) -> list[dict]:
    """Read a rung-2 table handle: disambiguated 'columns' are keys, 'cells[1:]' are data rows (str)."""
    columns = [str(c) for c in (handle.get("columns") or [])]
    cells = handle.get("cells") or []
    rows: list[dict] = []
    for record in cells[1:]:  # cells[0] is the header row
        rows.append({columns[i]: (str(record[i]) if i < len(record) else "") for i in range(len(columns))})
    return rows


# ------------------------------------------------------------------
# Merge: pick the winning candidate by precedence, read its exact rows.
# ------------------------------------------------------------------
_RUNG_RANK = {"1": 0, "2": 1, "3a": 2}  # lower is better: CSV file > Word table > transcription


def _merge_source(name, candidates, proposal, inventory, side="sample_input"):
    """Pick the best-rung candidate (file>table>transcribed) and read its exact rows; return (rows, provenance)."""
    best = None  # (rank, rung, handle_id)
    for handle_id in candidates:
        rung = _derive_rung(handle_id, inventory)
        rank = _RUNG_RANK.get(rung)
        if rank is None:
            continue  # a needs_human candidate is unusable; skip it
        if best is None or rank < best[0]:
            best = (rank, rung, handle_id)
    if best is None:
        raise NeedsHuman(f"source {name!r}: no usable candidate handle (all needs_human): {candidates}")
    _rank, rung, handle_id = best
    delimiter = None
    if rung == "1":
        handle = _resolve(handle_id, inventory)
        rows = _read_csv_handle(handle)
        # Preserve the delimiter the exploder SNIFFED for this file so the harness
        # materializes it (and the configurator reads it back) with the SAME separator --
        # never a hard-coded ';'. A rung-2 table / rung-3 transcription has no source file,
        # so no delimiter to carry (materialize falls back to its default there).
        delimiter = (handle.get("csv_dialect") or {}).get("delimiter")
    elif rung == "2":
        rows = _read_table_handle(_resolve(handle_id, inventory))
    else:  # "3a": the LLM transcribed the rows into the proposal (image/prose only)
        rows = list(proposal.get(side, {}).get(name, []))
    prov = {"rung": rung, "handle": handle_id}
    if delimiter:
        prov["delimiter"] = delimiter
    return rows, prov


# ------------------------------------------------------------------
# Column-order reconcile (the engine binds CSV columns POSITIONALLY).
# ------------------------------------------------------------------
def _normalize_col(name) -> str:
    """Fold a column name to a match key: lowercase, then drop all whitespace and punctuation."""
    return re.sub(r"[^a-z0-9]+", "", str(name).strip().lower())


def _reconcile_columns(src_cols, schema_cols) -> dict:
    """Map each schema col to a source col by exact, then normalized, then positional; raise NeedsHuman otherwise."""
    src_cols = list(src_cols)
    schema_cols = list(schema_cols)
    # (i) exact: identical name-set (order-independent), no duplicates, 1:1.
    if (len(src_cols) == len(schema_cols)
            and len(set(src_cols)) == len(src_cols)
            and set(src_cols) == set(schema_cols)):
        return {sc: sc for sc in schema_cols}
    # (ii) normalized: fold case/space/punct; require a clean 1:1 on both sides.
    src_norm = {_normalize_col(c): c for c in src_cols}
    sch_norm = [_normalize_col(c) for c in schema_cols]
    if (len(src_cols) == len(schema_cols)
            and len(src_norm) == len(src_cols)           # no source collisions
            and len(set(sch_norm)) == len(schema_cols)   # no schema collisions
            and set(src_norm.keys()) == set(sch_norm)):
        return {sc: src_norm[_normalize_col(sc)] for sc in schema_cols}
    # (iii) positional: counts match -> bind by position (matches the engine's positional binding).
    if len(src_cols) == len(schema_cols):
        return {schema_cols[i]: src_cols[i] for i in range(len(schema_cols))}
    # Unreconcilable name/count mismatch -> only the validator guards this; fail closed.
    raise NeedsHuman(
        f"cannot reconcile columns {src_cols} to schema order {schema_cols} "
        f"(count {len(src_cols)} != {len(schema_cols)})")


def _reorder_to_schema(rows, schema_cols) -> list[dict]:
    """Reorder each row-dict so its key order MATCHES schema_cols; reconcile exact/normalized/positional or raise NeedsHuman."""
    if not rows:
        return list(rows)  # empty stays empty; nothing to reorder
    mapping = _reconcile_columns(list(rows[0].keys()), schema_cols)
    reordered: list[dict] = []
    for row in rows:
        rebuilt: dict = {}
        for sc in schema_cols:
            src = mapping[sc]
            if src not in row:  # a ragged LATER row (row0 had this key, this row does not) -> fail closed
                raise NeedsHuman(f"ragged rows: row is missing column {src!r}")
            rebuilt[sc] = row[src]
        reordered.append(rebuilt)
    return reordered


def _reconcile_expected(rows, output_cols):
    """Reorder expected rows to the proposed output name-space if it reconciles; else keep the header and flag low-confidence (Phase 1 never hard-fails the expected side)."""
    if not output_cols:
        return list(rows), (
            "expected-output name-space not reconciled: no proposed output columns supplied; kept expected header")
    try:
        return _reorder_to_schema(rows, output_cols), None
    except NeedsHuman as exc:
        return list(rows), f"expected-output name-space not reconciled ({exc}); kept expected header"


# ------------------------------------------------------------------
# Role/content-distinctness guard: a graded output must differ from every
# input (else a byte-passthrough oracle can't tell a transform from a no-op).
# ------------------------------------------------------------------
def _materialized_bytes(rows) -> bytes:
    """Serialize rows to the exact ';'-delimited CSV bytes materialize_golden would write (header = first row's keys)."""
    if not rows:
        return b""
    header = list(rows[0].keys())
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow([row.get(col, "") for col in header])
    return buf.getvalue().encode("utf-8")


def _distinctness(sample_input, expected_output) -> set:
    """Return graded-output names to DEGRADE: content byte-identical to a sample source (passthrough) or shared across roles."""
    source_keys = {_materialized_bytes(rows) for rows in (sample_input or {}).values() if rows}
    output_keys: dict[bytes, list] = {}
    for name, rows in (expected_output or {}).items():
        if rows:  # only graded (>=1 row) outputs are gradable, so only they can be degraded
            output_keys.setdefault(_materialized_bytes(rows), []).append(name)
    degrade: set = set()
    for key, names in output_keys.items():
        if key in source_keys or len(names) > 1:  # before==after passthrough, or one handle in >1 role
            degrade.update(names)
    return degrade


# ------------------------------------------------------------------
# Name normalization: NL BRD label -> safe filename component, with
# deterministic collision disambiguation (never collapse two into one key).
# ------------------------------------------------------------------
_ILLEGAL_NAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")  # keep filename-safe chars; fold the rest to "_"


def _safe_output_name(name) -> str:
    """Sanitize a natural-language name into one safe filename component (fold illegal chars to '_', collapse, strip)."""
    folded = re.sub(r"_+", "_", _ILLEGAL_NAME_CHARS.sub("_", str(name))).strip("_")
    return folded if folded not in ("", ".", "..") else "_"  # neutralize empty and dot-traversal components


def _safe_output_names(names) -> dict:
    """Map each name to a UNIQUE safe filename component, disambiguating collisions with a deterministic '_N' suffix."""
    mapping: dict = {}
    used: set = set()
    for name in names:
        base = _safe_output_name(name)
        candidate, index = base, 2
        while candidate in used:
            candidate, index = f"{base}_{index}", index + 1
        used.add(candidate)
        mapping[name] = candidate
    return mapping


# ------------------------------------------------------------------
# output_keys verification (COMPOSITE tuple-uniqueness) + conformance synthesis.
# ------------------------------------------------------------------
def _verify_output_keys(name, keys, expected_rows) -> list:
    """Accept a COMPOSITE key only if its tuple is unique across every expected row; else fall back to [] (bag) + low_confidence."""
    keys = list(keys or [])
    rows = list(expected_rows or [])
    if keys and len({tuple(r.get(c) for c in keys) for r in rows}) == len(rows):
        return keys
    if keys:
        logger.warning(
            "[normalize_validate] output %s: composite key %s not unique across %d expected row(s); "
            "falling back to bag/multiset (low_confidence)", name, keys, len(rows))
    return []


def _conformance_ok() -> dict:
    """Synthesize a passing conformance report for a real BRD (no template blocks; completeness lives in extraction.status)."""
    return {"ok": True, "missing_blocks": [], "parse_errors": []}


# ------------------------------------------------------------------
# Tier: enforced deterministically at the grading boundary (spec Section 7).
# Fail-closed: a missing/unknown rung is NEVER exact -> never earns "verified".
# ------------------------------------------------------------------
def _is_exact(name, provenance) -> bool:
    """True only if `name` has a provenance rung in {1,2}; a missing entry/rung is NOT exact (fail-closed)."""
    return (provenance.get(name) or {}).get("rung") in _EXACT_RUNGS


def _compute_tier(provenance, expected_graded, distinct_ok) -> str:
    """Grade the job tier (verified|smoke|build), quantified over EVERY source AND EVERY graded output; fail-closed."""
    graded = list(expected_graded or [])
    graded_set = set(graded)
    sources = [name for name in provenance if name not in graded_set]  # non-graded provenance == sample sources
    if not sources:
        return "build"  # no parseable sample source present
    verified = (
        bool(graded)                                       # at least one gradable oracle exists
        and all(_is_exact(s, provenance) for s in sources)  # EVERY source rung 1-2
        and all(_is_exact(g, provenance) for g in graded)   # EVERY graded output rung 1-2
        and bool(distinct_ok)                               # role/content distinctness holds
    )
    return "verified" if verified else "smoke"


# ------------------------------------------------------------------
# Section-9 completeness cross-check: account for EVERY inventory handle.
# ------------------------------------------------------------------
def _cross_check_coverage(inventory, coverage_map, emitted, unresolved=None) -> tuple:
    """Return (unaccounted, unresolved): a handle is accounted only with a disposition AND (extracted_to) all refs emitted."""
    emitted_set = set(emitted or ())
    by_handle = {}
    for entry in coverage_map or []:
        hid = entry.get("handle")
        if hid is not None:
            by_handle[hid] = entry  # last entry wins on a duplicate handle
    handle_ids = [h.get("id") for h in inventory.get("handles", []) if h.get("id") is not None]
    accounted = set()
    for hid in handle_ids:
        entry = by_handle.get(hid)
        if entry is None:
            continue  # no disposition at all -> unaccounted (fail-closed)
        disposition = entry.get("disposition")
        if disposition == "extracted_to":
            refs = entry.get("refs") or []
            if refs and all(ref in emitted_set for ref in refs):  # content-checked, not trivially satisfiable
                accounted.add(hid)
        elif disposition in ("irrelevant", "could_not_interpret"):
            accounted.add(hid)  # a disposition with no ref obligation
        # any other/unknown disposition -> not accounted (fail-closed)
    unaccounted = [hid for hid in handle_ids if hid not in accounted]
    return unaccounted, list(unresolved or [])


# ------------------------------------------------------------------
# Rung-aware derived facts: a rung-3 source is NOT trusted to declare a
# unique key, so emit the conservative (ambiguity-raising) value.
# ------------------------------------------------------------------
def _rung_aware_facts(sample_input, provenance) -> dict:
    """Compute derived facts; for a rung-3 (3a/3b) source force unique=False and max_group_size>=2 (conservative)."""
    facts = compute_derived_facts(sample_input)
    for source, col_facts in facts.items():
        if (provenance.get(source) or {}).get("rung") in ("3a", "3b"):
            for col_fact in col_facts.values():
                col_fact["unique"] = False  # never claim a verified-unique key off unverified rows
                if col_fact.get("max_group_size", 0) <= 1:
                    col_fact["max_group_size"] = 2  # raise doc-interpreter's non-unique-key ambiguity
    return facts


# ------------------------------------------------------------------
# assemble: tie the merge/guard helpers into the final extract_doc.json.
# ------------------------------------------------------------------
def _build_emitted(source_names, output_names, sources_schema, output_keys_proposed, expected_output, rules, extra_sections, name_map) -> set:
    """Build the set of ref targets a coverage entry may resolve to (raw AND sanitized names, schema/output fields, rule ids, headings)."""
    emitted: set = set()
    for source in source_names:
        emitted.update({source, name_map[source]})
        for col_spec in sources_schema.get(source, []):
            col = col_spec.get("name")
            if col is not None:
                emitted.update({f"{source}.{col}", f"{name_map[source]}.{col}"})
    for output in output_names:
        emitted.update({output, name_map[output]})
        cols = set(output_keys_proposed.get(output, []))
        rows = expected_output.get(output, [])
        if rows:
            cols.update(rows[0].keys())
        for col in cols:
            emitted.update({f"{output}.{col}", f"{name_map[output]}.{col}"})
    for rule in rules or []:
        rid = rule.get("id")
        if rid is not None:
            emitted.add(rid)
    emitted.update(extra_sections or {})
    return emitted


def assemble(proposal, inventory, model_id="") -> tuple:
    """Integrate proposal+inventory into the final extract_doc.json dict; return (extract_dict, extraction status)."""
    sources_schema = proposal.get("sources_schema", {}) or {}
    rules = proposal.get("rules", []) or []
    notes = proposal.get("notes", "") or ""
    extra_sections = proposal.get("extra_sections", {}) or {}
    output_keys_proposed = proposal.get("output_keys", {}) or {}
    located = proposal.get("located", {}) or {}
    located_sample = located.get("sample_input", {}) or {}
    located_expected = located.get("expected_output", {}) or {}
    coverage_map = proposal.get("coverage_map", []) or []
    low_confidence = list(proposal.get("low_confidence", []) or [])

    source_names = list(sources_schema.keys())
    output_names = list(located_expected.keys())

    sample_input: dict = {}   # original name -> exact rows (schema order)
    expected_output: dict = {}
    provenance: dict = {}     # original name -> {"rung", "handle"}
    unresolved_names: list = []

    # ---- 1. Merge each sample_input source (HARD: unreconcilable -> unresolved) ----
    for source in source_names:
        schema_cols = [c.get("name") for c in sources_schema.get(source, [])]
        try:
            rows, prov = _merge_source(source, located_sample.get(source, []), proposal, inventory, side="sample_input")
            sample_input[source] = _reorder_to_schema(rows, schema_cols)
            provenance[source] = prov
        except NeedsHuman as exc:
            logger.warning("[normalize_validate] source %s unresolved: %s", source, exc)
            unresolved_names.append(source)

    # ---- 2. Merge each expected_output (SOFT name-space; only a missing data handle is unresolved) ----
    for output in output_names:
        try:
            rows, prov = _merge_source(output, located_expected.get(output, []), proposal, inventory, side="expected_output")
        except NeedsHuman as exc:
            logger.warning("[normalize_validate] output %s unresolved: %s", output, exc)
            unresolved_names.append(output)
            continue
        proposed_keys = list(output_keys_proposed.get(output, []))
        header = list(rows[0].keys()) if rows else []
        # Reorder to the proposed key name-space only when it is a full-width column list; else keep the header (soft).
        output_cols = proposed_keys if (proposed_keys and header and len(proposed_keys) == len(header)) else []
        merged_rows, note = _reconcile_expected(rows, output_cols)
        expected_output[output] = merged_rows
        provenance[output] = prov
        if note and output_cols:
            low_confidence.append(note)

    # ---- 3. Graded set + guards (pinned to materialize_golden: rows > 0) ----
    graded = [name for name, rows in expected_output.items() if len(rows) > 0]
    missing_prov_graded = [name for name in graded if name not in provenance]
    distinct_ok = not _distinctness(sample_input, expected_output)

    # ---- 4. output_keys (COMPOSITE tuple-uniqueness) + low_confidence flag ----
    output_keys_final: dict = {}
    for output, rows in expected_output.items():
        proposed = list(output_keys_proposed.get(output, []))
        result = _verify_output_keys(output, proposed, rows)
        output_keys_final[output] = result
        if result == [] and bool(proposed):  # re-derive the (log-only) low_confidence flag from Task 8
            low_confidence.append(
                f"output_keys for {output!r}: proposed composite key {proposed} not unique across expected rows; "
                "using bag/multiset")

    # ---- 5. Co-key name sanitization: ONE map applied across every keyed artifact ----
    name_map = _safe_output_names(list(dict.fromkeys([*source_names, *output_names])))

    def _remap(mapping):
        return {name_map[key]: value for key, value in mapping.items()}

    sources_schema_out = _remap(sources_schema)
    sample_input_out = _remap(sample_input)
    expected_output_out = _remap(expected_output)
    provenance_out = _remap(provenance)
    output_keys_out = _remap(output_keys_final)
    graded_out = [name_map[name] for name in graded]

    # ---- 6. Tier + rung-aware facts + coverage cross-check ----
    tier = _compute_tier(provenance_out, graded_out, distinct_ok)
    derived_facts = _rung_aware_facts(sample_input_out, provenance_out)
    emitted = _build_emitted(source_names, output_names, sources_schema, output_keys_proposed,
                             expected_output, rules, extra_sections, name_map)
    unresolved_out = [name_map.get(name, name) for name in unresolved_names]
    unaccounted, unresolved = _cross_check_coverage(inventory, coverage_map, emitted, unresolved_out)

    # ---- 7. Extraction status: any hard blocker routes to human ----
    status = "needs_human" if (unaccounted or unresolved or missing_prov_graded) else "ok"
    if missing_prov_graded:
        logger.warning("[normalize_validate] graded output(s) lack provenance -> needs_human: %s", missing_prov_graded)
    extraction = {"status": status, "unaccounted": unaccounted, "unresolved": unresolved, "low_confidence": low_confidence}

    extract_dict = {
        "sources_schema": sources_schema_out,
        "rules": rules,
        "sample_input": sample_input_out,
        "expected_output": expected_output_out,
        "output_keys": output_keys_out,
        "derived_facts": derived_facts,
        "conformance": _conformance_ok(),
        "notes": notes,
        "extra_sections": extra_sections,
        "tier": tier,
        "provenance": provenance_out,
        "coverage_map": coverage_map,
        "extraction": extraction,
        "normalization": {"model_id": model_id},
    }
    return extract_dict, status


# ------------------------------------------------------------------
# Shape validation: an enumerated, value-blind predicate over the raw
# normalizer_proposal.json. Malformed-proposal failures route to the repair
# loop (shape_error); the coverage hard-blocker (unaccounted handles / a graded
# output missing provenance) is assemble's extraction.status job (needs_human).
# ------------------------------------------------------------------
def _shape_declared_refs(proposal) -> set:
    """Build the value-blind set of coverage-ref targets a proposal DECLARES (source/output names, schema fields, rule ids, section headings)."""
    sources_schema = proposal.get("sources_schema") or {}
    located = proposal.get("located") or {}
    source_names = list(sources_schema.keys())
    output_names = list((located.get("expected_output") or {}).keys())
    name_map = _safe_output_names(list(dict.fromkeys([*source_names, *output_names])))
    safe_schema = {s: [c for c in (cols or []) if isinstance(c, dict)] for s, cols in sources_schema.items()}
    return _build_emitted(source_names, output_names, safe_schema, proposal.get("output_keys") or {},
                          proposal.get("expected_output") or {}, proposal.get("rules") or [],
                          proposal.get("extra_sections") or {}, name_map)


def _shape_errors(proposal, inventory) -> list:
    """Return an enumerated list of value-blind shape failures (pointer/why/fix); an empty list means the proposal is well-formed."""
    errors: list = []

    # (1) every rule declares a kind in the allowed set.
    for i, rule in enumerate(proposal.get("rules") or []):
        kind = rule.get("kind") if isinstance(rule, dict) else None
        if kind not in _VALID_RULE_KINDS:
            errors.append({
                "pointer": f"rules[{i}].kind",
                "why": f"rule kind {kind!r} is not one of join|schema_validate|filter|aggregate|sort|derive",
                "fix": "set kind to one of the six allowed rule kinds",
            })

    # (2) every declared source carries at least one column.
    sources_schema = proposal.get("sources_schema") or {}
    for name, cols in sources_schema.items():
        if not isinstance(cols, list) or len(cols) < 1:
            errors.append({
                "pointer": f"sources_schema.{name}",
                "why": "source schema declares no columns",
                "fix": "declare at least one {name,type,nullable,key} column for this source",
            })

    # (3) every located name is consistent (sample -> a declared source; expected -> a declared output).
    located = proposal.get("located") or {}
    located_sample = located.get("sample_input") or {}
    located_expected = located.get("expected_output") or {}
    # A valid output appears under output_keys OR in located.expected_output; a missing
    # output_keys entry means bag/[] (keyless), which assemble treats as a valid output.
    valid_outputs = set((proposal.get("output_keys") or {}).keys()) | set(located_expected.keys())
    for name in located_sample:
        if name not in sources_schema:
            errors.append({
                "pointer": f"located.sample_input.{name}",
                "why": "located sample_input name has no matching sources_schema source",
                "fix": "add a sources_schema entry for this name or remove the located slot",
            })
    for name in located_expected:
        if name not in valid_outputs:
            errors.append({
                "pointer": f"located.expected_output.{name}",
                "why": "located expected_output name is not a declared output",
                "fix": "declare this output under output_keys or in located.expected_output, or remove the slot",
            })

    # (4) every located candidate handle id resolves against the inventory.
    for side, mapping in (("sample_input", located_sample), ("expected_output", located_expected)):
        for name, candidates in mapping.items():
            for j, cand in enumerate(candidates or []):
                if _resolve(cand, inventory) is None:
                    errors.append({
                        "pointer": f"located.{side}.{name}[{j}]",
                        "why": f"candidate handle {cand!r} is not a member of the exploder inventory",
                        "fix": "reference an inventory handle id (para:N | table:N | image:N | embed:<name> | sibling:<name>)",
                    })

    # (5) an extracted_to coverage entry MUST carry non-empty refs that resolve to declared targets.
    try:
        declared_refs = _shape_declared_refs(proposal)
    except Exception:  # malformed schema/rows already flagged above; skip ref-resolution this pass
        declared_refs = None
    for k, entry in enumerate(proposal.get("coverage_map") or []):
        if not isinstance(entry, dict) or entry.get("disposition") != "extracted_to":
            continue
        refs = entry.get("refs") or []
        if not refs:
            errors.append({
                "pointer": f"coverage_map[{k}].refs",
                "why": "disposition 'extracted_to' requires a non-empty refs list",
                "fix": "list the schema field(s)/rule id(s)/source/output/section this handle fed, or change the disposition",
            })
        elif declared_refs is not None:
            for ref in refs:
                if ref not in declared_refs:
                    errors.append({
                        "pointer": f"coverage_map[{k}].refs",
                        "why": f"ref {ref!r} does not resolve to any declared source/output/schema-field/rule/section",
                        "fix": "reference a declared <source>.<column>, rule id, source/output name, or extra_sections heading",
                    })
    return errors


# ------------------------------------------------------------------
# validate + CLI: shape-validate, then assemble; map status -> artifact + exit.
# ------------------------------------------------------------------
def validate(inventory_path, proposal_path, out_path, feedback_path, model_id="") -> str:
    """Shape-validate then assemble; on a shape failure write normalizer_feedback.json (shape_error), else write extract_doc.json (ok|needs_human)."""
    with open(inventory_path, "r", encoding="utf-8") as fh:
        inventory = json.load(fh)  # deterministic tool output: fail-loud on a malformed inventory
    try:
        with open(proposal_path, "r", encoding="utf-8") as fh:
            proposal = json.load(fh)
        errors = _shape_errors(proposal, inventory)
    except (json.JSONDecodeError, AttributeError, TypeError, ValueError) as exc:
        errors = [{
            "pointer": "$",
            "why": f"proposal is not valid JSON or has the wrong top-level shape: {exc}",
            "fix": "emit a well-formed normalizer_proposal.json (object with rules/sources_schema/located/coverage_map)",
        }]
    if errors:
        fb = Path(feedback_path)
        fb.parent.mkdir(parents=True, exist_ok=True)
        fb.write_text(json.dumps({"errors": errors}, indent=2), encoding="utf-8")
        logger.warning("[normalize_validate] shape_error: %d issue(s) -> %s", len(errors), feedback_path)
        return "shape_error"

    extract_dict, status = assemble(proposal, inventory, model_id)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(extract_dict, indent=2), encoding="utf-8")
    logger.info("[normalize_validate] status=%s tier=%s -> %s", status, extract_dict.get("tier"), out_path)
    return status


def main(argv=None) -> int:
    """CLI: shape-validate + assemble a normalizer proposal; exit 0 (ok) / 3 (shape_error) / 4 (needs_human)."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Validate a normalizer proposal into extract_doc.json or normalizer_feedback.json.")
    parser.add_argument("--inventory", required=True, help="path to exploder_inventory.json")
    parser.add_argument("--proposal", required=True, help="path to normalizer_proposal.json")
    parser.add_argument("--out", required=True, help="write extract_doc.json here (ok|needs_human)")
    parser.add_argument("--feedback", required=True, help="write normalizer_feedback.json here (shape_error)")
    parser.add_argument("--model-id", default="", help="advisory model id recorded under normalization.model_id")
    args = parser.parse_args(argv)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.feedback).parent.mkdir(parents=True, exist_ok=True)

    status = validate(args.inventory, args.proposal, args.out, args.feedback, args.model_id)
    sys.stdout.write(f"[normalize_validate] status={status}\n")
    return _STATUS_EXIT.get(status, 4)


if __name__ == "__main__":
    import sys

    sys.exit(main())
