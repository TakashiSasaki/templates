# Coding-agent bootstrap contract

This contract defines how an external coding agent can acquire the Composition consumer Skill without cloning `TakashiSasaki/templates` and without depending on a particular transport command.

It is a consumer bootstrap contract. It does not govern agents maintaining the `composition` authority itself; repository-maintenance routing remains in the root `AGENTS.md`.

## Goal

A user should be able to direct a coding agent to use Composition for either a new project or an existing project. The agent may choose any available HTTPS and filesystem mechanism appropriate to its environment. Composition does not require `curl`, `wget`, PowerShell, Git, GitHub CLI, or a templates checkout merely to transport bootstrap resources.

Bootstrap ends when the Composition Skill has been materialized at a caller-selected local destination and control has been handed to that installed `SKILL.md`. Project inspection, initial composition, managed update, upgrade, recovery, and validation remain responsibilities of the installed Skill and Composer.

## Trust and mutability model

Bootstrap separates discovery from executable content.

1. A stable mutable discovery document identifies the currently recommended immutable Skill distribution.
2. The discovery document MUST identify the distribution with a full 40-character lowercase Git commit SHA.
3. The immutable installation manifest and every repository resource it names MUST be resolved from that exact revision, never from a moving branch or tag.
4. A consumer MUST fail closed when a revision, path, digest, or manifest invariant cannot be verified.

The mutable discovery document is routing metadata, not executable authority. Updating it changes which immutable distribution is recommended to new consumers; it does not mutate an already installed Skill or an already managed consumer repository.

## Transport independence

The contract specifies resources and resulting bytes, not commands used to retrieve them. A coding agent MAY use a native HTTP facility, a GitHub integration, Python, PowerShell, `curl`, `wget`, or another mechanism that can retrieve the required immutable HTTPS resources without changing their bytes.

A bootstrap instruction MUST NOT claim that one transport program is required unless that program is itself part of the declared installed runtime contract. The reference human installer may have stronger runtime prerequisites than direct agent materialization.

## Canonical materialization model

The immutable installation manifest is the canonical description of the distributable Skill tree. Given one valid manifest and its pinned repository revision, materialization MUST have one deterministic result for the files governed by that manifest.

Each file entry identifies:

- a repository-relative source path;
- a destination path relative to the selected Skill installation root; and
- a SHA-256 digest of the exact file bytes.

Materializers MUST reject absolute destinations, `.` or `..` path segments, platform-unsafe destinations, duplicate destinations, portable case-fold collisions, unsupported entry types, digest mismatches, missing required entrypoints, and resources that resolve outside the pinned repository revision.

The manifest MUST reserve installation metadata paths that are written by a materializer rather than supplied as distributable Skill content.

## Reference installer and direct agent materialization

The Python remote installer is the reference materializer for human and agent environments that have a supported Python runtime. Its installation semantics MUST be derived from the same immutable installation manifest rather than from an independently maintained file inventory.

A coding agent MAY instead interpret the manifest directly when it can safely retrieve, verify, and write the declared files. Direct materialization and the reference installer MUST produce equivalent governed Skill bytes and equivalent source provenance for the same manifest revision.

An implementation may use an archive as a transport optimization. Archive membership is not installation authority: the manifest remains authoritative for the files that may be installed and their expected digests.

## Installed provenance

A completed installation records at least:

- the source repository identity; and
- the full immutable revision from which the Skill distribution was materialized.

The installed Skill's existing provenance command may expose this information. Materializers MUST NOT guess a source revision for an unrecorded development copy.

## Handoff

After successful materialization, the coding agent MUST read the installed Composition `SKILL.md` and use it as the repository-facing operational entry point. Remote bootstrap instructions MUST NOT duplicate Composer lifecycle semantics or become a second authority for `inspect`, `plan`, `apply`, `validate`, update, upgrade, or recovery behavior.

The installed Skill determines the target repository state before mutation. The remote bootstrap path therefore remains the same for an empty/new project, an existing unmanaged project, and an already managed project.

## Required validation properties

Composition CI MUST eventually make the following properties executable regressions rather than documentation-only assumptions:

- discovery documents conform to their schema and pin a full SHA;
- immutable manifests conform to their schema;
- every manifest source exists at the pinned revision and matches its digest;
- destination safety and collision checks fail closed;
- required installed entrypoints are present;
- reinstall/replace behavior is deterministic;
- reference-installer and direct-manifest materialization are equivalent for governed files; and
- bootstrap instructions contain no mandatory transport-tool dependency.

## Non-goals

This contract does not define a general package manager, dependency solver, Skill registry, shell abstraction, or vendor-specific remote-Skill protocol. It does not require coding agents to support a particular Agent Skill discovery standard. The interoperability baseline is intentionally smaller: retrieve a stable public bootstrap entry point, resolve an immutable manifest, verify bytes, materialize files, and hand control to the installed Skill.
