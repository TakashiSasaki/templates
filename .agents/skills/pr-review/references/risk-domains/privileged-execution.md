<!--
agent-policy-generated: true
source-skill: pr-review
DO NOT EDIT DIRECTLY
-->
# Privileged execution

This is a **provider-neutral procedure-support reference** for `pr-review`. It generates and falsifies candidates only; semantic security/correctness policy decides whether a condition is a finding.

## Trigger

Use this domain when untrusted or change-controlled inputs, environment, configuration, artifacts, hooks, plugins, commands, templates, interpreters, or runtime selection can influence behavior executed with meaningful privilege or trust.

## State and authority model

Model the source of executable influence, validation/allowlisting boundaries, transformation steps, selected runtime or execution context, inherited authority, and the final sink. Distinguish data from instructions and caller-controlled selection from trusted policy-owned selection.

## Candidate seeds

Generate candidates when:

- data can cross into an executable or privileged interpretation without a controlling validation boundary;
- a caller can select a runtime, command, plugin, hook, template, or configuration outside the intended authority set;
- environment or search-path state can redirect execution to a different effective artifact;
- lower-trust generated or downloaded content is executed before provenance/integrity validation;
- quoting/encoding/parsing boundaries allow one component to reinterpret data as control syntax;
- fallback behavior silently increases privilege or broadens the execution target.

A seed is not a finding.

## Falsification evidence

Trace the exact execution path and controlling actors. Look for structured APIs, allowlists, capability restrictions, immutable runtime identity, verified provenance, privilege separation, sandboxing, encoding boundaries, and earlier rejection layers. Discard candidates that cannot influence executable semantics or cannot cross the relevant trust boundary.

## Closure

Close this domain only after the reviewer can identify the exact bytes/state that determine privileged behavior, who can control them, and which validated boundary prevents unintended instruction or authority injection.