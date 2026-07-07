from docx import Document

from agents.tools.extract_doc import (
    ExtractResult, _read_section_prose, extract_doc, to_dict,
)


def _table(doc, header, rows):
    t = doc.add_table(rows=1, cols=len(header))
    for i, h in enumerate(header):
        t.rows[0].cells[i].text = h
    for r in rows:
        cells = t.add_row().cells
        for i, v in enumerate(r):
            cells[i].text = v
    return t


def test_extract_result_new_fields_default():
    r = ExtractResult(
        sources_schema={}, rules=[], sample_input={}, expected_output={},
        output_keys={}, derived_facts={}, conformance=None,
    )
    assert r.notes == "" and r.extra_sections == {} and r.tier == "build"
    d = to_dict(r)
    assert d["notes"] == "" and d["extra_sections"] == {} and d["tier"] == "build"


def test_read_section_prose_collects_paragraphs(tmp_path):
    doc = Document()
    doc.add_heading("Notes / Special Handling", level=1)
    doc.add_paragraph("Trim whitespace on all keys.")
    doc.add_paragraph("Amounts are in minor units.")
    path = tmp_path / "n.docx"
    doc.save(str(path))
    prose = _read_section_prose(Document(str(path)))
    assert prose["Notes / Special Handling"] == "Trim whitespace on all keys.\nAmounts are in minor units."


def _min_doc(path, with_notes=False):
    doc = Document()
    doc.add_heading("Inputs and Schema", level=1)
    _table(doc, ["Source", "Column", "Type", "Nullable", "Key"], [["src", "id", "str", "false", "true"]])
    doc.add_heading("Transformation Rules", level=1)
    _table(doc, ["ID", "Kind", "Description"], [["R1", "sort", "order by id"]])
    if with_notes:
        doc.add_heading("Notes / Special Handling", level=1)
        doc.add_paragraph("Keys are case-sensitive.")
    doc.save(str(path))


def test_extract_doc_captures_notes(tmp_path):
    path = tmp_path / "d.docx"
    _min_doc(path, with_notes=True)
    result = extract_doc(str(path))
    assert result.notes == "Keys are case-sensitive."


def test_extract_doc_no_notes_is_empty_string(tmp_path):
    path = tmp_path / "d.docx"
    _min_doc(path, with_notes=False)
    assert extract_doc(str(path)).notes == ""
