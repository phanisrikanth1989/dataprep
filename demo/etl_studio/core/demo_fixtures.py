"""Scripted-double fixtures for the trade_positions demo (ticket 17).

Ticket 16's fixtures scripted the ORCHESTRATOR placeholders and stub-stage
choreography; this module grows them into the REAL specialists' replies: the
opening line (ticket 06's live-line source) followed by the fenced JSON
artifact the real stages parse, validate (the vendored validator and
validate_config judge this content for real) and land on the bus.

Content posture: everything here is what a scripted model SAYS; every
machine consequence -- shape errors, needs_human, gap rounds, the code-gate
cells, validate results -- is computed from it by the real chassis. The
``brd.normalize.shape`` / ``brd.normalize.gap`` variants carry genuine
defects the real validator catches (rig-selected labels; see
real_stages.RealDocNormalizer).

Consumption note: a label's calls are consumed in order per core process and
the last call repeats -- the smoke phases each drive one process, so the
sequences below script one full walk (retries, tool rounds, re-runs ride the
same label as successive calls).
"""

from __future__ import annotations

import copy
import json
from typing import Any, Dict, List

JOB = "trade_positions"
BRD = "trade_position_demo.docx"

# ---------------------------------------------------------------------------
# The requirement content (the demo BRD's real pipeline)
# ---------------------------------------------------------------------------

SCHEMA: Dict[str, List[Dict[str, Any]]] = {
    "trades": [
        {"name": "trade_id", "type": "string", "nullable": False, "key": True},
        {"name": "account_id", "type": "string", "nullable": False, "key": False},
        {"name": "symbol", "type": "string", "nullable": False, "key": False},
        {"name": "quantity", "type": "integer", "nullable": False, "key": False},
        {"name": "price", "type": "decimal", "nullable": False, "key": False},
        {"name": "status", "type": "string", "nullable": False, "key": False},
        {"name": "trade_date", "type": "date", "nullable": False, "key": False},
    ],
    "accounts": [
        {"name": "account_id", "type": "string", "nullable": False, "key": True},
        {"name": "account_name", "type": "string", "nullable": False, "key": False},
        {"name": "region", "type": "string", "nullable": False, "key": False},
    ],
    "prices": [
        {"name": "symbol", "type": "string", "nullable": False, "key": True},
        {"name": "closing_price", "type": "decimal", "nullable": False, "key": False},
    ],
}

GAPS: List[Dict[str, Any]] = [
    {
        "id": "G1",
        "severity": "blocking",
        "rule": "R2",
        "prompt": "Trades with no matching account — drop them, or keep them with blank account fields?",
        "options": [
            {"id": "keep_blanks", "label": "Keep them with blanks", "kind": "choice",
             "recommended": True, "why": "the requirement reads as a full extract"},
            {"id": "drop", "label": "Drop unmatched trades", "kind": "choice"},
        ],
        "free_prompt": "Something else…",
    },
    {
        "id": "G2",
        "severity": "advisory",
        "rule": "R6",
        "prompt": "Equal market values: no tie-breaker is stated. Default to trade_id ascending within ties?",
        "options": [
            {"id": "trade_id_asc", "label": "trade_id ascending", "kind": "choice",
             "recommended": True, "why": "stable and auditable"},
            {"id": "waive", "label": "Waive — proceed with the default", "kind": "waive"},
        ],
        "free_prompt": "A different tie-breaker…",
    },
]

GAP_G3: Dict[str, Any] = {
    "id": "G3",
    "severity": "advisory",
    "rule": "R5",
    "prompt": ("R5 validates trade_date as yyyy-MM-dd, but the failure disposition "
               "wasn't stated. Drop non-conforming rows, or pass them through?"),
    "options": [
        {"id": "validate_drop", "label": "Drop non-conforming rows", "kind": "choice",
         "recommended": True, "why": "a malformed date would corrupt the sorted feed"},
        {"id": "passthrough", "label": "Pass dates through untouched", "kind": "waive"},
    ],
    "free_prompt": "A different handling…",
}


