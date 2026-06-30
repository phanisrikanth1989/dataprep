"""
Add connectors metadata to ui_registry.json for each component.
This defines which input/output/trigger ports each component has,
so the UI knows how to render connection points on nodes.
"""
import json
from collections import OrderedDict

INPUT_FILE = "src/router/ui_registry.json"
OUTPUT_FILE = "src/router/ui_registry.json"

# ── Trigger definitions ──────────────────────────────────────────
ALL_TRIGGERS = [
    "OnComponentOk",
    "OnComponentError",
    "OnSubjobOk",
    "OnSubjobError",
    "RunIf",
]

# ── Reusable port builders ────────────────────────────────────────
def _in_main(required=True):
    return {"name": "main", "type": "row", "label": "Main", "required": required, "maxConnections": 1}

def _in_main_multi():
    return {"name": "main", "type": "row", "label": "Main", "required": True, "maxConnections": -1}

def _in_lookup(required=False, max_conn=-1):
    return {"name": "lookup", "type": "row", "label": "Lookup", "required": required, "maxConnections": max_conn}

def _out_main(label="Main", max_conn=1):
    # maxConnections always emitted (explicit), mirroring the input ports.
    # main row outputs are single-connection (1); fan-out (tReplicate) passes -1.
    return {"name": "main", "type": "row", "label": label, "maxConnections": max_conn}

def _out_reject():
    return {"name": "reject", "type": "row", "label": "Reject", "maxConnections": 1}

def _out_duplicate():
    return {"name": "duplicate", "type": "row", "label": "Duplicate", "maxConnections": 1}

def _out_iterate():
    return {"name": "iterate", "type": "iterate", "label": "Iterate", "maxConnections": 1}

def _all_triggers():
    return {"outgoing": list(ALL_TRIGGERS), "incoming": list(ALL_TRIGGERS)}

# ── Connector pattern helpers ─────────────────────────────────────
def source():
    """Data source – no row input, main output."""
    return {"inputs": [], "outputs": [_out_main()], "triggers": _all_triggers()}

def sink():
    """Data sink – main input, no row output."""
    return {"inputs": [_in_main()], "outputs": [], "triggers": _all_triggers()}

def passthrough():
    """Main in → main out."""
    return {"inputs": [_in_main()], "outputs": [_out_main()], "triggers": _all_triggers()}

def with_reject():
    """Main in → main + reject out."""
    return {"inputs": [_in_main()], "outputs": [_out_main(), _out_reject()], "triggers": _all_triggers()}

def utility():
    """No data flow – trigger-only component."""
    return {"inputs": [], "outputs": [], "triggers": _all_triggers()}

