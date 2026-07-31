# Helper scripts and stable launchers

This directory is optional in a concrete skill.

Use it for small deterministic helpers, validators, converters, generators, or stable in-place launchers that the skill invokes directly. A helper script is not automatically a packaged public CLI and does not automatically require `INTERFACES.md` or `CLI_INTERFACE.md`.

Every retained script must have an exact `Script: scripts/...` declaration in `SKILL.md`. That declaration must state when the agent may run the script and the bounded execution contract. A directly linked operational reference may provide supplemental detail, but it must not replace the declaration in `SKILL.md`.

For every retained script, document:

- when the agent should run it;
- the exact invocation and working directory;
- arguments, stdin, files, and environment inputs;
- stdout or generated-result expectations;
- stderr and diagnostic behavior;
- exit-status meanings when nontrivial;
- files, repositories, services, or external state it may modify;
- network access and required permissions;
- whether automatic execution is allowed;
- whether human confirmation is required;
- idempotency, retry, timeout, and partial-failure behavior where relevant.

Implementation rules:

- locate the skill root from the script location rather than assuming the caller's current directory;
- do not install runtimes, package managers, or dependencies silently;
- fail with an actionable diagnostic when prerequisites are missing;
- avoid exposing secrets through arguments, output, logs, or committed configuration;
- preserve delegated exit status when acting as a launcher;
- keep side effects narrow and explicit;
- add tests proportional to the script's risk and complexity.

A short one-purpose helper may remain self-contained. Delegate to reusable implementation code when several scripts or public adapters share substantial behavior, not merely to satisfy an architectural pattern.

Use `RUNTIME.md` when runtime, dependency, installation, distribution, or shared command decisions need a maintained authority. Select `packaged-cli` and retain `INTERFACES.md` plus `CLI_INTERFACE.md` only when command compatibility, structured output, stable exit codes, or other caller-visible guarantees are intentionally maintained.

Delete this directory if the concrete skill has no helper scripts or in-place launchers.
