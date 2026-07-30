# Language-neutral Agent Skill Template

This repository is a template for developing a portable Agent Skill whose repository root is intended to become the skill directory itself.

Typical installation target:

```text
<project>/.agents/skills/<skill-name>/
```

The template starts from the smallest valid skill and adds implementation or service concerns only when the skill actually needs them. It deliberately does **not** require a programming runtime, package manager, CLI, MCP server, or Web interface.

## Core principle

An Agent Skill is first an instruction and resource package for an agent:

```text
Agent Skill
  ├─ instructions                  SKILL.md
  ├─ optional operational knowledge references/
  ├─ optional output resources     assets/
  ├─ optional executable helpers   scripts/
  └─ optional application interfaces
       ├─ packaged CLI
       ├─ MCP
       └─ Web or service interface
```

`SKILL.md` is the only universally required skill file. A concrete skill may be complete with that file alone. Keep additional files only when they improve reliability, reuse, determinism, or maintainability.

## Skill profiles

Profiles are cumulative design patterns, not mandatory product tiers.

| Profile | Typical contents | Use when |
|---|---|---|
| Instruction-only | `SKILL.md` | The agent can perform the workflow using its existing tools and knowledge |
| Knowledge-augmented | `SKILL.md`, `references/` | The workflow needs domain terminology, policies, schemas, or bounded procedures |
| Asset-driven | `SKILL.md`, `assets/` | The skill copies, fills, transforms, or emits templates and static resources |
| Script-assisted | `SKILL.md`, `scripts/`, optional tests/runtime record | Small deterministic helpers improve accuracy or repeatability |
| Packaged CLI | runtime files, `src/`, tests, `RUNTIME.md`, `INTERFACES.md` | A stable human or automation command is a maintained public interface |
| MCP-enabled | CLI/application profile plus `mcp/` and MCP contract documentation | The skill must expose operations through MCP hosts or clients |
| Web/service-enabled | application profile plus deployment decisions; `WEB_INTERFACE.md` only for browser-facing behavior | A browser or independently reachable network service is an intentional interface |

See `docs/skill-profiles.md` for selection and removal rules.

## Repository areas

- `SKILL.md`: operational instructions loaded by an agent;
- `references/`: optional knowledge read only when the workflow requires it;
- `assets/`: optional static templates, examples, configuration skeletons, or output resources;
- `scripts/`: optional deterministic helpers or stable in-place launchers;
- `RUNTIME.md`: optional runtime and command decision record for implemented software;
- `INTERFACES.md`: required public contract for a packaged CLI or MCP interface, otherwise optional;
- `WEB_INTERFACE.md`: optional browser-facing contract, not a generic headless-service contract;
- `mcp/`: optional MCP adapters and bounded MCP clients;
- `src/`: optional application implementation;
- `tests/`: tests appropriate to the selected profile and risk;
- `docs/`: maintainer material not normally loaded during skill execution;
- `AGENTS.md`: contributor rules for agents modifying this repository.

A concrete skill should delete unused optional files and directories. Keeping a placeholder contract for an unsupported interface increases context and maintenance cost.

## Creating a concrete skill

1. Create a repository from this template.
2. Choose the final lowercase hyphenated skill name.
3. Rewrite `SKILL.md` around the actual trigger, workflow, resources, outputs, and safety constraints.
4. Select the smallest profile that fully supports the workflow.
5. Add `references/`, `assets/`, or `scripts/` only when they have a defined operational use.
6. Add `RUNTIME.md` only when runtime selection, dependency installation, or executable commands need a maintained record.
7. Add and complete `INTERFACES.md` whenever a packaged CLI or MCP interface is maintained; private helper scripts do not require it.
8. Keep MCP files only when MCP is supported, and keep `WEB_INTERFACE.md` only when a browser-facing interface is supported.
9. Add only the manifests, lockfiles, source layout, and tests required by the selected implementation.
10. Replace `LICENSE.template` with the selected license and remove unused template guidance.

## Progressive disclosure

The agent should begin with `SKILL.md`. That file must say exactly when to read each reference, use each asset, or run each helper. Avoid making the agent load all supporting material preemptively.

The same principle applies to maintainers:

- instruction and resource changes should not require reading MCP or Web documents;
- script changes require the applicable runtime and script contracts;
- MCP changes require the MCP contract and transport documents;
- browser-interface changes require the Web and deployment documents;
- headless-service changes require runtime, service, security, health, and deployment documentation, but not `WEB_INTERFACE.md` unless a browser surface also exists.

## Helper scripts versus public CLIs

A helper script is not automatically a public CLI.

A helper may be narrow, agent-oriented, and documented directly in `SKILL.md`. It still needs a clear invocation, inputs, outputs, side effects, permissions, and failure behavior, but it does not need a large compatibility contract unless callers rely on one.

Create a packaged CLI and complete `INTERFACES.md` when command names, structured output, exit codes, or backward compatibility are intentionally maintained for humans, agents, or CI.

## Runtime neutrality

Runtime neutrality means delaying implementation choices until the workflow requires them. It does not mean adding every ecosystem as an alternative.

Do not add competing manifests or lockfiles for unused runtimes. A knowledge-only or instruction-only skill needs no runtime declaration. A script-assisted or application profile selects only the runtime and dependency workflow it actually uses.

## Optional application extensions

CLI, MCP, and Web interfaces remain supported as advanced profiles. When several interfaces expose the same operations, keep adapters thin and share implementation where that separation provides real value. Do not impose an application/domain architecture on a small self-contained helper solely to match the advanced profile.

MCP-specific revision, transport, pagination, result-preservation, and HTTP-security guidance remains in `RUNTIME.md`, `INTERFACES.md`, `docs/mcp-transports.md`, and `mcp/README.md`. Browser topology and browser-facing behavior remain in `RUNTIME.md` and `WEB_INTERFACE.md`. A headless network service records its runtime, endpoint, security, lifecycle, health, and deployment decisions without retaining a browser-only contract.

## Installation modes

Clone as a user-level skill:

```sh
git clone <repository-url> ~/.agents/skills/<skill-name>
```

Track as a project-level submodule:

```sh
git submodule add <repository-url> .agents/skills/<skill-name>
```

Vendoring a release archive into `.agents/skills/<skill-name>/` is also valid when the parent repository should own the files directly.