def _rules(no_match: Any, r5_detail: str) -> List[Dict[str, Any]]:
    return [
        {"id": "R1", "kind": "filter", "label": "Keep settled trades",
         "detail": "status = SETTLED",
         "column": "status", "operator": "==", "value": "SETTLED"},
        {"id": "R2", "kind": "join", "label": "Add account details",
         "detail": "left join · account_id",
         "source": "trades", "lookup": "accounts",
         "keys": {"left": ["account_id"], "right": ["account_id"]},
         "columns_added": ["account_name", "region"],
         "cardinality": "1:1", "no_match": no_match},
        {"id": "R3", "kind": "join", "label": "Add closing price",
         "detail": "left join · symbol",
         "source": "trades", "lookup": "prices",
         "keys": {"left": ["symbol"], "right": ["symbol"]},
         "columns_added": ["closing_price"],
         "cardinality": "1:1", "no_match": "keep"},
        {"id": "R4", "kind": "derive", "label": "Compute market value",
         "detail": "quantity × price",
         "output_column": "market_value",
         "how": "quantity multiplied by price, numeric"},
        {"id": "R5", "kind": "schema_validate", "label": "Validate trade_date",
         "detail": r5_detail,
         "columns": [{"name": "trade_date", "type": "date", "format": "yyyy-MM-dd"}]},
        {"id": "R6", "kind": "sort", "label": "Sort by market value",
         "detail": "high to low",
         "criteria": [{"column": "market_value", "order": "desc", "sort_type": "num"}]},
    ]


def _spec_reply(rules: List[Dict[str, Any]], gaps: List[Dict[str, Any]],
                what_changed: Any) -> Dict[str, Any]:
    return {
        "rules": rules,
        "schema": SCHEMA,
        "outputs": [{"name": "trade_positions"}],
        "gaps": gaps,
        "what_changed": what_changed,
        "notes": None,
    }


SPEC_READ = _spec_reply(_rules(None, "yyyy-MM-dd"), GAPS, None)
SPEC_TYPED_FOLD_1 = _spec_reply(
    _rules("keep", "yyyy-MM-dd"), [GAP_G3],
    "Folded your answers in — unmatched trades keep blanks, ties break on "
    "trade_id. R5's failure disposition is the one open point.")
SPEC_TYPED_FOLD_2 = _spec_reply(
    _rules("keep", "yyyy-MM-dd · drop failures"), [],
    "R5 drops non-conforming rows — the spec is complete.")
SPEC_BRD_FOLD = _spec_reply(
    _rules("keep", "yyyy-MM-dd"), [],
    "Folded your answers in — unmatched trades keep blanks, ties break on trade_id.")
SPEC_REVISED = _spec_reply(
    _rules("keep", "yyyy-MM-dd · drop failures"), [],
    "Folded your revision note into the spec — every signed answer carries over.")
# A directed revision must genuinely CHANGE the spec (the conductor's
# signature rule skips the re-sign-off otherwise): the note lands on it.
SPEC_REVISED["notes"] = ("Revision folded from your latest note; every signed "
                         "answer carries over unchanged.")


# ---------------------------------------------------------------------------
# The normalizer proposals (judged by the real vendored validator)
# ---------------------------------------------------------------------------

_PROPOSAL_RULES = [
    {"id": "R1", "kind": "join",
     "description": "Join each trade to Accounts on account_id (unique key; left join; keep unmatched) to add account_name and region."},
    {"id": "R2", "kind": "join",
     "description": "Join each trade to Prices on symbol (unique key; left join; keep unmatched) to add closing_price."},
    {"id": "R3", "kind": "derive",
     "description": "Derive market_value as quantity multiplied by price (numeric)."},
    {"id": "R4", "kind": "filter",
     "description": "Keep only trades whose status is SETTLED."},
    {"id": "R5", "kind": "schema_validate",
     "description": "Validate trade_date is a yyyy-MM-dd date; a non-conforming trade is dropped."},
    {"id": "R6", "kind": "sort",
     "description": "Sort the output by the derived numeric market_value, descending."},
]

