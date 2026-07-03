# Job envelope contract (engine-verified)

Every component needs a `subjob_id`. Component `schema` is `{"input": [...], "output": [...]}` (NOT a flat list). Flows are `{"name": <flow>, "type": "flow", "from": <id>, "to": <id>}` and each component carries `inputs`/`outputs` lists referencing flow names. `type:"main"` on a flow routes NOTHING; use `"flow"`. tMap one-sided breaks use an output with `inner_join_reject: true` (NOT `is_reject`, which stays empty for a join miss).

Minimal envelope example:

```json
{
  "components": [
    {"id": "in_main", "type": "FileInputDelimited", "subjob_id": "sj1",
     "schema": {"input": [], "output": [{"name": "cc", "type": "string"}]},
     "config": {"filepath": "main.csv", "fieldseparator": ";"},
     "inputs": [], "outputs": ["main_flow"]},
    {"id": "out_matched", "type": "FileOutputDelimited", "subjob_id": "sj1",
     "schema": {"input": [{"name": "cc", "type": "string"}], "output": []},
     "config": {"filepath": "matched.csv", "fieldseparator": ";"},
     "inputs": ["matched_flow"], "outputs": []}
  ],
  "flows": [
    {"name": "matched_flow", "type": "flow", "from": "tmap", "to": "out_matched"}
  ]
}
```
