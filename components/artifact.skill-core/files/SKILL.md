---
name: agent-skill-template
description: Minimal scaffold for defining a portable Agent Skill. Use this template to specify an agent-triggered workflow, then add only the knowledge, assets, helper scripts, or composed application capabilities the concrete skill actually needs.
---

# Agent Skill Template

This repository is a scaffold, not an operational skill. Replace the guidance with the concrete trigger, workflow, outputs, and safety boundary. Remove sections that do not apply.

## Purpose

State the outcome this skill helps the agent produce.

TODO

## Use this skill when

Describe observable requests, repository states, file types, or workflow conditions that should trigger the skill.

- TODO

## Do not use this skill when

Record important exclusions and routes to other skills or normal agent behavior.

- TODO

## Required inputs and prerequisites

List only information, permissions, tools, files, runtimes, or network access the workflow actually requires.

- TODO

An instruction-only or knowledge-only skill may require no implementation runtime.

## Workflow

Write the shortest reliable sequence the agent should follow.

1. TODO
2. TODO
3. Validate the result against the output and safety requirements below.

Prefer explicit decision points over vague instructions.

## Operational knowledge

Add `references/` only when the workflow depends on maintained operational knowledge. For every retained reference, declare its trigger and authority here.

```text
Reference: references/TODO.md
Read when: TODO
Provides: TODO
Authority or freshness notes: TODO
```

Delete this section when no reference is required.

## Assets

Add `assets/` only when the workflow copies, fills, transforms, compares, or emits static resources.

```text
Asset: assets/TODO
Use when: TODO
Handling: copy / fill / transform / attach / compare: TODO
Must remain unchanged: TODO
```

Delete this section when no asset is required.

## Helper scripts

A helper script is private to the skill unless a public capability contract says otherwise. For every retained helper, document a bounded execution contract.

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

Delete this section when no helper is required.

## Public execution interfaces

Application interfaces are composition capabilities, not Skill profiles. The resolved composition lock is the machine authority for which capabilities were materialized.

When one or more public interfaces exist, record the agent-facing route here:

```text
Preferred agent interface: TODO or NOT APPLICABLE
Fallback order: TODO or NONE
Availability/fallback conditions: TODO or NOT APPLICABLE
```

Detailed behavior remains in the materialized capability contract:

- `CLI_INTERFACE.md` for `capability.cli`;
- `MCP_INTERFACE.md` for `capability.mcp`;
- `MCP_APPS.md` for `capability.mcp-apps`;
- `WEB_INTERFACE.md` for `capability.web-interface`;
- `SERVICE_INTERFACE.md` for `capability.service`;
- `RUNTIME.md` for `capability.runtime`.

An MCP App enriches an MCP route; it is not a separate agent route. A standalone browser interface is never an implicit agent fallback.

Fallback must not silently weaken authentication, authorization, confirmation, workspace, or write restrictions. Distinguish interface unavailability from a negative domain result.

## Output requirements

Define the expected artifact, message, file changes, structured data, or side effects.

- TODO

## Validation

State how the agent determines that the workflow completed correctly.

- TODO

Validation should be proportional to risk.

## Safety and approval

State actions that are read-only, automatically allowed, mutating, destructive, externally visible, or approval-gated.

- TODO

Do not infer permission merely because a script, CLI, MCP tool, browser action, or service endpoint exists.

## Examples

Include a small number of representative inputs and expected outcomes when they materially reduce ambiguity.

TODO

## Edge cases and failure handling

Document bounded recovery behavior, when to stop, and what must be reported rather than guessed.

- TODO

## Skill profile selection

Skill profiles describe Skill-specific resource structure only. Record exactly one machine-readable line:

Selected profiles: template-scaffold

For a concrete skill, replace `template-scaffold` with either `instruction-only` by itself or one or more compatible tags from:

- `instruction-only`;
- `knowledge-augmented`;
- `asset-driven`;
- `script-assisted`.

`instruction-only` is exclusive. The other profiles may be combined.

Do not put `packaged-cli`, `mcp-enabled`, `browser-interface`, or `headless-service` on this line. Those former Skill profile tags are now composition capabilities selected by the recipe/configuration and recorded in the composition lock.

`template-scaffold` is reserved for this uncustomized template. `SKILL.md` is the only universal Skill semantic file. Create `references/`, `assets/`, or `scripts/` only when their corresponding profile is selected.
