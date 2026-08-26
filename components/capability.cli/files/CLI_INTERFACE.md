# Packaged CLI interface contract

This contract is materialized by `capability.cli`. It defines caller-visible behavior for a maintained packaged CLI. Runtime identity, dependency management, installation, build, and distribution remain authoritative in `RUNTIME.md`.

Private helper scripts are not public CLIs and do not require this contract.

## Machine-readable authority

`contracts/cli-interface.json` is the canonical machine-readable state for this selected capability. Its lifecycle is `template` -> `planning` -> `product`.

- `template` makes no caller-visible CLI claim and keeps the entrypoint inventory empty.
- Before product coding, switch to `planning` and enumerate every intended caller-visible entrypoint by stable `id` and non-empty `purpose`. Do not invent implementation commands, working directories, output selectors, or exit-code mappings at this stage.
- Bind each planned entrypoint exactly to an implementation-evidence planning target `contract-item / cli_interface / entrypoint / <entrypoint-id>`, with executable proof strength declared before coding. Composition validation must pass in this planning state.
- Promote the same stable IDs to `product` only when the operational invocation/output/exit-code contract is concrete. Product implementation evidence then supplies the executable positive and negative proof for those entrypoints.

When `capability.cli` is selected, planning implementation evidence cannot validate while this contract is still in `template` mode, and phantom planning target IDs are rejected. Product implementation evidence cannot remain release-valid while this contract is not in `product` mode. Static source inspection and unit-only proof do not satisfy the CLI executable-proof obligation. Use `integration-test` or `end-to-end-test` proof kinds for caller-visible CLI execution.

Keep the narrative notes below aligned with the machine contract; when they conflict, the JSON contract is authoritative for validation.

## Human and agent CLI

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
Mode selector: TODO
Format: TODO, normally JSON
Contract version field: TODO
```

The mode selector must be sufficient for a caller to construct the invocation without inferring implementation details.

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

Another envelope is valid when field stability, forward-compatible extension behavior, and negative-domain-result semantics are documented.

### Exit codes

| Code | Meaning |
|---:|---|
| 0 | Successful execution and successful domain result |
| 1 | Successful execution with a negative validation, policy, or domain result |
| 2 | Invalid command or input |
| 3 | Missing runtime, dependency, endpoint, or configuration |
| 4 | Refused by a safety, authorization, or permission rule |
| 5 | Protocol, transport, or unexpected internal failure |
| 6 | Additional input required in non-interactive mode |

A concrete artifact may revise the mapping, but every documented code must be an integer from 0 through 255.

## Inputs, outputs, and side effects

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

Specify which changes are backward compatible, how deprecations are announced, and when a contract-version change is required. Do not infer interface compatibility solely from the package version.

## Semantic-equivalence and tests

When the same operation is exposed through CLI, MCP, Web, or a headless service under the same identity, authorization, configuration, and workspace policy:

- inputs, results, side effects, and safety checks have equivalent meaning;
- presentation differences do not change domain behavior;
- adapters reuse the same tested operation implementation when justified;
- contract tests cover the canonical command, structured output, diagnostics, exit codes, invalid input, refusal, cancellation, and installation or in-place execution as applicable.

## Decision rationale

Explain why a maintained packaged CLI is warranted, which compatibility guarantees callers may rely on, and why the selected command and output contracts fit the artifact.

```text
Rationale: TODO
```
