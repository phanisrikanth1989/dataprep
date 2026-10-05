# 01 - Usage count of real v1 jobs

Status: open
Type: task

## Question

Which components, config keys and Java constructs do real v1 job configs
actually use? The 10-15 component set, and the order the expression work is
done in, should follow real usage. The only job configs in this repo are 37
converter fixtures (`tests/talend_xml_samples/converted_jsons/`), which
over-represent LogRow and single-component jobs.

The work, in two halves:

- Agent: write a small script that walks a folder of v1 job configs and prints
  aggregate counts only. Standard library only, Python 3.12, runs on Windows
  and RHEL. It counts:
  - component types: jobs using each, and instances;
  - per component type, which config keys appear and how often;
  - value distributions for a fixed allow-list of low-risk keys: `encoding`,
    `fieldseparator`, `row_separator`, `csv_option`, `header_rows`,
    `footer_rows`, `die_on_error`, `join_mode`, `matching_mode`,
    `lookup_mode`, aggregate `function`, filter `operator` and `function`,
    `sort_type`, `order`, `keep`;
  - flow types, trigger types, schema type names and date patterns;
  - `{{java}}` strings by component type and config key, and how many use
    each construct that needs rewriting: ternary, `.equals(`, `&&` / `||`,
    string methods, `StringHandling.` / `TalendDate.` / other routine calls,
    `globalMap`, casts, `null`.

  It must never print file paths, expressions, context values or any other
  job content: the output has to be safe to carry off the machine it runs on.
- Human: run it where the real v1 job configs live and paste the output into
  this ticket.

Resolved when the counts are recorded here. They feed
[Pin the component list](27-pin-the-component-list.md) and
[Python expressions: what is allowed and how it reads](16-python-expressions-allowed.md).
