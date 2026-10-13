"""The end-of-day payments job as a v1 job config, in two spellings.

``python``
    The map is a PyMap and its expressions are Python. This one file runs
    on v1 and on v2.

``java``
    The map is a tMap and its expressions are Java, the way the converter
    writes a Talend job. It runs on v1, through the Java bridge.

Everything else is the same in both, component for component, so the two
spellings can only differ in what the map's expressions mean.

The job has three stages, each started by a trigger:

1. settings: a small file of settings is loaded into the context;
2. validate and enrich: the payments are checked, de-duplicated, joined to
   their branch, prepared and enriched in two maps, sorted and totalled;
3. reject report: the rejected payments are counted per currency.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

VARIANTS = ("python", "java")
OUTPUTS = (
    "enriched.csv", "high_value.csv", "cross_border.csv", "summary.csv", "format_rejects.csv",
    "unknown_branch.csv", "reject_report.csv",
)

Column = Dict[str, Any]
Spec = Sequence[Tuple[str, str]]

# What an account number has to look like: two capitals, two digits, then 12 to 30 capitals or digits.
IBAN = "[A-Z]{2}[0-9]{2}[A-Z0-9]{12,30}"
CURRENCY = "[A-Z]{3}"
MID_VALUE = 10_000

PAYMENT: Spec = (
    ("txn_id", "int"), ("txn_ref", "str"), ("batch_id", "int"), ("seq_no", "int"),
    ("value_date", "date"), ("booking_date", "date"), ("created_ts", "stamp"),
    ("amount", "money"), ("fee", "money"), ("instructed_amount", "money"), ("fx_rate", "rate"),
    ("currency", "str"), ("instructed_currency", "str"),
    ("debit_account", "str"), ("credit_account", "str"), ("debit_bic", "str"), ("credit_bic", "str"),
    ("debit_country", "str"), ("credit_country", "str"), ("branch_code", "str"), ("customer_id", "int"),
    ("channel", "str"), ("product_code", "str"), ("status", "str"), ("priority", "int"),
    ("charge_bearer", "str"), ("settlement_method", "str"), ("clearing_system", "str"),
    ("narrative", "str"), ("remittance_info", "str"), ("end_to_end_id", "str"), ("uetr", "str"),
    ("ordering_name", "str"), ("beneficiary_name", "str"), ("beneficiary_type", "str"),
    ("mandate_id", "str"), ("cost_code", "str"), ("tax_code", "str"),
    ("is_urgent", "bool"), ("is_recurring", "bool"), ("risk_score", "float"),
    ("source_system", "str"), ("file_name", "str"), ("operator_id", "str"), ("comment", "str"),
)
BRANCH: Spec = (("branch_code", "str"), ("branch_name", "str"), ("region", "str"), ("cost_centre", "str"))
CUSTOMER: Spec = (
    ("customer_id", "int"), ("customer_name", "str"), ("segment", "str"), ("status", "str"),
    ("risk_rating", "str"), ("home_country", "str"),
)
PURPOSE: Spec = (("purpose_code", "str"), ("purpose_name", "str"), ("category", "str"))
SETTING: Spec = (("key", "str"), ("value", "str"))
JOINED: Spec = tuple(PAYMENT) + (("region", "str"), ("cost_centre", "str"))
# The payment as text, to read a reject file back; the amount stays a number so it can be added up.
REJECTED: Spec = tuple((name, "money" if name == "amount" else "str") for name, _ in PAYMENT)

# ------------------------------------------------------------------
# The maps' expressions: (output column, type, Python, Java)
# ------------------------------------------------------------------

_INVOICE = r"INV-\d{4}-\d{6}"
_LIMIT_JAVA = "new java.math.BigDecimal(context.high_value_limit)"

Mapped = Tuple[str, str, str, str]


def _same(name: str, kind: str, source: str) -> Mapped:
    """A column handed on as it is."""
    return (name, kind, f"{source}.{name}", f"{source}.{name}")


# The first map keeps the columns the rest of the job needs and works out the ones made by a pattern.
PREPARED: Sequence[Mapped] = (
    _same("txn_id", "int", "joined"), _same("txn_ref", "str", "joined"), _same("seq_no", "int", "joined"),
    _same("value_date", "date", "joined"), _same("booking_date", "date", "joined"),
    _same("currency", "str", "joined"), _same("amount", "money", "joined"), _same("fee", "money", "joined"),
    ("amount_usd", "money", "joined.amount * joined.fx_rate", "joined.amount.multiply(joined.fx_rate)"),
    _same("debit_account", "str", "joined"), _same("credit_account", "str", "joined"),
    _same("debit_country", "str", "joined"), _same("credit_country", "str", "joined"),
    _same("branch_code", "str", "joined"), _same("region", "str", "joined"), _same("cost_centre", "str", "joined"),
    _same("customer_id", "int", "joined"), _same("channel", "str", "joined"),
    # Runs of blanks in the narrative become one blank.
    ("narrative", "str", r"re.sub(r'\s+', ' ', joined.narrative).strip()",
     'joined.narrative.replaceAll("\\\\s+", " ").trim()'),
    # The invoice the payment settles, when its narrative names one.
    ("invoice_ref", "str",
     f"re.search(r'{_INVOICE}', joined.narrative).group(0) if re.search(r'{_INVOICE}', joined.narrative) else None",
     'joined.narrative.matches(".*INV-\\\\d{4}-\\\\d{6}.*") '
     '? joined.narrative.replaceAll("^.*?(INV-\\\\d{4}-\\\\d{6}).*$", "$1") : null'),
    # The purpose code, pulled out of the remittance text; the second map looks it up.
    ("purpose_code", "str", r"re.search(r'/PURP/([A-Z]{4})', joined.remittance_info).group(1)",
     'joined.remittance_info.replaceAll("^.*/PURP/([A-Z]{4}).*$", "$1")'),
)

ROUTE: Mapped = (
    "route", "str", "prepared.debit_country + '-' + prepared.credit_country",
    'prepared.debit_country + "-" + prepared.credit_country',
)
_CUSTOMER_NAME: Mapped = ("customer_name", "str", "cust.customer_name", "cust.customer_name")
_SEGMENT: Mapped = ("segment", "str", "cust.segment", "cust.segment")
_PURPOSE_NAME: Mapped = ("purpose_name", "str", "purp.purpose_name", "purp.purpose_name")

ENRICHED: Sequence[Mapped] = (
    _same("txn_id", "int", "prepared"), _same("txn_ref", "str", "prepared"),
    _same("value_date", "date", "prepared"), _same("booking_date", "date", "prepared"),
    _same("currency", "str", "prepared"), _same("amount", "money", "prepared"), _same("fee", "money", "prepared"),
    _same("amount_usd", "money", "prepared"),
    ("value_band", "str",
     f"'HIGH' if prepared.amount_usd >= context.high_value_limit else "
     f"('MID' if prepared.amount_usd >= {MID_VALUE} else 'LOW')",
     f'prepared.amount_usd.compareTo({_LIMIT_JAVA}) >= 0 ? "HIGH" : '
     f'(prepared.amount_usd.compareTo(new java.math.BigDecimal({MID_VALUE})) >= 0 ? "MID" : "LOW")'),
    _same("debit_account", "str", "prepared"), _same("credit_account", "str", "prepared"),
    _same("debit_country", "str", "prepared"), _same("credit_country", "str", "prepared"),
    ("is_cross_border", "str", "'Y' if Var['crosses'] else 'N'", 'Var.crosses ? "Y" : "N"'),
    ROUTE,
    _same("branch_code", "str", "prepared"), _same("region", "str", "prepared"),
    _same("cost_centre", "str", "prepared"), _same("customer_id", "int", "prepared"),
    _CUSTOMER_NAME, _SEGMENT, ("risk_rating", "str", "cust.risk_rating", "cust.risk_rating"),
    ("active_customer", "str", "'N' if pd.isna(cust.customer_name) else 'Y'", 'cust.customer_name == null ? "N" : "Y"'),
    _same("purpose_code", "str", "prepared"), _PURPOSE_NAME,
    ("purpose_category", "str", "purp.category", "purp.category"),
    _same("invoice_ref", "str", "prepared"), _same("narrative", "str", "prepared"),
    ("channel", "str", "prepared.channel.lower()", "prepared.channel.toLowerCase()"),
    ("reference", "str", "prepared.txn_ref + '/' + str(prepared.seq_no)", 'prepared.txn_ref + "/" + prepared.seq_no'),
    ("business_date", "str", "context.business_date", "context.business_date"),
)
HIGH_VALUE: Sequence[Mapped] = (
    _same("txn_id", "int", "prepared"), _same("txn_ref", "str", "prepared"), _same("value_date", "date", "prepared"),
    _same("currency", "str", "prepared"), _same("amount", "money", "prepared"),
    _same("amount_usd", "money", "prepared"), _same("customer_id", "int", "prepared"),
    _CUSTOMER_NAME, _SEGMENT, _same("region", "str", "prepared"),
)
CROSS_BORDER: Sequence[Mapped] = (
    _same("txn_id", "int", "prepared"), _same("txn_ref", "str", "prepared"), _same("value_date", "date", "prepared"),
    _same("debit_country", "str", "prepared"), _same("credit_country", "str", "prepared"), ROUTE,
    _same("currency", "str", "prepared"), _same("amount_usd", "money", "prepared"),
    _same("purpose_code", "str", "prepared"), _PURPOSE_NAME,
)
SUMMARY: Spec = (
    ("value_date", "date"), ("currency", "str"), ("region", "str"), ("payments", "int"),
    ("total_usd", "money"), ("average_usd", "money"), ("largest_usd", "money"),
)
REJECT_REPORT: Spec = (("currency", "str"), ("rejects", "int"), ("amount", "money"))

_TYPES = {"int": "int", "str": "str", "float": "float", "bool": "bool", "date": "datetime", "stamp": "datetime",
          "money": "Decimal", "rate": "Decimal"}
_EXTRAS: Dict[str, Dict[str, Any]] = {
    "date": {"date_pattern": "%Y-%m-%d"}, "stamp": {"date_pattern": "%Y-%m-%d %H:%M:%S"},
    "money": {"precision": 2}, "rate": {"precision": 4},
}


def columns(spec: Spec) -> List[Column]:
    """Declared columns from (name, kind) pairs."""
    return [
        {"name": name, "type": _TYPES[kind], "nullable": True, "key": False, **_EXTRAS.get(kind, {})}
        for name, kind in spec
    ]


def _spec(mapped: Sequence[Mapped]) -> Spec:
    return tuple((name, kind) for name, kind, _, _ in mapped)


# ------------------------------------------------------------------
# Components
# ------------------------------------------------------------------

def _reader(component_id: str, path: Path, spec: Spec, *outputs: str) -> Dict[str, Any]:
    config = {"filepath": str(path), "fieldseparator": ";", "row_separator": "\\n", "header_rows": 1,
              "encoding": "UTF-8", "remove_empty_row": True, "die_on_error": False}
    return {"id": component_id, "type": "FileInputDelimited", "config": config,
            "schema": {"input": [], "output": columns(spec)}, "inputs": [], "outputs": list(outputs)}


def _writer(component_id: str, path: Path, spec: Optional[Spec], source: str) -> Dict[str, Any]:
    config = {"filepath": str(path), "fieldseparator": ";", "row_separator": "\\n", "encoding": "UTF-8",
              "include_header": True, "file_exist_exception": False}
    return {"id": component_id, "type": "FileOutputDelimited", "config": config,
            "schema": {"input": columns(spec) if spec else [], "output": []}, "inputs": [source], "outputs": []}


def _flow(name: str, source: str, target: str, kind: str = "flow") -> Dict[str, str]:
    return {"name": name, "from": source, "to": target, "type": kind}


def _matches(column: str, pattern: str) -> Dict[str, str]:
    return {"column": column, "function": "", "operator": "MATCHES", "value": pattern}


def _said(variant: str, python: str, java: str) -> str:
    """An expression in the variant's language; the converter marks Java with ``{{java}}``."""
    return "{{java}}" + java if variant == "java" else python


