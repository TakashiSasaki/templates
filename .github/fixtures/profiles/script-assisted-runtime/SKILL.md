---
name: line-normalization-runtime-helper
description: Normalize supplied UTF-8 text deterministically with a private Python helper whose runtime and exact commands are maintained in RUNTIME.md.
---

# Line normalization helper with runtime authority

## Purpose

Normalize line endings and remove trailing horizontal whitespace from a supplied UTF-8 text file using one private Python helper with an explicit runtime record.

## Use this skill when

Use this skill when deterministic text normalization is required and maintainers need the supported Python version and exact helper commands recorded separately from the operational workflow.

## Helper scripts

Script: scripts/normalize.py
Run when: the input file must be normalized before comparison or delivery
Exact invocation: python scripts/normalize.py INPUT OUTPUT
Working directory: skill root
Inputs and arguments: INPUT is a readable UTF-8 text file and OUTPUT is a distinct destination path that must not resolve to the same file as INPUT
Stdout/result: prints the normalized output path after a successful write
Stderr/diagnostics: reports invalid arguments, aliased input/output files, unreadable input, invalid UTF-8, or write failures
Exit status: zero on success; 2 for invalid arguments or aliased input/output files; 3 for invalid UTF-8; 1 for file-system failure
Files or external state modified: writes or replaces only the caller-supplied OUTPUT path
Network access: NONE
Required permissions: read access to INPUT and write access to OUTPUT
Automatic execution allowed: YES
Human confirmation required: NO
Idempotency and retry behavior: repeated execution with the same input produces identical output and may be retried after correcting a reported failure

## Runtime authority

Runtime identity, portability, and exact shared commands are authoritative in `RUNTIME.md`. The helper and its executable test use only the Python standard library, and the helper is not a packaged public CLI.

## Workflow

1. Confirm that the input and output paths are distinct and do not resolve to the same file.
2. From the skill root, run `python scripts/normalize.py INPUT OUTPUT`.
3. Stop on a nonzero exit status and report the stderr diagnostic.
4. Validate the generated output before comparison or delivery.

## Output requirements

Return the output path and whether normalization changed the text. The output must use LF line endings, contain no trailing horizontal whitespace, and end with one newline.

## Validation

From the skill root, run `python -m py_compile scripts/normalize.py` and `python tests/test_normalize.py`. The executable test confirms deterministic LF output, input immutability, same-file and hard-link alias rejection, and bounded invalid-UTF-8 failure.

## Safety and approval

Write only to the caller-supplied output path. Reject any output path that resolves to the input file. Do not access the network, install dependencies, modify the input file, or treat the helper as a stable public CLI.

Selected profiles: script-assisted
