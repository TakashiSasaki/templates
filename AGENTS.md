# Repository instructions

## Repository identity

The repository root is the Agent Skill root. It must remain suitable for installation directly at:

```text
.agents/skills/<skill-name>/
```

Do not add an additional enclosing `skill/` directory.

## Required reading

Before changing implementation or packaging, read:

- `RUNTIME.md`
- `INTERFACES.md`
- `docs/architecture.md`
- `docs/runtime-selection.md`

## Runtime policy

This template is intentionally language-neutral.

- Do not assume Python or Node.js.
- Do not assume uv, pip, npm, pnpm, yarn, or bun.
- Do not add manifests or lockfiles for runtimes that are not selected.
- A concrete skill must record one primary runtime and its exact commands in `RUNTIME.md`.
- Supporting a second runtime requires a documented reason and tests proving equivalent behavior.

## Architecture

Separate these concerns:

1. `SKILL.md`: when and how an agent should use the skill.
2. CLI adapter: human terminal interface and optional agent launcher.
3. MCP adapter: optional protocol interface.
4. Application/domain implementation: reusable behavior.
5. Tests: contract, adapter, integration, and security verification.

CLI and MCP adapters must call the same application logic. Do not duplicate domain behavior in adapters.

## Interface policy

`INTERFACES.md` is the contract index. It must state:

- the canonical human CLI command;
- the canonical in-place agent command, if different;
- the stdio MCP server launch command, if MCP is supported;
- the ad hoc MCP client command, if supported;
- the preferred agent interface and deterministic fallback order;
- output formats and exit-code meanings.

An agent must not be left to choose arbitrarily between equivalent execution paths.

## stdio MCP requirements

When an stdio MCP server exists:

- stdout is reserved for MCP protocol traffic;
- diagnostics and logs go to stderr;
- startup performs no expensive repository-wide scan;
- the process exits when stdin closes;
- paths are resolved and constrained to the allowed workspace;
- tools expose narrow domain operations, not arbitrary shell execution.

## Completion criteria

Before reporting a change complete:

1. Update `SKILL.md` when operational behavior changes.
2. Update `RUNTIME.md` when commands, runtimes, or package managers change.
3. Update `INTERFACES.md` when CLI or MCP contracts change.
4. Run the selected runtime's tests and static checks.
5. Verify CLI and MCP semantic equivalence when both exist.
6. Confirm generated files and lockfiles correspond only to selected tooling.
7. Review the final repository as if it were cloned directly into `.agents/skills/<skill-name>/`.
