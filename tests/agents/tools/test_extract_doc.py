from docx import Document

from agents.tools.extract_doc import _read_sections


def test_read_sections_associates_tables_with_headings(tmp_path):
    doc = Document()
    doc.add_heading("Inputs and Schema", level=1)
    t1 = doc.add_table(rows=1, cols=1)
    t1.rows[0].cells[0].text = "schema-table"
    doc.add_heading("Sample Input", level=1)
    doc.add_heading("ledger", level=2)
    t2 = doc.add_table(rows=1, cols=1)
    t2.rows[0].cells[0].text = "ledger-table"
    path = tmp_path / "d.docx"
    doc.save(str(path))

    sections = _read_sections(Document(str(path)))

    assert set(sections.keys()) == {"Inputs and Schema", "Sample Input"}
    assert sections["Inputs and Schema"][0][0] is None
    assert sections["Inputs and Schema"][0][1].rows[0].cells[0].text == "schema-table"
    assert sections["Sample Input"][0][0] == "ledger"
    assert sections["Sample Input"][0][1].rows[0].cells[0].text == "ledger-table"


from agents.tools.extract_doc import _parse_schema_table


def _table(doc, header, rows):
    t = doc.add_table(rows=1, cols=len(header))
    for i, h in enumerate(header):
        t.rows[0].cells[i].text = h
    for r in rows:
        cells = t.add_row().cells
        for i, v in enumerate(r):
            cells[i].text = v
    return t


def test_parse_schema_table_groups_by_source():
    doc = Document()
    t = _table(
        doc,
        ["Source", "Column", "Type", "Nullable", "Key"],
        [
            ["ledger", "txn_id", "str", "false", "true"],
            ["ledger", "amt", "float", "false", "false"],
            ["statement", "ref_id", "str", "false", "true"],
        ],
    )
    schema = _parse_schema_table(t)
    assert list(schema.keys()) == ["ledger", "statement"]
    assert schema["ledger"][0].name == "txn_id"
    assert schema["ledger"][0].type == "str"
    assert schema["ledger"][0].nullable is False
    assert schema["ledger"][0].key is True
    assert schema["ledger"][1].key is False


from agents.tools.extract_doc import _parse_rules_table


def test_parse_rules_table():
    doc = Document()
    t = _table(
        doc,
        ["ID", "Kind", "Description"],
        [
            ["R1", "Match", "match ledger.txn_id to statement.ref_id"],
            ["R2", "Tolerance", "amounts equal within 0.01"],
            ["", "", ""],  # blank row ignored
        ],
    )
    rules = _parse_rules_table(t)
    assert len(rules) == 2
    assert rules[0] == {"id": "R1", "kind": "match", "description": "match ledger.txn_id to statement.ref_id"}
    assert rules[1]["kind"] == "tolerance"


from agents.tools.extract_doc import _parse_data_block


def _named_table(doc, header, rows):
    return _table(doc, header, rows)


def test_parse_data_block_sample_input():
    doc = Document()
    items = [
        ("ledger", _named_table(doc, ["txn_id", "amt"], [["T1", "100.00"], ["T2", "50.00"]])),
        ("statement", _named_table(doc, ["ref_id", "amt"], [["T1", "100.00"]])),
    ]
    data = _parse_data_block(items)
    assert data["ledger"] == [{"txn_id": "T1", "amt": "100.00"}, {"txn_id": "T2", "amt": "50.00"}]
    assert data["statement"] == [{"ref_id": "T1", "amt": "100.00"}]


def test_parse_data_block_expected_output_extracts_composite_key():
    doc = Document()
    items = [
        ("matched", _named_table(doc, ["txn_id*", "src*", "amt"], [["T1", "ledger", "100.00"]])),
    ]
    data, keys = _parse_data_block(items, extract_keys=True)
    assert keys["matched"] == ["txn_id", "src"]
    assert data["matched"] == [{"txn_id": "T1", "src": "ledger", "amt": "100.00"}]


from agents.tools.extract_doc import compute_derived_facts


def test_compute_derived_facts():
    sample = {
        "ledger": [
            {"txn_id": "T1", "amt": "100"},
            {"txn_id": "T2", "amt": ""},
            {"txn_id": "T2", "amt": "50"},
        ]
    }
    facts = compute_derived_facts(sample)["ledger"]
    assert facts["txn_id"]["unique"] is False          # T2 repeats
    assert facts["txn_id"]["max_group_size"] == 2
    assert facts["txn_id"]["n_distinct"] == 2
    assert facts["txn_id"]["null_rate"] == 0.0
    assert facts["amt"]["null_rate"] == round(1 / 3, 4)  # one empty cell
    assert facts["amt"]["unique"] is True                # 100, 50 distinct among non-null


from agents.tools.extract_doc import _check_conformance


def test_conformance_ok():
    sections = {b: [] for b in ("Inputs and Schema", "Transformation Rules", "Sample Input", "Expected Output")}
    report = _check_conformance(
        sections,
        sources_schema={"ledger": ["x"]},
        rules=[{"id": "R1"}],
        sample_input={"ledger": [{"a": "1"}]},
        expected_output={"matched": [{"a": "1"}]},
    )
    assert report.ok is True


def test_conformance_missing_block():
    sections = {"Inputs and Schema": [], "Transformation Rules": [], "Sample Input": []}
    report = _check_conformance(sections, {"ledger": ["x"]}, [{"id": "R1"}], {"ledger": [{"a": "1"}]}, {})
    assert report.ok is False
    assert "Expected Output" in report.missing_blocks


def test_conformance_empty_table_is_parse_error():
    sections = {b: [] for b in ("Inputs and Schema", "Transformation Rules", "Sample Input", "Expected Output")}
    report = _check_conformance(sections, {"ledger": ["x"]}, [{"id": "R1"}], {"ledger": []}, {"matched": [{"a": "1"}]})
    assert report.ok is False
    assert any("Sample Input" in e for e in report.parse_errors)
