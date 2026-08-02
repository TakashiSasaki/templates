# Packaged CLI interface contract

## Status

Selection status: SELECTED

## Human CLI

Command: text-stat
Working directory: any directory with the installed command on PATH

The command accepts one UTF-8 input path or `-` for standard input and emits human-readable statistics by default.

### Structured output

Mode selector: --output json
Format: JSON
Contract version field: contractVersion

The JSON object contains `contractVersion`, `ok`, and `result`. Additive result fields are backward compatible within contract version `1` and consumers must ignore fields they do not recognize.

### Exit codes

| Code | Meaning |
|---:|---|
| 0 | Normal completion with statistics emitted and flushed |
| 2 | Invalid command, option, argument count, or non-UTF-8 input |
| 3 | Input could not be read because of a file-system or I/O failure |
| 5 | Output could not be written or flushed because of an I/O failure |

## In-place agent launcher

Supported: YES
Command: ruby bin/text-stat
Delegates to: `TextStat::CLI.run` in `src/text_stat.rb`

## Inputs, outputs, and side effects

| Item | Selected behavior |
|---|---|
| Input forms and precedence | One path argument is used; `-` reads standard input; no environment override exists |
| Standard output | Human-readable counts by default or one JSON object with `--output json`; successful output is flushed before exit code 0 |
| Standard error | One concise diagnostic for invalid invocation, encoding, input I/O failure, or output write/flush failure |
| Files or external state modified | NONE |
| Network access | NONE |
| Required permissions | Read access to the selected file or standard input and a writable standard-output destination |
| Confirmation policy | No confirmation is required because the command is read-only |
| Timeout and cancellation | The caller may interrupt the process; no background work survives process termination |
| Idempotency and retry behavior | Identical input bytes produce identical output; failed reads or writes may be retried after fixing the I/O condition |

## Compatibility and versioning

Compatibility policy: Command names, option meanings, exit codes, and existing contract-version-1 JSON fields remain backward compatible within the 1.x package series.
Deprecation policy: Deprecated options remain accepted for one minor release and emit a stderr warning before removal in a major release.
Structured contract version source: The `TextStat::CONTRACT_VERSION` constant and `contractVersion` JSON field.

## Semantic-equivalence and test requirements

The installed executable and in-place launcher must return identical counts, JSON fields, diagnostics, and exit codes. Tests cover help, version reporting, human output, structured output, additive result-field compatibility, binary standard input, invalid encoding, missing input, output write and flush failures, package build, and installed-command execution.

## Decision rationale

Rationale: A maintained CLI is warranted because terminal users and CI jobs need one stable command and agents need deterministic structured output without a service or protocol dependency.