PROPOSAL: Dict[str, Any] = {
    "sources_schema": SCHEMA,
    "rules": _PROPOSAL_RULES,
    "notes": ("A trade whose account_id has no matching account is KEPT with "
              "account_name and region blank; likewise a missing symbol price. "
              "Both lookups are left joins; never drop a trade for a missing "
              "lookup value."),
    "extra_sections": {
        "Overview": {"prose": "Builds an enriched trade position feed for the "
                              "downstream reporting team.", "tables": []},
    },
    "output_keys": {"trade_positions": ["trade_id"]},
    "located": {
        "sample_input": {
            "trades": ["sibling:trades.csv"],
            "accounts": ["sibling:accounts.csv"],
            "prices": ["sibling:prices.csv"],
        },
        "expected_output": {"trade_positions": ["table:1"]},
    },
    "coverage_map": [
        {"handle": "para:0", "disposition": "extracted_to", "refs": ["Overview"]},
        {"handle": "table:0", "disposition": "extracted_to",
         "refs": ["R1", "R2", "R3", "R4", "R5", "R6"]},
        {"handle": "para:1", "disposition": "extracted_to",
         "refs": ["R1", "R2", "R3", "R4", "R5", "R6"]},
        {"handle": "table:1", "disposition": "extracted_to", "refs": ["trade_positions"]},
        {"handle": "sibling:trades.csv", "disposition": "extracted_to", "refs": ["trades"]},
        {"handle": "sibling:accounts.csv", "disposition": "extracted_to", "refs": ["accounts"]},
        {"handle": "sibling:prices.csv", "disposition": "extracted_to", "refs": ["prices"]},
    ],
    "low_confidence": [
        "output name trade_positions is synthesized — the document names no output dataset",
    ],
}

# A genuine shape defect: rule kind outside the enum (the validator's
# rules[].kind check catches it and its errors[] feed the repair pass).
PROPOSAL_SHAPE_DEFECT = copy.deepcopy(PROPOSAL)
PROPOSAL_SHAPE_DEFECT["rules"][4]["kind"] = "validate"

# A genuine coverage hole: para:0 has no disposition -> extraction fails
# closed (unaccounted) and routes to the question channel.
PROPOSAL_UNACCOUNTED = copy.deepcopy(PROPOSAL)
PROPOSAL_UNACCOUNTED["coverage_map"] = [
    e for e in PROPOSAL_UNACCOUNTED["coverage_map"] if e["handle"] != "para:0"]


# ---------------------------------------------------------------------------
# The flow plan
# ---------------------------------------------------------------------------

FLOW_EDGES: List[List[str]] = [
    ["in_trades", "filter_settled"],
    ["filter_settled", "join_accounts"],
    ["in_accounts", "join_accounts"],
    ["join_accounts", "join_prices"],
    ["in_prices", "join_prices"],
    ["join_prices", "validate_date"],
    ["validate_date", "derive_mv"],
    ["derive_mv", "sort_mv"],
    ["sort_mv", "out_positions"],
]

FLOW_PLAN: Dict[str, Any] = {
    "pattern": ("filter early, two keyed left lookups (accounts, prices), one "
                "vectorized derive, a date validation, numeric sort last, one "
                "delimited output"),
    "components": [
        {"id": "in_trades", "type": "FileInputDelimited", "label": "Read trades",
         "purpose": "Read the daily trades extract (7 columns)."},
        {"id": "in_accounts", "type": "FileInputDelimited", "label": "Read accounts",
         "purpose": "Read the accounts reference file (3 columns)."},
        {"id": "in_prices", "type": "FileInputDelimited", "label": "Read prices",
         "purpose": "Read the closing prices reference file (2 columns)."},
        {"id": "filter_settled", "type": "FilterRows", "label": "Keep settled",
         "purpose": "Keep only SETTLED trades before the lookups (input reduction)."},
        {"id": "join_accounts", "type": "tJoin", "label": "Match accounts",
         "purpose": "Left join on account_id; unmatched trades keep blanks per the signed answer."},
        {"id": "join_prices", "type": "tJoin", "label": "Match prices",
         "purpose": "Left join on symbol adding closing_price."},
        {"id": "validate_date", "type": "SchemaComplianceCheck", "label": "Validate date",
         "purpose": "Validate trade_date as yyyy-MM-dd; non-conforming rows drop to reject."},
        {"id": "derive_mv", "type": "tPythonDataFrame", "label": "Compute value",
         "purpose": ("One vectorized derive: market_value = quantity x price. "
                     "Unsandboxed code cell — human-reviewed at the gate; the "
                     "configurator must pin execution_mode batch.")},
        {"id": "sort_mv", "type": "SortRow", "label": "Sort by value",
         "purpose": ("Numeric descending sort as the LAST step so the output "
                     "order is the contract; configurator must pin "
                     "execution_mode batch.")},
        {"id": "out_positions", "type": "FileOutputDelimited", "label": "Write positions",
         "purpose": "Write the enriched, sorted trade_positions feed."},
    ],
    "edges": FLOW_EDGES,
}


