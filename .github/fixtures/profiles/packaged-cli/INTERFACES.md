# Public interface selection contract

## Status

Selection status: SELECTED

## Execution policy

Preferred agent interface: installed human CLI command
Fallback 1: stable in-place CLI launcher
Fallback 2: NONE

## Contract index

| Selected profile or interface | Authoritative contract |
|---|---|
| Packaged CLI caller behavior | `CLI_INTERFACE.md` |
| Runtime, commands, and packaging | `RUNTIME.md` |

## Cross-interface invariants

The installed command and in-place launcher invoke the same `TextStat::CLI` implementation and therefore use identical inputs, output fields, diagnostics, exit codes, and read-only behavior.

## Availability and failure behavior

Unavailable preferred interface behavior: Use the in-place Ruby launcher only from a trusted repository checkout.
Fallback activation conditions: Activate the fallback when the installed `text-stat` executable is absent and CRuby 3.1 or newer is available.
Failure classification exposed to callers: Exit code 2 denotes invalid invocation or input, exit code 3 denotes an input read failure, and exit code 5 denotes an output write or flush failure.

## Decision rationale

Rationale: Prefer the installed command for a stable PATH-based interface and retain one repository-local fallback for development and validation without adding another runtime or network service.
