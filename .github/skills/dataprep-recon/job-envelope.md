# Job envelope contract (engine-verified)

Every component needs a `subjob_id`. Component `schema` is `{"input": [...], "output": [...]}` (NOT a flat list). Flows are `{"name": <flow>, "type": "flow", "from": <id>, "to": <id>}` and each component carries `inputs`/`outputs` lists referencing flow names. `type:"main"` on a flow routes NOTHING; use `"flow"`. The default enrichment join is a `LEFT_OUTER_JOIN` that KEEPS ALL source rows -- an unmatched source row still flows out, with null lookup columns. `inner_join_reject: true` on an output is AVAILABLE if a job must route unmatched source rows to a reject output (`is_reject` stays empty for a join miss), but that is NOT the enrichment default.

Minimal envelope example (LEFT-join enrichment -- keeps all source rows, lookup adds `country_name`):

```json
{
  "components": [
    {"id": "in_source", "type": "FileInputDelimited", "subjob_id": "sj1",
     "schema": {"input": [], "output": [{"name": "cc", "type": "string"}]},
     "config": {"filepath": "source.csv", "fieldseparator": ";"},
     "inputs": [], "outputs": ["source_flow"]},
    {"id": "out_enriched", "type": "FileOutputDelimited", "subjob_id": "sj1",
     "schema": {"input": [{"name": "cc", "type": "string"}, {"name": "country_name", "type": "string"}], "output": []},
     "config": {"filepath": "enriched.csv", "fieldseparator": ";"},
     "inputs": ["enriched_flow"], "outputs": []}
  ],
  "flows": [
    {"name": "enriched_flow", "type": "flow", "from": "tmap", "to": "out_enriched"}
  ]
}
```