def _output(variant: str, name: str, mapped: Sequence[Mapped], filtered: str = "") -> Dict[str, Any]:
    return {
        "name": name, "is_reject": False, "inner_join_reject": False, "filter": filtered,
        "activate_filter": bool(filtered),
        "columns": [
            {"name": column, "expression": _said(variant, python, java), "type": _TYPES[kind], "nullable": True}
            for column, kind, python, java in mapped
        ],
    }


def _lookup(name: str, column: str, kind: str, key: str, filtered: str = "") -> Dict[str, Any]:
    return {
        "name": name, "matching_mode": "UNIQUE_MATCH", "lookup_mode": "LOAD_ONCE", "filter": filtered,
        "activate_filter": bool(filtered), "join_mode": "LEFT_OUTER_JOIN",
        "join_keys": [{"lookup_column": column, "expression": key, "type": kind, "nullable": True, "operator": "="}],
    }


def _map(variant: str, component_id: str, config: Dict[str, Any], inputs: Dict[str, Spec]) -> Dict[str, Any]:
    """A PyMap with Python expressions, or a tMap with Java ones."""
    return {
        "id": component_id, "type": "Map" if variant == "java" else "PyMap", "config": config,
        "schema": {"inputs": {name: columns(spec) for name, spec in inputs.items()}},
        "inputs": list(inputs), "outputs": [output["name"] for output in config["outputs"]],
    }


