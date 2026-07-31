# Repository instructions

## Repository identity

The repository root is the Agent Skill root. It must remain suitable for installation directly at:

```text
.agents/skills/<skill-name>/
```

Do not add an additional enclosing `skill/` directory.

## Core rule

Treat `SKILL.md` as the operational center of the repository. A concrete skill may be complete with `SKILL.md` alone. Do not require a programming runtime, CLI, MCP server, Web interface, or application-layer architecture unless the workflow needs it.

Select the smallest sufficient profile described in `docs/skill-profiles.md`. Every `SKILL.md` must contain exactly one `Selected profiles:` line using the documented machine-readable tags. The `template-scaffold` value is reserved for the uncustomized `agent-skill-template`; replace it before adding operational resources, implementation, runtime manifests, or interface contracts.

Delete unsupported optional contracts and directories rather than leaving large placeholder documents in a concrete skill. Use `docs/profile-contract-map.md` to identify the source of truth for each decision.

## Progressive maintainer reading

Always read:

- `SKILL.md`;
- files directly named by the current task.

Read additional material only when applicable:

- knowledge or procedure changes: the affected files under `references/`;
- asset changes: the affected files under `assets/` and their usage instructions in `SKILL.md`;
- helper-script changes: the affected scripts, their execution contracts in `SKILL.md`, and `RUNTIME.md` only when a separate runtime record exists;
- packaged CLI changes: `RUNTIME.md`, `INTERFACES.md`, and `CLI_INTERFACE.md`;
- MCP changes: `RUNTIME.md`, `INTERFACES.md`, `MCP_INTERFACE.md`, `docs/mcp-transports.md`, and `mcp/README.md`;
- browser-interface changes: `RUNTIME.md`, `WEB_INTERFACE.md`, and applicable architecture/deployment documentation;
- headless-service changes: completed `RUNTIME.md` plus applicable API, security, health, lifecycle, and deployment configuration;
- repository-wide architecture or packaging changes: the applicable files under `docs/`.

Do not load MCP or browser-interface documentation merely because it exists in the template.

## Skill resources

Every retained operational resource under `references/`, `assets/`, or `scripts/` must:

- be a regular file contained within the installable skill;
- be declared by its exact repository-relative path in the corresponding `Reference:`, `Asset:`, or `Script:` entry in `SKILL.md`;
- have its trigger, purpose, handling, or execution contract documented with that entry.

Do not use symlinks or Git submodules/gitlinks under these directories. External links can escape the skill root, become absent after cloning or vendoring, and make validation environment-dependent.

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
- `SKILL.md` must contain the exact `Script:` declaration and bounded execution trigger for every retained script.
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
- `RUNTIME.md` is required and must be completed when `packaged-cli`, `mcp-enabled`, `browser-interface`, or `headless-service` is selected.
- `RUNTIME.md` is authoritative for runtime identity, dependencies, exact commands, packaging, distribution, exact MCP selections, service lifecycle, and deployment topology.
- Caller-visible CLI behavior belongs in `CLI_INTERFACE.md`; caller-visible MCP behavior belongs in `MCP_INTERFACE.md`; browser-visible behavior belongs in `WEB_INTERFACE.md`.
- Supporting a second runtime requires a documented reason and proportionate equivalence tests.

## Public interfaces

Direct helper invocation may be documented entirely in `SKILL.md`.

- `INTERFACES.md` records the preferred agent interface and deterministic fallback order when `packaged-cli` or `mcp-enabled` is selected.
- `CLI_INTERFACE.md` is required only for `packaged-cli` and records the canonical command, working directory, structured output, diagnostics, exit codes, side effects, compatibility, and versioning.
- `MCP_INTERFACE.md` is required only for `mcp-enabled` and records caller-visible negotiation, transport behavior, pagination, lossless results, interaction, cancellation, compatibility, and test invariants.
- `WEB_INTERFACE.md` is retained only for a browser-facing interface. A headless network service does not retain that browser-only contract unless it also exposes a browser surface.

Do not duplicate a profile-specific public contract in `INTERFACES.md`. Do not describe a local helper command as a public CLI or protocol method unless that compatibility contract is intentional.

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
- Record exact revisions, SDK, schema dialects, entry points, bind, command, and distribution selections in `RUNTIME.md`.
- Record caller-visible negotiation, fallback, pagination, result preservation, interaction, cancellation, and compatibility in `MCP_INTERFACE.md`.
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
- browser-interface: routing, authentication, authorization, health separation, browser exposure, and deployment smoke tests;
- headless-service: endpoint, authentication, authorization, health, lifecycle, shutdown, exposure, and deployment smoke tests.

Do not require service-grade tests from an instruction-only skill, and do not under-test executable or networked profiles.

During the Phase 2 document transition, run:

```sh
ruby .github/scripts/validate-profile-contracts.rb
```

The compatibility adapter assembles split interface files only in memory for legacy validators. Do not reintroduce duplicated committed contracts to satisfy those parsers.

## Completion criteria

Before reporting a change complete:

1. Update `SKILL.md` whenever operational behavior, resource usage, helper invocation, outputs, safety, or selected profiles change.
2. Confirm that the single `Selected profiles:` line matches the implemented interfaces and resources, and that `template-scaffold` has been removed before customization.
3. Update only the optional contracts applicable to the selected profile.
4. Remove files and directories that no longer serve an operational or maintainer purpose.
5. Run the validation and tests appropriate to the selected profile.
6. Confirm that references, assets, and scripts are declared by exact path and reachable through explicit instructions rather than accidental discovery.
7. Confirm that operational resource directories contain no symlinks or gitlinks.
8. Confirm that selected application and service profiles have completed contract status and required fields.
9. Confirm that no secrets or environment-specific credentials are committed.
10. Review the result as if the repository were cloned directly into `.agents/skills/<skill-name>/`.
