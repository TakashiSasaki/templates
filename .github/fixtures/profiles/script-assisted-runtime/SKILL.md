---
name: line-normalization-runtime-helper
description: Normalize supplied UTF-8 text deterministically with a private Ruby helper whose runtime and exact commands are maintained in RUNTIME.md.
---

# Line normalization helper with runtime authority

## Purpose

Normalize line endings and remove trailing horizontal whitespace from a supplied UTF-8 text file using one private Ruby helper with an explicit runtime record.

## Use this skill when

Use this skill when deterministic text normalization is required and maintainers need the supported Ruby version and exact helper commands recorded separately from the operational workflow.

## Helper scripts

Script: scripts/normalize.rb
Run when: the input file must be normalized before comparison or delivery
Exact invocation: ruby scripts/normalize.rb INPUT OUTPUT
Working directory: skill root
Inputs and arguments: INPUT is a readable UTF-8 text file and OUTPUT is the destination path
Stdout/result: prints the normalized output path after a successful write
Stderr/diagnostics: reports invalid arguments, unreadable input, invalid UTF-8, or write failures
Exit status: zero on success; 2 for invalid arguments; 3 for invalid UTF-8; 1 for file-system failure
Files or external state modified: writes or replaces only the caller-supplied OUTPUT path
Network access: NONE
Required permissions: read access to INPUT and write access to OUTPUT
Automatic execution allowed: YES
Human confirmation required: NO
Idempotency and retry behavior: repeated execution with the same input produces identical output and may be retried after correcting a reported failure

## Runtime authority

Runtime identity, portability, and exact shared commands are authoritative in `RUNTIME.md`. The helper uses only the Ruby standard library and is not a packaged public CLI.

## Workflow

1. Confirm that the input and output paths are distinct.
2. From the skill root, run `ruby scripts/normalize.rb INPUT OUTPUT`.
3. Stop on a nonzero exit status and report the stderr diagnostic.
4. Validate the generated output before comparison or delivery.

## Output requirements

Return the output path and whether normalization changed the text. The output must use LF line endings, contain no trailing horizontal whitespace, and end with one newline.

## Validation

Run `ruby -c scripts/normalize.rb`, execute the helper on representative UTF-8 input, and confirm that the input remains unchanged and the output is deterministic.

## Safety and approval

Write only to the caller-supplied output path. Do not access the network, install dependencies, modify the input file, or treat the helper as a stable public CLI.

Selected profiles: script-assisted