def _prepare(variant: str) -> Dict[str, Any]:
    """The first map: the columns the job goes on with, and the ones a pattern makes."""
    config = {
        "inputs": {"main": {"name": "joined", "filter": "", "activate_filter": False}, "lookups": []},
        "variables": [],
        "outputs": [_output(variant, "prepared", PREPARED)],
    }
    return _map(variant, "prepare", config, {"joined": JOINED})


def _enrich(variant: str) -> Dict[str, Any]:
    """The second map: two lookups, and three outputs that each take the rows of their own condition."""
    def said(python: str, java: str) -> str:
        return _said(variant, python, java)

    config = {
        "inputs": {
            "main": {"name": "prepared", "filter": "", "activate_filter": False},
            "lookups": [
                # Only customers that are still active are looked up. Talend would write the Java filter on
                # the lookup's own row (cust.status). v1's tMap hands the filter the lookup's rows under the
                # main flow's name, and finds no customer at all when the filter is written Talend's way, so
                # the Java spelling here is the one v1 reads.
                _lookup("cust", "customer_id", "int", said("prepared.customer_id", "prepared.customer_id"),
                        said("cust.status == 'ACTIVE'", '"ACTIVE".equals(prepared.status)')),
                # The code the first map pulled out of the remittance text is looked up here.
                _lookup("purp", "purpose_code", "str", said("prepared.purpose_code", "prepared.purpose_code")),
            ],
        },
        "variables": [{
            "name": "crosses", "type": "bool", "nullable": True,
            "expression": said("prepared.debit_country != prepared.credit_country",
                               "!prepared.debit_country.equals(prepared.credit_country)"),
        }],
        "outputs": [
            _output(variant, "enriched", ENRICHED),
            _output(variant, "high_value", HIGH_VALUE,
                    said("prepared.amount_usd >= context.high_value_limit",
                         f"prepared.amount_usd.compareTo({_LIMIT_JAVA}) >= 0")),
            _output(variant, "cross_border", CROSS_BORDER, said("Var['crosses']", "Var.crosses")),
        ],
    }
    return _map(variant, "enrich", config, {"prepared": _spec(PREPARED), "cust": CUSTOMER, "purp": PURPOSE})


