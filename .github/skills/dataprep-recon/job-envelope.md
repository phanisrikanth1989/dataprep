# Job envelope contract (engine-verified)

Every component needs a `subjob_id`. Component `schema` is `{"input": [...], "output": [...]}` (NOT a flat list). Flows are `{"name": <flow>, "type": "flow", "from": <id>, "to": <id>}` and each component carries `inputs`/`outputs` lists referencing flow names. `type:"main"` on a flow routes NOTHING; use `"flow"`. tMap one-sided breaks use an output with `inner_join_reject: true` (NOT `is_reject`, which stays empty for a join miss).
