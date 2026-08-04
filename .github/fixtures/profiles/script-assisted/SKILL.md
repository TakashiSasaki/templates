---
name: line-normalization-helper
description: Normalize supplied UTF-8 text deterministically with a private repository helper and report the generated output path.
---

# Line normalization helper

## Purpose

Normalize line endings and remove trailing horizontal whitespace from a supplied UTF-8 text file.

## Use this skill when

Use this skill when deterministic text normalization is required before comparison or review.

## Helper scripts

Script: scripts/normalize.rb
Run when: the input file must be normalized before comparison or delivery
Exact invocation: ruby scripts/normalize.rb INPUT OUTPUT
Working directory: repository root
Inputs and arguments: INPUT is a readable UTF-8 text file and OUTPUT is the destination path; INPUT and OUTPUT must refer to different files, including no hard-link or equivalent alias
Stdout/result: prints the normalized output path after a successful write
Stderr/diagnostics: reports invalid arguments, aliased input and output files, unreadable input, invalid UTF-8, or write failures
Exit status: zero on success and nonzero on validation or file-system failure
Files or external state modified: writes or replaces only the caller-supplied OUTPUT path
Network access: NONE
Required permissions: read access to INPUT and write access to OUTPUT
Automatic execution allowed: YES
Human confirmation required: NO
Idempotency and retry behavior: repeated execution with the same input produces identical output and may be retried after correcting a reported failure

## Workflow

1. Confirm that the input and output paths refer to different files.
2. Run `ruby scripts/normalize.rb INPUT OUTPUT` from the repository root.
3. Inspect any diagnostic and stop on a nonzero exit status.
4. Compare the generated output with the normalization requirements.

## Output requirements

Return the output path and whether normalization changed the text.

## Validation

Confirm that the output is valid UTF-8, uses LF line endings, has no trailing horizontal whitespace, and ends with one newline.

## Safety and approval

Write only to the caller-supplied output path, reject an output path that aliases the input file, and do not access the network or modify the input file.

Selected profiles: script-assisted