# ---------------------------------------------------------------------------
# The configured draft (validated for real by the vendored validate_config)
# ---------------------------------------------------------------------------

CODE_CELL_CODE = "df['market_value'] = df['quantity'].astype(float) * df['price'].astype(float)"
CODE_CELL_REVISED = ("df['market_value'] = (df['quantity'].astype('float64')\n"
                     "                      * df['price'].astype('float64')).round(2)")

_TRADES_COLS = [{"name": c["name"], "type": {"integer": "int", "decimal": "float"}.get(
    c["type"], "str")} for c in SCHEMA["trades"]]
_ENRICHED_COLS = _TRADES_COLS + [
    {"name": "account_name", "type": "str"}, {"name": "region", "type": "str"}]
_PRICED_COLS = _ENRICHED_COLS + [{"name": "closing_price", "type": "float"}]
FINAL_COLS = [{"name": n, "type": t} for n, t in (
    ("trade_id", "str"), ("account_name", "str"), ("region", "str"),
    ("symbol", "str"), ("market_value", "float"), ("closing_price", "float"))]


def _reader(name: str, cols: List[Dict[str, str]]) -> Dict[str, Any]:
    return {
        "id": f"in_{name}", "type": "FileInputDelimited",
        "config": {"filepath": f"{name}.csv", "fieldseparator": ",",
                   "header_rows": 1, "csv_option": True, "text_enclosure": "\"",
                   "die_on_error": False},
        "schema": {"input": [], "output": cols},
    }


def build_config_draft(cell_code: str = CODE_CELL_CODE,
                       sort_type: Any = None) -> Dict[str, Any]:
    """The configurator's draft. ``sort_type`` None reproduces the
    sortrow-alpha-default landmine (validates clean, mis-sorts numerically --
    the demo's run-1 failure); the repair sets it to "num"."""
    sort_criterion: Dict[str, Any] = {"column": "market_value", "order": "desc"}
    if sort_type:
        sort_criterion["sort_type"] = sort_type
    components = [
        _reader("trades", _TRADES_COLS),
        _reader("accounts", [{"name": "account_id", "type": "str"},
                             {"name": "account_name", "type": "str"},
                             {"name": "region", "type": "str"}]),
        _reader("prices", [{"name": "symbol", "type": "str"},
                           {"name": "closing_price", "type": "float"}]),
        {"id": "filter_settled", "type": "FilterRows",
         "config": {"conditions": [{"column": "status", "operator": "==",
                                    "value": "SETTLED"}],
                    "logical_op": "&&"},
         "schema": {"input": [], "output": list(_TRADES_COLS)}},
        {"id": "join_accounts", "type": "tJoin",
         "config": {"use_inner_join": False,
                    "join_key": [{"input_column": "account_id",
                                  "lookup_column": "account_id"}],
                    "use_lookup_cols": True,
                    "lookup_cols": [
                        {"output_column": "account_name", "lookup_column": "account_name"},
                        {"output_column": "region", "lookup_column": "region"}],
                    "die_on_error": False},
         "schema": {"input": [], "output": list(_ENRICHED_COLS)}},
        {"id": "join_prices", "type": "tJoin",
         "config": {"use_inner_join": False,
                    "join_key": [{"input_column": "symbol",
                                  "lookup_column": "symbol"}],
                    "use_lookup_cols": True,
                    "lookup_cols": [
                        {"output_column": "closing_price", "lookup_column": "closing_price"}],
                    "die_on_error": False},
         "schema": {"input": [], "output": list(_PRICED_COLS)}},
        {"id": "validate_date", "type": "SchemaComplianceCheck",
         "config": {"schema": [
             {"name": "trade_date", "type": "datetime", "date_pattern": "yyyy-MM-dd"}],
             "check_all": False, "check_another": True,
             "checkcols": [{"column": "trade_date", "selected_type": "datetime",
                            "date_pattern": "yyyy-MM-dd"}],
             "strict_date_check": True},
         "schema": {"input": [], "output": list(_PRICED_COLS)}},
        {"id": "derive_mv", "type": "tPythonDataFrame",
         "config": {"python_code": cell_code, "execution_mode": "batch",
                    "output_columns": [c["name"] for c in FINAL_COLS]},
         "schema": {"input": [], "output": list(FINAL_COLS)}},
        {"id": "sort_mv", "type": "SortRow",
         "config": {"criteria": [sort_criterion], "execution_mode": "batch"},
         "schema": {"input": [], "output": list(FINAL_COLS)}},
        {"id": "out_positions", "type": "FileOutputDelimited",
         "config": {"filepath": "trade_positions.csv", "fieldseparator": ",",
                    "include_header": True, "csv_option": True,
                    "text_enclosure": "\"", "file_exist_exception": False},
         "schema": {"input": list(FINAL_COLS), "output": []}},
    ]
    return {"components": components}


