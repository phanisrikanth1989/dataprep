# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the
actual strings used in this repo's issue tracker.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding
string from this table.

## How they are applied here

This repo uses a local-markdown issue tracker (`docs/agents/issue-tracker.md`), so these are
not tracker labels — they are the value of the `Status:` line near the top of each issue file:

```markdown
# 03 - Fix tMap reject-flow row counts

Status: ready-for-agent
```

One role per issue at a time. Re-triaging means rewriting that line, not adding a second one.

Edit the right-hand column above to match whatever vocabulary you actually use.