# ── Per-component connector definitions ───────────────────────────
CONNECTOR_MAP = {
    # ═══════════════════════ FILE / INPUT ═══════════════════════
    "tFileInputDelimited":  source(),
    "tFileInputExcel":      source(),
    "tFileInputJSON":       source(),
    "tFileInputXML":        source(),
    "tFileInputPositional": source(),
    "tFileInputRaw":        source(),
    "tFileInputProperties": source(),
    "tFileInputMSXML":      source(),
    "tFileInputFullRow":    source(),
    "tFixedFlowInput":      source(),

    # ═══════════════════════ FILE / OUTPUT ══════════════════════
    "tFileOutputDelimited":   sink(),
    "tFileOutputExcel":       sink(),
    "tAdvancedFileOutputXML": sink(),
    "tFileOutputPositional":  sink(),
    "tFileOutputEBCDIC":      sink(),

    # ═══════════════════════ FILE / UTILITY ═════════════════════
    "tFileCopy":            utility(),
    "tFileDelete":          utility(),
    "tFileExist":           utility(),
    "tFileArchive":         utility(),
    "tFileUnarchive":       utility(),
    "tFileTouch":           utility(),
    "tFileProperties":      utility(),
    "tFileRowCount":        utility(),
    "tSetGlobalVar":        utility(),
    "tChangeFileEncoding":  utility(),
    "tFileList": {
        "inputs": [],
        "outputs": [_out_iterate()],
        "triggers": _all_triggers(),
    },

    # ═══════════════════════ DATABASE / ORACLE ══════════════════
    "tOracleConnection": utility(),
    "tOracleCommit":     utility(),
    "tOracleClose":      utility(),
    "tOracleRollback":   utility(),
    "tOracleInput":      source(),
    "tOracleOutput":     sink(),
    "tOracleBulkExec":   sink(),
    "tOracleRow": {
        "inputs": [_in_main(required=False)],
        "outputs": [_out_main()],
        "triggers": _all_triggers(),
    },
    "tOracleSP": {
        "inputs": [],
        "outputs": [_out_main()],
        "triggers": _all_triggers(),
    },

    # ═══════════════════════ DATABASE / MSSQL ═══════════════════
    "tMSSqlConnection": utility(),
    "tMSSqlInput":      source(),

    # ═══════════════════════ CONTEXT ════════════════════════════
    "tContextLoad": {
        "inputs": [_in_main(required=False)],
        "outputs": [],
        "triggers": _all_triggers(),
    },

    # ═══════════════════════ AGGREGATE ══════════════════════════
    "tAggregateRow":       passthrough(),
    "tAggregateSortedRow": passthrough(),
    "tUniqueRow": {
        "inputs": [_in_main()],
        "outputs": [_out_main(label="Unique"), _out_duplicate()],
        "triggers": _all_triggers(),
    },

    # ═══════════════════════ ITERATE ════════════════════════════
    "tForeach": {
        "inputs": [],
        "outputs": [_out_iterate()],
        "triggers": _all_triggers(),
    },
    "tFlowToIterate": {
        "inputs": [_in_main()],
        "outputs": [_out_iterate()],
        "triggers": _all_triggers(),
    },

    # ═══════════════════════ CONTROL ════════════════════════════
    "tPrejob": {
        "inputs": [],
        "outputs": [],
        "triggers": {
            "outgoing": ["OnComponentOk"],
            "incoming": [],
        },
    },
    "tPostjob": {
        "inputs": [],
        "outputs": [],
        "triggers": {
            "outgoing": ["OnComponentOk"],
            "incoming": [],
        },
    },
    "tDie":         utility(),
    "tWarn":        utility(),
    "tSleep":       utility(),
    "tSendMail":    utility(),
    "tRunJob":      utility(),
    "tParallelize": utility(),
    "tLoop": {
        "inputs": [],
        "outputs": [_out_iterate()],
        "triggers": _all_triggers(),
    },

    # ═══════════════════════ TRANSFORM (passthrough) ════════════
    "tFilterColumns":            passthrough(),
    "tSortRow":                  passthrough(),
    "tSampleRow":                passthrough(),
    "tSplitRow":                 passthrough(),
    "tNormalize":                passthrough(),
    "tDenormalize":              passthrough(),
    "tConvertType":              passthrough(),
    "tMemorizeRows":             passthrough(),
    "tPivotToColumnsDelimited":  passthrough(),
    "tUnpivotRow":               passthrough(),
    "tParseRecordSet":           passthrough(),
    "tReplace":                  passthrough(),
    "tLogRow":                   passthrough(),
    "tSwiftTransformer":         passthrough(),
    "tPythonDataframe":          passthrough(),
    "tRowGenerator":             source(),
    "tHashOutput":               sink(),

    # ═══════════════════════ TRANSFORM (with reject) ════════════
    "tFilterRows":               with_reject(),
    "tExtractDelimitedFields":   with_reject(),
    "tExtractPositionalFields":  with_reject(),
    "tExtractXmlFields":         with_reject(),
    "tExtractJsonFields":        with_reject(),
    "tExtractRegexFields":       with_reject(),
    "tJavaRow":                  with_reject(),
    "tPythonRow":                with_reject(),

    # ═══════════════════════ TRANSFORM (multi-input) ════════════
    "tUnite": {
        "inputs": [_in_main_multi()],
        "outputs": [_out_main()],
        "triggers": _all_triggers(),
    },
    "tReplicate": {
        "inputs": [_in_main()],
        "outputs": [_out_main(max_conn=-1)],
        "triggers": _all_triggers(),
    },

    # ═══════════════════════ TRANSFORM (join/map) ═══════════════
    "tMap": {
        "inputs": [_in_main(), _in_lookup(required=False, max_conn=-1)],
        "outputs": [_out_main(), _out_reject()],
        "triggers": _all_triggers(),
    },
    "tJoin": {
        "inputs": [_in_main(), _in_lookup(required=True, max_conn=1)],
        "outputs": [_out_main(), _out_reject()],
        "triggers": _all_triggers(),
    },
    "tXmlMap": {
        "inputs": [_in_main(), _in_lookup(required=False, max_conn=-1)],
        "outputs": [_out_main(), _out_reject()],
        "triggers": _all_triggers(),
    },

    # ═══════════════════════ PAGINATION ═════════════════════════
    "tPagination": {
        "inputs": [_in_main()],
        "outputs": [
            _out_main(label="Summary (per page)"),
            {"name": "detail", "type": "row", "label": "Detail (per row)", "maxConnections": 1},
        ],
        "triggers": _all_triggers(),
    },

    # ═══════════════════════ CODE ═══════════════════════════════
    "tJava": {
        "inputs": [_in_main(required=False)],
        "outputs": [_out_main()],
        "triggers": _all_triggers(),
    },
    "tPython": {
        "inputs": [_in_main(required=False)],
        "outputs": [_out_main()],
        "triggers": _all_triggers(),
    },
}


def add_connectors(registry: dict) -> dict:
    """Insert 'connectors' key after 'category' in each component."""
    updated = OrderedDict()
    missing = []

    for comp_name, comp_data in registry.items():
        if comp_name not in CONNECTOR_MAP:
            missing.append(comp_name)
            updated[comp_name] = comp_data
            continue

        # Build new ordered dict: label, icon, category, connectors, groups, properties.
        # Drop any pre-existing 'connectors' key so re-runs are idempotent -- it is
        # re-inserted fresh from CONNECTOR_MAP right after 'category'. Without this,
        # copying the stale key would clobber the freshly injected one.
        new_comp = OrderedDict()
        for key, value in comp_data.items():
            if key == "connectors":
                continue
            new_comp[key] = value
            if key == "category":
                new_comp["connectors"] = CONNECTOR_MAP[comp_name]

        updated[comp_name] = new_comp

    if missing:
        print(f"WARNING: No connector definition for: {missing}")

    return updated


def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        registry = json.load(f, object_pairs_hook=OrderedDict)

    print(f"Loaded {len(registry)} components")
    updated = add_connectors(registry)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(updated, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Written {len(updated)} components with connectors to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
