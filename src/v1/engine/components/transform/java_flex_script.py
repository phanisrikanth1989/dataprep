"""Pure Groovy-source assembly for tJavaFlex (no bridge, no state).

Builds one unit: <START> ; for-row loop with auto-propagate + <MAIN> ; <END>.
START vars are top-level script locals, visible in the loop and in END
(Talend one-scope parity). See the Phase 3.0 design spec, section 6.
"""
from __future__ import annotations


def _propagate_lines(input_cols: list[str], output_cols: list[str],
                     in_name: str, out_name: str) -> list[str]:
    in_set = set(input_cols)
    return [f"    {out_name}.{c} = {in_name}.{c};"
            for c in output_cols if c in in_set]


def build_script(*, code_start: str, code_main: str, code_end: str,
                 input_cols: list[str], output_cols: list[str],
                 input_row_name: str, output_row_name: str,
                 auto_propagate: bool, propagate_timing: str) -> str:
    """Assemble the tJavaFlex Groovy unit. See module docstring."""
    copies = _propagate_lines(input_cols, output_cols,
                              input_row_name, output_row_name) if auto_propagate else []
    before = copies if propagate_timing == "before" else []
    after = copies if propagate_timing == "after" else []
    lines: list[str] = []
    lines.append(code_start or "")
    lines.append("for (int __i = 0; __i < input.size(); __i++) {")
    # Groovy loop-locals via `def` (NOT bare assignment, which would leak into
    # the script Binding and risk colliding with the bound input/output names).
    # Spec sec 6 shows `RowWrapper row1 = ...` illustratively; `def` avoids
    # needing the RowWrapper type imported into the script scope.
    lines.append(f"    def {input_row_name} = input.get(__i);")
    lines.append(f"    def {output_row_name} = output.get(__i);")
    lines.extend(before)
    lines.append(code_main or "")
    lines.extend(after)
    lines.append("}")
    lines.append(code_end or "")
    return "\n".join(lines)
