---
name: agent-skill-template
description: Template scaffold for creating a portable Agent Skill from the smallest instruction-only form through optional knowledge, asset, helper-script, packaged CLI, MCP, browser, and headless-service profiles. Use when creating or restructuring an Agent Skill repository; replace this description with the concrete skill trigger and purpose.
---

# Agent Skill Template

This repository is a template, not a completed operational skill. Replace the guidance below with concise instructions for the concrete workflow. Delete sections and optional files that do not apply.

## Purpose

State the outcome this skill helps the agent produce.

TODO

## Use this skill when

Describe observable user requests, repository states, file types, or workflow conditions that should trigger the skill.

- TODO

## Do not use this skill when

Record important exclusions and routes to other skills or normal agent behavior.

- TODO

## Required inputs and prerequisites

List only information, permissions, tools, files, runtimes, or network access that the workflow actually requires.

- TODO

An instruction-only or knowledge-only skill may require no implementation runtime.

## Workflow

Write the shortest reliable sequence the agent should follow.

1. TODO
2. TODO
3. Validate the result against the output and safety requirements below.

Prefer explicit decision points over vague instructions such as “handle as appropriate.”

## Operational knowledge

Read references only when they are relevant to the current task. For every retained file under `references/`, state its trigger and purpose here.

```text
Reference: references/TODO.md
Read when: TODO
Provides: TODO
Authority or freshness notes: TODO
```

Delete this section and `references/` when the skill needs no additional operational knowledge.

## Assets

For every retained file under `assets/`, state when and how it is used. Assets are inputs or output resources, not instructions by themselves.

```text
Asset: assets/TODO
Use when: TODO
Handling: copy / fill / transform / attach / compare: TODO
Must remain unchanged: TODO
```

Delete this section and `assets/` when the skill uses no static resources.

## Helper scripts

A helper script is optional and is not automatically a public CLI. For every script the agent may run, document a bounded execution contract.

```text
Script: scripts/TODO
Run when: TODO
Exact invocation: TODO
Working directory: TODO
Inputs and arguments: TODO
Stdout/result: TODO
Stderr/diagnostics: TODO
Exit status: TODO
Files or external state modified: TODO
Network access: TODO
Required permissions: TODO
Automatic execution allowed: YES / NO / WITH CONDITIONS
Human confirmation required: TODO
Idempotency and retry behavior: TODO
```

Small deterministic helpers may remain self-contained. Introduce a reusable application/domain layer only when complexity, testing, or multiple maintained interfaces justify it.

Delete this section and `scripts/` when no helper is needed.

## Public execution interfaces

Most simple skills do not need a public-interface document. Describe direct helper invocation above.

When the skill intentionally maintains a stable packaged CLI, complete `RUNTIME.md`, `INTERFACES.md`, and `CLI_INTERFACE.md`, then summarize the canonical command here.

```text
Canonical command: TODO or NOT APPLICABLE
Working directory: TODO or NOT APPLICABLE
Preferred agent route: see INTERFACES.md or NOT APPLICABLE
Detailed interface contract: CLI_INTERFACE.md / MCP_INTERFACE.md / NOT APPLICABLE
```

When MCP is supported, state the preferred route and fallback order from `INTERFACES.md`; keep caller-visible MCP behavior in `MCP_INTERFACE.md` and exact runtime, SDK, transport, command, and deployment selections in `RUNTIME.md`.

When a human Web interface is supported, state whether it is available in the current environment and retain `WEB_INTERFACE.md`. Delete unused interface files from the concrete skill.

## Output requirements

Define the expected artifact, message, file changes, structured data, or side effects.

- TODO

## Validation

State how the agent determines that the workflow completed correctly.

- TODO

Validation should be proportional to risk. An instruction-only skill may require a short checklist; executable or service profiles may require automated tests.

## Safety and approval

State actions that are read-only, automatically allowed, mutating, destructive, externally visible, or approval-gated.

- TODO

Do not infer permission merely because a script, CLI, MCP tool, Web action, or service endpoint exists.

## Examples

Include a small number of representative inputs and expected outcomes when examples materially reduce ambiguity.

TODO

## Edge cases and failure handling

Document bounded recovery behavior, when to stop, and what must be reported rather than guessed.

- TODO

## Maintainer profile selection

Record the selected profiles on exactly one machine-readable line. Use comma-separated tags only when combining compatible non-`instruction-only` profiles.

Selected profiles: template-scaffold

Replace `template-scaffold` in every concrete skill with either `instruction-only` by itself or one or more compatible tags from:

- `instruction-only`;
- `knowledge-augmented`;
- `asset-driven`;
- `script-assisted`;
- `packaged-cli`;
- `mcp-enabled`;
- `browser-interface`;
- `headless-service`.

`instruction-only` is exclusive and must not be combined with resource, executable, or service profiles. Other compatible profile combinations retain the union of their requirements.

`template-scaffold` is reserved for this uncustomized template. Profiles are selectable patterns, not mandatory layers. `SKILL.md` is the only universally required skill file. Optional contracts and directories must be removed when they do not apply. See `docs/profile-contract-map.md` for profile-specific contract ownership.
