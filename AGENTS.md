# Repository instructions

## Repository identity

The repository root is the Agent Skill root. It must remain suitable for installation directly at:

```text
.agents/skills/<skill-name>/
```

Do not add an additional enclosing `skill/` directory.

## Core rule

Treat `SKILL.md` as the operational center of the repository. A concrete skill may be complete with `SKILL.md` alone. Do not require a programming runtime, CLI, MCP server, Web interface, or application-layer architecture unless the workflow needs it.

Select the smallest sufficient profile described in `docs/skill-profiles.md`. Delete unsupported optional contracts and directories rather than leaving large placeholder documents in a concrete skill.

## Progressive maintainer reading

Always read:

- `SKILL.md`;
- files directly named by the current task.

Read additional material only when applicable:

- knowledge or procedure changes: the affected files under `references/`;
- asset changes: the affected files under `assets/` and their usage instructions in `SKILL.md`;
- helper-script changes: the affected scripts, their execution contracts in `SKILL.md`, and `RUNTIME.md` when a runtime record exists;
- packaged CLI changes: `RUNTIME.md` and `INTERFACES.md`;
- MCP changes: `RUNTIME.md`, `INTERFACES.md`, `docs/mcp-transports.md`, and `mcp/README.md`;
- browser-interface changes: `RUNTIME.md`, `WEB_INTERFACE.md`, and applicable architecture/deployment documentation;
- headless-service changes: the authoritative runtime/service record and applicable security, health, lifecycle, and deployment documentation;
- repository-wide architecture or packaging changes: the applicable files under `docs/`.

Do not load MCP or browser-interface documentation merely because it exists in the template.

## Skill resources

Every retained operational resource under `references/`, `assets/`, or `scripts/` must:

- be a regular file contained within the installable skill;
- be declared by its exact repository-relative path in the corresponding `Reference:`, `Asset:`, or `Script:` entry in `SKILL.md`;
- have its trigger, purpose, handling, or execution contract documented with that entry.

Do not use symlinks under these directories. Symlinked resources can escape the skill root, become broken after cloning or vendoring, and make validation environment-dependent.

### Operational references

Keep runtime knowledge under `references/` only when the agent may need it while performing the skill.

- `SKILL.md` must state when each reference should be read and what it provides.
- Prefer bounded, task-specific references over general documentation dumps.
- Record authority, version, provenance, or freshness requirements when stale knowledge could change the result.
- Avoid deep chains of references.

### Assets

Use `assets/` for static resources consumed or emitted by the workflow.

- `SKILL.md` must contain the exact `Asset:` declaration and state when and how each retained asset is used.
- A directly linked reference may add detail but does not replace the declaration or trigger in `SKILL.md`.
- Do not treat an asset as an instruction source unless the skill explicitly says to read it as one.
- Preserve immutable template regions and licenses where applicable.

### Helper scripts

Use `scripts/` for small deterministic helpers or stable in-place launchers.

- A helper script is not automatically a public CLI.
- `SKILL.md` must contain the exact `Script:` declaration and the bounded execution trigger for every retained script.
- A directly linked operational reference may add invocation or failure detail but does not replace the declaration in `SKILL.md`.
- Resolve the skill root from the script location when possible; do not assume the caller's current directory.
- Do not install runtimes or package managers silently.
- Preserve delegated exit status and emit actionable diagnostics.
- A small helper may remain self-contained. Do not force adapter/domain layering onto trivial code.

## Runtime policy

This template is language-neutral.

- Instruction-only, knowledge-augmented, and asset-driven skills need no runtime selection.
- Select a runtime only when scripts or maintained application code require one.
- Do not add manifests or lockfiles for unused runtimes.
- When `RUNTIME.md` is retained, it is the source of truth for runtime, dependency, command, transport, and deployment selections that apply to the chosen profile.
- Supporting a second runtime requires a documented reason and proportionate equivalence tests.

## Public interfaces

Direct helper invocation may be documented entirely in `SKILL.md`.

Retain and complete `INTERFACES.md` whenever the skill maintains a packaged CLI or MCP contract, including command compatibility, structured output, exit codes, negotiation, or fallback behavior.

Retain and complete `WEB_INTERFACE.md` only when a browser-facing interface is supported. A headless network service does not retain that browser-only contract unless it also exposes a browser surface.

Do not describe a local helper command as a public CLI or protocol method unless that compatibility contract is intentional.

## Optional application architecture

Use a shared application/domain implementation with thin adapters when multiple maintained interfaces expose the same behavior or when complexity and testing justify the separation.

When applicable:

1. CLI, MCP, and Web adapters remain separate from domain behavior.
2. stdio and Streamable HTTP MCP adapters share tool definitions.
3. MCP clients traverse an actual MCP adapter rather than bypassing the protocol.
4. A Web path claiming MCP verification traverses the MCP client, protocol, transport, and server adapter.
5. A deliberately non-MCP Web API may call the application layer directly but must not be described as MCP verification.

These rules do not require a small one-purpose helper script to be decomposed into application and domain layers.

## MCP-specific requirements

Apply this section only when MCP is supported.

- Verify the current official specification and selected SDK before implementation.
- Record exact revisions, compatibility, schema, transport, and command decisions in `RUNTIME.md`.
- Reserve stdout for stdio protocol traffic and send diagnostics to stderr.
- Use Streamable HTTP rather than describing a normal HTTP server as raw TCP MCP.
- Keep Host, Origin, authentication, authorization, size-limit, and protocol-header decisions request-scoped.
- Validate Origin on every HTTP request before dispatch and do not reuse an allow decision across connection reuse or multiplexing.
- Preserve the complete protocol result where a lossless mode is claimed.
- Preserve each paginated `tools/list` page separately from any flattened presentation.
- Test every claimed revision, fallback, interaction model, cancellation path, and transport exposure.

## Web-specific requirements

Apply this section only when a browser-facing interface is supported.

- Record deployment topology and exposure capabilities in `RUNTIME.md`.
- Record browser-visible behavior, security, operation policy, redaction, health semantics, and failure behavior in `WEB_INTERFACE.md`.
- Keep the Web interface optional and normally disabled when it is only for debugging.
- Do not equate Web readiness with MCP readiness.
- A separate process, port, or container is optional; logical security and lifecycle boundaries are not.

## Validation proportionality

Validation must match the selected profile and risk.

- instruction-only: frontmatter, trigger clarity, workflow completeness, output and safety checks;
- knowledge or asset profiles: resource existence, exact linkage, provenance/freshness where applicable;
- script-assisted: helper contract tests, failure behavior, side effects, permissions, and representative execution;
- packaged CLI: stable command, structured output, exit codes, compatibility, and installation tests;
- MCP: protocol, transport, pagination, result preservation, cancellation, security, and compatibility tests;
- Web/service: routing, authentication, authorization, health separation, exposure, and deployment smoke tests.

Do not require service-grade tests from an instruction-only skill, and do not under-test executable or networked profiles.

## Completion criteria

Before reporting a change complete:

1. Update `SKILL.md` whenever operational behavior, resource usage, helper invocation, outputs, or safety changes.
2. Update only the optional contracts applicable to the selected profile.
3. Remove files and directories that no longer serve an operational or maintainer purpose.
4. Run the validation and tests appropriate to the selected profile.
5. Confirm that references, assets, and scripts are declared by exact path and reachable through explicit instructions rather than accidental discovery.
6. Confirm that operational resource directories contain no symlinks.
7. Confirm that no secrets or environment-specific credentials are committed.
8. Review the result as if the repository were cloned directly into `.agents/skills/<skill-name>/`.
