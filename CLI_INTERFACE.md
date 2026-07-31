# Packaged CLI interface contract

Retain and complete this file only when `packaged-cli` is selected. Private helper scripts remain documented in `SKILL.md` and do not require this public compatibility contract.

Runtime identity, dependency management, installation, build, and distribution selections remain authoritative in `RUNTIME.md`. This file defines caller-visible command behavior.

## Status

```text
Selection status: UNSELECTED
```

Change the status to `SELECTED` only after every applicable field is concrete and the canonical command agrees with `RUNTIME.md` and `SKILL.md`.

## Human CLI

```text
Command: TODO
Working directory: TODO
```

The CLI must:

- provide `--help` and a stable version-reporting mechanism;
- emit readable terminal output by default;
- provide a structured output mode for agents and CI;
- send diagnostics to stderr;
- use documented stable exit codes;
- keep domain behavior out of argument parsing and presentation code;
- define compatibility expectations for command names, options, output fields, and deprecations.

### Structured output

```text
Mode selector: TODO, for example --output json, --json, a documented subcommand, or SKILL_OUTPUT=json
Format: TODO, normally JSON
Contract version field: TODO
```

`Mode selector` must record the exact caller-visible option, subcommand, or environment assignment that activates structured output. It must be sufficient for an agent or CI job to construct the structured-output invocation without inferring behavior from implementation details.

Suggested envelope:

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

A concrete skill may use another envelope, but must document field stability, forward-compatible extension behavior, and how partial or negative domain results differ from execution failures.

### Exit codes

| Code | Meaning |
|---:|---|
| 0 | Successful execution and successful domain result |
| 1 | Successful execution with a negative validation, policy, or domain result |
| 2 | Invalid command or input |
| 3 | Missing runtime, dependency, endpoint, or configuration |
| 4 | Operation refused by a safety, authorization, or permission rule |
| 5 | Protocol, transport, or unexpected internal failure |
| 6 | Operation incomplete because additional input is required in non-interactive mode |

A concrete skill may revise this mapping, but every documented code must be an integer from `0` through `255` so that its meaning survives portable process-status reporting. Documentation, tests, and every adapter exposing the same operation must remain consistent.

## In-place agent launcher

```text
Supported: TODO: YES or NO
Command: TODO or NOT SUPPORTED
Delegates to: TODO or NOT SUPPORTED
```

Use a stable in-place launcher only when it adds value over the installed CLI. It may locate the skill root and delegate to the selected runtime, but it must not implement domain behavior or silently install dependencies.

## Inputs, outputs, and side effects

Document the public contract for each maintained command or command family:

| Item | Selected behavior |
|---|---|
| Input forms and precedence | TODO |
| Standard output | TODO |
| Standard error | TODO |
| Files or external state modified | TODO or NONE |
| Network access | TODO or NONE |
| Required permissions | TODO or NONE |
| Confirmation policy | TODO |
| Timeout and cancellation | TODO |
| Idempotency and retry behavior | TODO |

## Compatibility and versioning

```text
Compatibility policy: TODO
Deprecation policy: TODO
Structured contract version source: TODO
```

Specify which changes are backward compatible, how deprecated commands or fields are announced, and when a contract-version change is required. Do not infer compatibility solely from the package version.

## Semantic-equivalence and test requirements

When the same operation is exposed through CLI, MCP, Web, or a headless service under the same identity, authorization, configuration, and workspace policy:

- inputs, results, side effects, and safety checks must have equivalent meaning;
- presentation differences must not change domain behavior;
- adapters should reuse the same tested operation implementation when that separation is justified;
- contract tests must cover the canonical command, structured output, diagnostics, exit codes, invalid input, refusal paths, cancellation, and installation or in-place execution as applicable.

## Decision rationale

Explain why a maintained packaged CLI is warranted instead of direct helper invocation, which compatibility guarantees callers may rely on, and why the selected command and output contracts fit the skill.

```text
Rationale: TODO
```
