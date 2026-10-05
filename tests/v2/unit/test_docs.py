"""Component doc pages are generated from the declared config keys."""
from scripts.gen_v2_docs import generate, page
from src.v2.components.base import Transform
from src.v2.components.registry import REGISTRY
from src.v2.job.keys import EXPRESSION, Key, Kind


class Sample(Transform):
    """Keep some rows.

    A second paragraph.
    """

    names = ("sample", "Sample", "tSample")
    outputs = {"main": ("flow", "main", "filter"), "reject": ("reject",)}
    keys = (
        Key("condition", type=EXPRESSION, required=True, aliases=("advanced_cond",), doc="Rows to keep."),
        Key("mode", default="a|b", choices=("a|b", "c"), doc="How."),
        Key("rules", type=list, default=[], doc="Rules.",
            items=(Key("column", required=True, doc="The column."), Key("trim", type=bool, default=False, doc="Strip it."))),
        Key("legacy", kind=Kind.IGNORED, type=object, doc="Talend tuning knob."),
        Key("uncompress", kind=Kind.REFUSED, type=bool, reason="compressed files are not read"),
    )


def test_page_lists_every_key_by_what_v2_does_with_it():
    text = page(Sample)
    assert text.startswith("# sample\n\nKeep some rows.")
    assert "`sample`, `Sample`, `tSample`" in text
    assert "| `condition` (required) | `advanced_cond` | Python expression |  | Rows to keep. |" in text
    assert '| `mode` |  | text | `"a\\|b"` | How. One of: `a\\|b`, `c`. |' in text
    assert "| `rules[].column` (required) |" in text and "| `rules[].trim` |  | true/false | `false` | Strip it. |" in text
    assert "## Accepted and ignored" in text and "- `legacy`: Talend tuning knob." in text
    assert "## Refused" in text and "- `uncompress`: compressed files are not read" in text
    assert "`label`" in text


def test_every_registered_component_gets_a_page_and_an_index_row(tmp_path):
    written = dict(generate(tmp_path))
    names = sorted(cls.names[0] for cls in REGISTRY.classes())
    assert sorted(name for name in written if name != "README.md") == [f"{name}.md" for name in names]
    for name in names:
        assert f"[{name}]({name}.md)" in written["README.md"]
        assert (tmp_path / f"{name}.md").read_text().startswith(f"# {name}\n")