CONFIG_DRAFT = build_config_draft()
CONFIG_DRAFT_REVISED = build_config_draft(cell_code=CODE_CELL_REVISED)
CONFIG_DRAFT_REPAIRED = build_config_draft(sort_type="num")


def build_job_reply() -> Dict[str, Any]:
    """The assembler's scripted envelope, built from the draft + edges so the
    wiring stays consistent with the plan (configs ride along but the real
    stage enforces config-from-draft regardless)."""
    draft = {c["id"]: copy.deepcopy(c) for c in CONFIG_DRAFT["components"]}
    flow_name = {(a, b): f"{a}_to_{b}" for a, b in (tuple(e) for e in FLOW_EDGES)}
    rename = {"out_positions": "trade_positions"}  # the output-name contract
    components: List[Dict[str, Any]] = []
    for cid, comp in draft.items():
        inputs = [flow_name[(a, b)] for a, b in (tuple(e) for e in FLOW_EDGES) if b == cid]
        outputs = [flow_name[(a, b)] for a, b in (tuple(e) for e in FLOW_EDGES) if a == cid]
        # tJoin driver-first order: the plan's edge order already lists the
        # driver edge before the lookup edge, so the comprehension holds it.
        producer_cols: List[Dict[str, str]] = []
        for a, b in (tuple(e) for e in FLOW_EDGES):
            if b == cid:
                producer_cols = draft[a]["schema"]["output"]
                break
        wired = dict(comp)
        wired["id"] = rename.get(cid, cid)
        wired["subjob_id"] = "sj1"
        wired["schema"] = {"input": list(producer_cols), "output": comp["schema"]["output"]}
        wired["inputs"] = inputs
        wired["outputs"] = outputs
        components.append(wired)
    flows = [{"name": flow_name[(a, b)], "type": "flow", "from": a,
              "to": rename.get(b, b)} for a, b in (tuple(e) for e in FLOW_EDGES)]
    return {"components": components, "flows": flows, "triggers": []}


JOB_REPLY = build_job_reply()


# ---------------------------------------------------------------------------
# Reply rendering: opening line + fenced JSON (the OUTPUT_CONTRACT shape)
# ---------------------------------------------------------------------------


