# Public interface contracts

This file prevents humans and agents from having to infer which equivalent interface to use.

## Execution policy

A concrete skill must select exactly one preferred agent interface and define a deterministic fallback order.

```text
Preferred agent interface: UNSELECTED
Fallback 1: UNSELECTED
Fallback 2: UNSELECTED
```

Allowed interface categories:

- native MCP tool already registered in the host;
- bundled ad hoc stdio MCP client;
- stable in-place CLI launcher;
- installed human CLI command.

Do not write “use whichever is appropriate” unless all routes are intentionally interchangeable and nondeterminism is acceptable.

## Human CLI

```text
Command: TODO
Working directory: TODO
```

The CLI should:

- provide `--help`;
- emit readable terminal output by default;
- provide a structured output mode when results are consumed by an agent or CI;
- send diagnostics to stderr;
- use documented, stable exit codes;
- avoid embedding domain logic in argument parsing or formatting code.

### Structured output

```text
Format: TODO, normally JSON
Contract version field: TODO
```

Suggested result envelope:

```json
{
  "contractVersion": "1",
  "ok": true,
  "result": {},
  "errors": [],
  "warnings": [],
  "metadata": {}
}
```

### Exit codes

| Code | Meaning |
|---:|---|
| 0 | Successful execution and successful domain result |
| 1 | Successful execution with a negative validation or policy result |
| 2 | Invalid command or input |
| 3 | Missing runtime, dependency, or configuration |
| 4 | Operation refused by a safety or permission rule |
| 5 | Unexpected internal failure |

A concrete skill may revise these codes, but CLI documentation and tests must remain consistent.

## In-place agent launcher

```text
Command: TODO
```

Use a stable launcher only when it adds value over the installed CLI. A launcher may locate the skill root and delegate to the selected runtime, but it must not implement domain behavior.

## stdio MCP server

```text
Supported: UNSELECTED
Launch command: TODO or NOT SUPPORTED
```

When supported:

- expose purpose-specific tools with typed inputs;
- keep stdout exclusively for protocol traffic;
- send logs to stderr;
- return structured results compatible with the CLI result model;
- reuse the same application/domain implementation as the CLI;
- document workspace and write restrictions;
- avoid generic `run_command` or arbitrary-code tools.

## Ad hoc MCP client

```text
Supported: UNSELECTED
Command: TODO or NOT SUPPORTED
Session scope: one call / multiple calls: TODO
```

An ad hoc client is justified when the MCP protocol path itself matters, several MCP tools benefit from one session, or the same server is also consumed by native MCP hosts. For a single stateless operation, a direct structured CLI may be simpler.

The presence of a server under `mcp/` does not register it automatically with an agent host.

## Semantic-equivalence requirement

For an operation exposed through both CLI and MCP:

- inputs must have equivalent meaning;
- results must have equivalent meaning;
- safety checks must be identical;
- differences in presentation must not change domain behavior;
- contract tests must exercise both adapters against the same fixtures.
