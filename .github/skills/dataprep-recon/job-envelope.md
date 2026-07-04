# Job envelope contract (engine-verified)

Every component needs a `subjob_id`. Component `schema` is `{"input": [...], "output": [...]}` (NOT a flat list). Flows are `{"name": <flow>, "type": "flow", "from": <id>, "to": <id>}` and each component carries `inputs`/`outputs` lists referencing flow names. `type:"main"` on a flow routes NOTHING; use `"flow"`. The default enrichment join is a `LEFT_OUTER_JOIN` that KEEPS ALL source rows -- an unmatched source row still flows out, with null lookup columns. `inner_join_reject: true` on an output is AVAILABLE if a job must route unmatched source rows to a reject output (`is_reject` stays empty for a join miss), but that is NOT the enrichment default.

Minimal connected enrichment example (source + lookup -> LEFT-join tMap -> output; every flow `from`/`to` is a real component id, and every component's `inputs`/`outputs` names a real flow):

```json
{
  "components": [
    {"id": "in_source", "type": "FileInputDelimited", "subjob_id": "sj1",
     "schema": {"input": [], "output": [{"name": "cc", "type": "str"}]},
     "config": {"filepath": "source.csv", "fieldseparator": ";", "header_rows": 1},
     "inputs": [], "outputs": ["source_flow"]},
    {"id": "in_lookup", "type": "FileInputDelimited", "subjob_id": "sj1",
     "schema": {"input": [], "output": [{"name": "cc", "type": "str"}, {"name": "country_name", "type": "str"}]},
     "config": {"filepath": "countries.csv", "fieldseparator": ";", "header_rows": 1},
     "inputs": [], "outputs": ["lookup_flow"]},
    {"id": "join1", "type": "Map", "subjob_id": "sj1",
     "schema": {"input": [{"name": "cc", "type": "str"}], "output": [{"name": "cc", "type": "str"}, {"name": "country_name", "type": "str"}]},
     "config": {
       "inputs": {
         "main": {"name": "source_flow", "matching_mode": "UNIQUE_MATCH", "lookup_mode": "LOAD_ONCE"},
         "lookups": [{"name": "lookup_flow", "join_mode": "LEFT_OUTER_JOIN",
                      "join_keys": [{"lookup_column": "cc", "expression": "source_flow.cc", "operator": "="}]}]
       },
       "outputs": [{"name": "enriched_flow", "is_reject": false, "columns": [
         {"name": "cc", "expression": "source_flow.cc", "type": "str"},
         {"name": "country_name", "expression": "lookup_flow.country_name", "type": "str"}]}]
     },
     "inputs": ["source_flow", "lookup_flow"], "outputs": ["enriched_flow"]},
    {"id": "out_enriched", "type": "FileOutputDelimited", "subjob_id": "sj1",
     "schema": {"input": [{"name": "cc", "type": "str"}, {"name": "country_name", "type": "str"}], "output": []},
     "config": {"filepath": "enriched.csv", "fieldseparator": ";", "include_header": true, "file_exist_exception": false},
     "inputs": ["enriched_flow"], "outputs": []}
  ],
  "flows": [
    {"name": "source_flow", "type": "flow", "from": "in_source", "to": "join1"},
    {"name": "lookup_flow", "type": "flow", "from": "in_lookup", "to": "join1"},
    {"name": "enriched_flow", "type": "flow", "from": "join1", "to": "out_enriched"}
  ]
}
```