def _reply(opening: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Two stream parts: the opening line word-streamed (the live line reads
    it as it lands), then the fenced artifact as chunked blob text (word
    pacing on a JSON body would crawl at demo cadence)."""
    return [
        {"text": opening + "\n"},
        {"blob": "```json\n" + json.dumps(payload, indent=2, ensure_ascii=True) + "\n```"},
    ]


# ---------------------------------------------------------------------------
# Orchestrator placeholder voice (ticket 16's, unchanged until ticket 18)
# ---------------------------------------------------------------------------

ORCH = {
    "questions": "I’ve read the requirement — three sources, six rules. Answers below and the spec is complete. They’re pinned to the rules they block, out on the canvas.",
    "signed": "Spec signed off. Your goldens are in place — this build grades against them.",
    "flow": "The flow is designed: a filter, two lookups, one computed column, a date check, a sort. Configuring each step now.",
    "gate": "One step writes code — computing market_value. Nothing runs until you approve the exact cell. The cell is on the canvas, spotlit.",
    "verdict": "Verified. The output matches your golden — all 4 rows, order included. Run 1 mis-sorted; the fix was one setting.",
    "reverdict": "Re-verified after your revision — the output still matches your golden, all 4 rows.",
}

THINK_INTERPRETER = (
    "The mapping table carries every target field; the rules read clean. "
    "Nothing settles unmatched trades — raising it rather than assuming. "
    "Sort is given (value, high to low) but no tie-breaker — advisory, default trade_id."
)
THINK_NORMALIZER = (
    "Two tables and three sibling CSVs — the mapping table is intent, the second "
    "table is the expected output, the CSVs are the exact sources. Six rule "
    "paragraphs normalize to one requirement block each; locating, never retyping."
)
THINK_FLOW = (
    "Filter first — it shrinks both lookups. "
    "Two joins stay separate: different keys, and rejects must be traceable per lookup. "
    "Sort placed last so the output order is the contract."
)
THINK_CONFIG_1 = (
    "join_accounts carries account_name and region; left join per the G1 answer — "
    "unmatched trades keep blanks. Validating each config as I go."
)
THINK_CONFIG_2 = (
    "The validator flagged the missing join_key — fixed and re-validated clean. "
    "market_value lands as the one generated cell — flagging it for the code gate."
)


def build_scripts() -> Dict[str, List[List[Dict[str, Any]]]]:
    """Fixture scripts handed to the DoubleAdapter, keyed by call label."""
    u = lambda n: {"usage": int(n * 1e9)}  # noqa: E731 -- AIU to nano-AIU
    draft_cfg = {c["id"]: c["config"] for c in CONFIG_DRAFT["components"]}
    join_missing_key = {k: v for k, v in draft_cfg["join_accounts"].items()
                        if k != "join_key"}
    return {
        # ---- orchestrator placeholders (ticket 18 replaces the call sites) --
        "orch.opening.brd": [[
            {"text": "Reading the requirements document — exploding it into stable handles first. I’ll interpret what I find into a spec; anything unclear becomes a question, never an assumption."},
            u(2.1),
        ]],
        "orch.opening.typed": [[
            {"text": "Reading your request. I’ll interpret it into a spec; anything unclear becomes a question, never an assumption."},
            u(1.7),
        ]],
        "orch.questions": [[{"text": ORCH["questions"]}, u(1.8)]],
        "orch.signed": [[{"text": ORCH["signed"]}, u(1.2)]],
        "orch.flow": [[{"text": ORCH["flow"]}, u(1.6)]],
        "orch.gate": [[{"text": ORCH["gate"]}, u(1.9)]],
        "orch.verdict": [[{"text": ORCH["verdict"]}, u(2.4)]],
        "orch.reverdict": [[{"text": ORCH["reverdict"]}, u(1.8)]],
        "orch.hold": [[
            {"text": "You’d like me to pause. Confirm and I’ll hold at the next stage boundary — the stage in flight finishes and its artifact lands whole, then the build waits for you."},
            u(1.4),
        ]],
        "orch.stop": [[
            {"text": "You’d like to stop this build. Confirm and I’ll end it plainly at the next boundary — nothing else executes, everything so far stays on the canvas."},
            u(1.3),
        ]],
        "orch.resume": [[{"text": "Resuming — picking the build up exactly where the hold left it."}, u(0.9)]],
        "orch.steer": [[
            {"text": "That’s spec-shaped feedback, so it routes to the Interpreter: the spec revises, you re-sign it, and the stages after it re-run."},
            u(1.2),
        ]],
        "orch.ask": [[{"echo_prompt": True}, u(1.5)]],

        # ---- doc-normalizer (the real validator judges every proposal) -----
        "brd.normalize.shape": [[
            {"think": THINK_NORMALIZER},
            *_reply("Proposing the extraction map across the 7 handles.",
                            PROPOSAL_SHAPE_DEFECT),
            u(6.2),
        ]],
        "brd.normalize.gap": [[
            {"think": "Applying the validator's pointers — every errors[] entry, then regenerating."},
            *_reply("Re-proposing with the rule kinds corrected.",
                            PROPOSAL_UNACCOUNTED),
            u(5.8),
        ]],
        "brd.normalize": [[
            {"think": THINK_NORMALIZER},
            *_reply("Locating sources and rules across the 7 handles — proposing the extraction map.",
                            PROPOSAL),
            u(6.4),
        ]],

        # ---- interpreter ---------------------------------------------------
        "interp.read": [[
            {"think": THINK_INTERPRETER},
            *_reply("Reading the mapping and rules into a typed spec — raising what's genuinely open.",
                            SPEC_READ),
            u(7.1),
        ]],
        "interp.refind": [
            [
                {"think": "G1 answered keep-blanks, G2 ties on trade_id, the data question is settled — folding in and re-checking the rule level."},
                *_reply("Folding your answers in and re-checking the spec for downstream gaps.",
                                SPEC_TYPED_FOLD_1),
                u(4.9),
            ],
            [
                *_reply("R5's disposition is settled — the spec is complete.",
                                SPEC_TYPED_FOLD_2),
                u(3.2),
            ],
        ],
        "brd.refind": [[
            {"think": "Both answers fold straight into R2 and R6 — nothing downstream opens up."},
            *_reply("Folding your answers in — the spec is complete.",
                            SPEC_BRD_FOLD),
            u(4.1),
        ]],
        "interp.revise": [[
            {"think": "Reading your note — folding it into the spec as a revision. Every signed answer carries over; only what you flagged moves."},
            *_reply("Folding your revision note into the signed spec.",
                            SPEC_REVISED),
            u(4.6),
        ]],

        # ---- flow designer (call 1 is a genuine malformed-output beat) -----
        "flow.design": [
            [
                {"think": THINK_FLOW},
                {"text": "Choosing the shape — filter early, two keyed lookups, derive, validate, sort last. {\"pattern\": \"filter early"},
                u(2.2),
            ],
            [
                *_reply("Re-emitting the flow plan as one artifact.",
                                FLOW_PLAN),
                u(6.8),
            ],
        ],
        "flow.repair": [[
            *_reply("Applying the diagnosed fix to the plan.", FLOW_PLAN),
            u(3.0),
        ]],

        # ---- configurator (real validate_config judges the tool args) ------
        "config.main": [
            [
                {"think": "Configuring each step against the component schemas…"},
                {"error": {"kind": "RateLimited", "message": "provider returned 429 on the last call", "retry_after": 1.8}},
            ],
            [
                {"think": THINK_CONFIG_1},
                {"tool": {"call_id": "v1", "name": "validate_config",
                          "args": {"type": "FileInputDelimited",
                                   "config": draft_cfg["in_trades"], "id": "in_trades"}}},
                {"pause": 0.4},
                {"tool": {"call_id": "v2", "name": "validate_config",
                          "args": {"type": "tJoin", "config": join_missing_key,
                                   "id": "join_accounts"}}},
                u(12.4),
            ],
            [
                {"think": THINK_CONFIG_2},
                {"tool": {"call_id": "v3", "name": "validate_config",
                          "args": {"type": "tJoin",
                                   "config": draft_cfg["join_accounts"],
                                   "id": "join_accounts"}}},
                {"tool": {"call_id": "v4", "name": "validate_config",
                          "args": {"type": "SortRow", "config": draft_cfg["sort_mv"],
                                   "id": "sort_mv"}}},
                u(9.7),
            ],
            [
                *_reply("Every step validates clean — emitting the configured draft.",
                                CONFIG_DRAFT),
                u(8.9),
            ],
        ],
        "config.revise": [[
            {"think": "Rewriting the market_value cell per your note — explicit float64 cast and a pinned 2-decimal round, no drift."},
            *_reply("Rewriting the one flagged cell — everything else byte-identical.",
                            CONFIG_DRAFT_REVISED),
            u(5.4),
        ]],
        "config.repair": [[
            {"think": "The diagnosis is one setting: sort_mv compares as text. Pinning sort_type = num; nothing else moves."},
            *_reply("Applying the diagnosed fix — sort_type = num on sort_mv.",
                            CONFIG_DRAFT_REPAIRED),
            u(4.2),
        ]],

        # ---- assembler -----------------------------------------------------
        "assemble.run": [[
            {"think": "Driver-first wiring for both joins; the terminal output id takes the output name per the contract."},
            *_reply("Wiring the envelope — flows, schemas and the output-name contract.",
                            JOB_REPLY),
            u(7.6),
        ]],
        "assemble.repair": [[
            *_reply("Re-wiring with the repaired draft.", JOB_REPLY),
            u(3.1),
        ]],

        # ---- stub diagnostician (ticket 19 replaces) -----------------------
        "diag.run": [[
            {"think": "run 1 output: rows 2 and 3 swapped against the golden. sort_mv compares as text — '15025.00' sorts above '6901.00' only numerically. Owner: Configurator; fix is one setting, sort_type = num."},
            u(5.3),
        ]],
    }
