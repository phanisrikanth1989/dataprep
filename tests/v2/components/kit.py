"""Helpers the component tests share: schema shorthand and small job configs."""
from typing import Any, Dict, List, Optional


def columns(shorthand: str) -> List[Dict[str, Any]]:
    """Columns from shorthand: ``"id:int!, amt:Decimal#2, d:datetime@%Y-%m-%d"``.

    ``!`` marks a column that may not be missing, ``#n`` gives the declared
    decimal places and ``@pattern`` the date pattern.
    """
    made = []
    for part in shorthand.split(","):
        name, _, rest = part.strip().partition(":")
        pattern = None
        if "@" in rest:
            rest, pattern = rest.split("@", 1)
        precision = None
        if "#" in rest:
            rest, places = rest.split("#", 1)
            precision = int(places.rstrip("!"))
            rest += "!" if places.endswith("!") else ""
        column: Dict[str, Any] = {
            "name": name, "type": rest.rstrip("!") or "str", "nullable": not rest.endswith("!"), "key": False,
        }
        if precision is not None:
            column["precision"] = precision
        if pattern:
            column["date_pattern"] = pattern
        made.append(column)
    return made


def reader(schema: str, component_id: str = "in", path: str = "in.csv", outputs=("row1",), **config: Any) -> Dict[str, Any]:
    """A v1-shaped delimited file input reading UTF-8 text separated by ``;``."""
    made = {"filepath": path, "fieldseparator": ";", "row_separator": "\\n", "header_rows": 0,
            "encoding": "UTF-8", "die_on_error": False, "remove_empty_row": True}
    made.update(config)
    return {"id": component_id, "type": "FileInputDelimited", "config": made,
            "schema": {"input": [], "output": columns(schema)}, "inputs": [], "outputs": list(outputs)}


def writer(schema: Optional[str], component_id: str = "out", path: str = "out.csv", inputs=("row2",),
           **config: Any) -> Dict[str, Any]:
    """A v1-shaped delimited file output writing UTF-8 text separated by ``;``."""
    made = {"filepath": path, "fieldseparator": ";", "row_separator": "\\n", "encoding": "UTF-8",
            "include_header": True, "file_exist_exception": False}
    made.update(config)
    return {"id": component_id, "type": "FileOutputDelimited", "config": made,
            "schema": {"input": columns(schema) if schema else [], "output": []},
            "inputs": list(inputs), "outputs": []}


def flow(name: str, source: str, target: str, kind: str = "flow") -> Dict[str, str]:
    return {"name": name, "from": source, "to": target, "type": kind}


def job(components: List[Dict[str, Any]], flows: List[Dict[str, str]], **more: Any) -> Dict[str, Any]:
    """A job config in v1's shape."""
    made = {
        "job_name": "t", "job_type": "Standard", "default_context": "Default", "context": {"Default": {}},
        "components": components, "flows": flows, "triggers": [], "subjobs": {},
        "java_config": {"enabled": False},
    }
    made.update(more)
    return made


def through(component: Dict[str, Any], schema: str, out_schema: Optional[str] = None, **reader_config: Any) -> Dict[str, Any]:
    """file -> the component under test -> file, the usual job of a transform's test.

    The component is given the id ``it`` and the flows ``row1`` (in) and
    ``row2`` (out).
    """
    out_schema = out_schema or schema
    made = dict(component)
    made.setdefault("id", "it")
    made.setdefault("schema", {"input": columns(schema), "output": columns(out_schema)})
    made.setdefault("inputs", ["row1"])
    made.setdefault("outputs", ["row2"])
    return job(
        [reader(schema, header_rows=1, **reader_config), made, writer(out_schema)],
        [flow("row1", "in", made["id"]), flow("row2", made["id"], "out")],
    )
