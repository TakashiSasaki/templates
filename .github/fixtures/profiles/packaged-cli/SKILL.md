---
name: text-stat-cli
description: Compute deterministic byte, line, and word counts through a packaged Ruby command with human-readable and versioned JSON output.
---

# Text statistics CLI

## Purpose

Compute deterministic byte, line, and word counts for one UTF-8 text file or standard input.

## Use this skill when

Use this skill when an agent or operator needs stable text statistics that can be consumed by a terminal user, CI job, or another program.

## Workflow

1. Select a readable UTF-8 input file or use standard input.
2. Run `text-stat INPUT` for human-readable output or `text-stat --output json INPUT` for structured output.
3. Inspect stderr and stop on a nonzero exit status.
4. Validate the reported counts against the supplied input.

## Public execution interfaces

Canonical command: text-stat
Working directory: any directory with the installed command on PATH
Preferred agent route: see INTERFACES.md
Detailed interface contract: CLI_INTERFACE.md

## Output requirements

Return byte, line, and word counts. Structured output must include `contractVersion`, `ok`, and a `result` object.

## Validation

Confirm `text-stat --help`, `text-stat --version`, human-readable output, JSON output, and documented failure exit codes through the repository test suite.

## Safety and approval

The command is read-only, does not use the network, and may run automatically on caller-supplied readable input.

Selected profiles: packaged-cli