def build(variant: str, data_dir: Path, out_dir: Path) -> Dict[str, Any]:
    """The job config.

    Args:
        variant: ``python`` or ``java``; see the module's own words.
        data_dir: Where the input files are.
        out_dir: Where the job writes.
    """
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant!r}; use one of {', '.join(VARIANTS)}")
    enriched = _spec(ENRICHED)

    settings = [
        _reader("settings_in", data_dir / "settings.csv", SETTING, "settings"),
        {"id": "load_settings", "type": "ContextLoad", "config": {},
         "schema": {"input": columns(SETTING), "output": []}, "inputs": ["settings"], "outputs": []},
    ]
    enrich = [
        _reader("payments_in", data_dir / "payments.csv", PAYMENT, "payments"),
        _reader("branches_in", data_dir / "branches.csv", BRANCH, "branches"),
        _reader("customers_in", data_dir / "customers.csv", CUSTOMER, "cust"),
        _reader("purposes_in", data_dir / "purposes.csv", PURPOSE, "purp"),
        {"id": "format_check", "type": "FilterRows",
         "config": {"logical_op": "&&", "conditions": [
             _matches("debit_account", IBAN), _matches("credit_account", IBAN), _matches("currency", CURRENCY),
             {"column": "amount", "function": "", "operator": ">", "value": "0"},
         ]},
         "schema": {"input": columns(PAYMENT), "output": columns(PAYMENT)},
         "inputs": ["payments"], "outputs": ["checked", "format_bad"]},
        {"id": "no_repeats", "type": "UniqueRow",
         "config": {"key_columns": [{"column": "txn_ref", "case_sensitive": True}]},
         "schema": {"input": columns(PAYMENT), "output": columns(PAYMENT)},
         "inputs": ["checked"], "outputs": ["single"]},
        {"id": "branch_join", "type": "Join",
         "config": {"join_key": [{"input_column": "branch_code", "lookup_column": "branch_code"}],
                    "use_inner_join": True, "use_lookup_cols": True,
                    "lookup_cols": [{"output_column": "region", "lookup_column": "region"},
                                    {"output_column": "cost_centre", "lookup_column": "cost_centre"}]},
         "schema": {"input": columns(BRANCH), "output": columns(JOINED)},
         "inputs": ["single", "branches"], "outputs": ["joined", "branch_bad"]},
        _prepare(variant),
        _enrich(variant),
        {"id": "by_date", "type": "SortRow",
         "config": {"criteria": [{"column": "value_date", "sort_type": "date", "order": "asc"},
                                 {"column": "amount_usd", "sort_type": "num", "order": "desc"},
                                 {"column": "txn_id", "sort_type": "num", "order": "asc"}]},
         "schema": {"input": columns(enriched), "output": columns(enriched)},
         "inputs": ["enriched"], "outputs": ["sorted_rows", "sorted_totals"]},
        {"id": "totals", "type": "AggregateRow",
         "config": {"groupbys": [{"input_column": name, "output_column": name}
                                 for name in ("value_date", "currency", "region")],
                    "operations": [
                        {"output_column": "payments", "function": "count", "input_column": "txn_id"},
                        {"output_column": "total_usd", "function": "sum", "input_column": "amount_usd"},
                        {"output_column": "average_usd", "function": "avg", "input_column": "amount_usd"},
                        {"output_column": "largest_usd", "function": "max", "input_column": "amount_usd"},
                    ]},
         "schema": {"input": columns(enriched), "output": columns(SUMMARY)},
         "inputs": ["sorted_totals"], "outputs": ["summary"]},
        _writer("enriched_out", out_dir / "enriched.csv", enriched, "sorted_rows"),
        _writer("high_value_out", out_dir / "high_value.csv", _spec(HIGH_VALUE), "high_value"),
        _writer("cross_border_out", out_dir / "cross_border.csv", _spec(CROSS_BORDER), "cross_border"),
        _writer("summary_out", out_dir / "summary.csv", SUMMARY, "summary"),
        _writer("format_rejects_out", out_dir / "format_rejects.csv", None, "format_bad"),
        _writer("unknown_branch_out", out_dir / "unknown_branch.csv", None, "branch_bad"),
    ]
    flows = [
        _flow("settings", "settings_in", "load_settings"),
        _flow("payments", "payments_in", "format_check"),
        _flow("checked", "format_check", "no_repeats"),
        _flow("format_bad", "format_check", "format_rejects_out", "reject"),
        _flow("single", "no_repeats", "branch_join", "unique"),
        _flow("branches", "branches_in", "branch_join"),
        _flow("joined", "branch_join", "prepare"),
        _flow("prepared", "prepare", "enrich"),
        _flow("branch_bad", "branch_join", "unknown_branch_out", "reject"),
        _flow("cust", "customers_in", "enrich"),
        _flow("purp", "purposes_in", "enrich"),
        _flow("enriched", "enrich", "by_date"),
        _flow("high_value", "enrich", "high_value_out"),
        _flow("cross_border", "enrich", "cross_border_out"),
        _flow("sorted_rows", "by_date", "enriched_out"),
        _flow("sorted_totals", "by_date", "totals"),
        _flow("summary", "totals", "summary_out"),
    ]
    report = [
        _reader("format_rejects_in", out_dir / "format_rejects.csv", tuple(REJECTED) + (("errorMessage", "str"),),
                "format_bad_back"),
        _reader("unknown_branch_in", out_dir / "unknown_branch.csv", REJECTED, "branch_bad_back"),
        {"id": "all_rejects", "type": "Unite", "config": {},
         "schema": {"input": columns(REJECTED), "output": columns(REJECTED)},
         "inputs": ["format_bad_back", "branch_bad_back"], "outputs": ["rejected"]},
        {"id": "reject_counts", "type": "AggregateRow",
         "config": {"groupbys": [{"input_column": "currency", "output_column": "currency"}],
                    "operations": [
                        {"output_column": "rejects", "function": "count", "input_column": "txn_ref"},
                        {"output_column": "amount", "function": "sum", "input_column": "amount"},
                    ]},
         "schema": {"input": columns(REJECTED), "output": columns(REJECT_REPORT)},
         "inputs": ["rejected"], "outputs": ["reject_report"]},
        _writer("reject_report_out", out_dir / "reject_report.csv", REJECT_REPORT, "reject_report"),
    ]
    flows += [
        _flow("format_bad_back", "format_rejects_in", "all_rejects"),
        _flow("branch_bad_back", "unknown_branch_in", "all_rejects"),
        _flow("rejected", "all_rejects", "reject_counts"),
        _flow("reject_report", "reject_counts", "reject_report_out"),
    ]
    triggers = [
        {"type": "OnSubjobOk", "from": "settings_in", "to": "payments_in"},
        # The report is only made when the format check turned something away.
        {"type": "RunIf", "from": "format_rejects_out", "to": "format_rejects_in",
         "condition": '((Integer)globalMap.get("format_rejects_out_NB_LINE")) > 0'},
    ]
    return {
        "job_name": f"payments_end_of_day_{variant}", "job_type": "Standard", "default_context": "Default",
        # The two settings are declared empty here; the first stage loads them from the settings file.
        "context": {"Default": {"business_date": {"value": "", "type": "str"},
                                "high_value_limit": {"value": "0", "type": "int"}}},
        "components": settings + enrich + report, "flows": flows, "triggers": triggers, "subjobs": {},
        "java_config": {"enabled": variant == "java", "routines": [], "libraries": []},
    }


def write(variant: str, data_dir: Path, out_dir: Path, target: Path) -> Path:
    """Write the job config as a JSON file and say where it is."""
    target.write_text(json.dumps(build(variant, data_dir, out_dir), indent=2), encoding="utf-8")
    return target
