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
  ├─ instructions                   SKILL.md
  ├─ optional operational knowledge references/
  ├─ optional output resources      assets/
  ├─ optional executable helpers    scripts/
  └─ optional application interfaces
       ├─ packaged CLI               CLI_INTERFACE.md
       ├─ MCP                        MCP_INTERFACE.md
       └─ Web or service interface  WEB_INTERFACE.md / RUNTIME.md
```

`SKILL.md` is the only universally required skill file. A concrete skill may be complete with that file alone. Keep additional files only when they improve reliability, reuse, determinism, or maintainability.

## Skill profiles

Profiles are selectable design patterns, not mandatory product tiers. The `instruction-only` profile is exclusive; compatible non-`instruction-only` profiles may be combined.

| Profile | Typical contents | Use when |
|---|---|---|
| Instruction-only | `SKILL.md` | The agent can perform the workflow using its existing tools and knowledge |
| Knowledge-augmented | `SKILL.md`, `references/` | The workflow needs domain terminology, policies, schemas, or bounded procedures |
| Asset-driven | `SKILL.md`, `assets/` | The skill copies, fills, transforms, or emits templates and static resources |
| Script-assisted | `SKILL.md`, `scripts/`, optional tests/runtime record | Small deterministic helpers improve accuracy or repeatability |
| Packaged CLI | runtime files, `src/`, tests, `RUNTIME.md`, `INTERFACES.md`, `CLI_INTERFACE.md` | A stable human or automation command is a maintained public interface |
| MCP-enabled | application/runtime files, `INTERFACES.md`, `MCP_INTERFACE.md`, `mcp/` | Operations must be exposed through MCP hosts, endpoints, or bounded clients |
| Browser-interface | application profile, `RUNTIME.md`, `WEB_INTERFACE.md` | A browser-facing interface is intentional |
| Headless-service | application profile, `RUNTIME.md`, deployment/API material | An independently reachable non-browser service is intentional |

Every concrete skill records its selected tags on exactly one `Selected profiles:` line in `SKILL.md`. Select `instruction-only` alone. When the skill retains references, assets, scripts, runtime or interface contracts, or service behavior, omit `instruction-only` and select the applicable profiles; those compatible profiles retain the union of their requirements. The special `template-scaffold` value is valid only for the uncustomized template and cannot be retained after operational resources are added. Structural validation uses the tags to activate profile requirements.

See `docs/skill-profiles.md` for the allowed tags, selection rules, retention matrix, and removal rules. See `docs/profile-contract-map.md` for the source-of-truth boundary between contract files.

## Repository areas

- `SKILL.md`: operational instructions loaded by an agent and the machine-readable profile selection;
- `references/`: optional knowledge read only when the workflow requires it;
- `assets/`: optional static templates, examples, configuration skeletons, or output resources;
- `scripts/`: optional deterministic helpers or stable in-place launchers;
- `RUNTIME.md`: runtime, command, package, protocol-selection, service-lifecycle, and deployment authority when retained;
- `INTERFACES.md`: preferred public interface and deterministic fallback order for packaged CLI or MCP profiles;
- `CLI_INTERFACE.md`: caller-visible packaged CLI contract, retained only for `packaged-cli`;
- `MCP_INTERFACE.md`: caller-visible MCP contract, retained only for `mcp-enabled`;
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
4. Replace `Selected profiles: template-scaffold` with `instruction-only` alone or the smallest sufficient compatible non-`instruction-only` profile tags before adding operational resources.
5. Add `references/`, `assets/`, or `scripts/` only when they have a defined operational use.
6. Add and complete `RUNTIME.md` when runtime selection, dependencies, executable commands, packaging, or service lifecycle need a maintained record, and whenever `packaged-cli`, `mcp-enabled`, `browser-interface`, or `headless-service` is selected.
7. For `packaged-cli`, complete `INTERFACES.md` and `CLI_INTERFACE.md`.
8. For `mcp-enabled`, complete `INTERFACES.md`, `MCP_INTERFACE.md`, and the applicable MCP maintainer documentation.
9. Keep `WEB_INTERFACE.md` only when `browser-interface` is selected; a headless service alone does not require it.
10. Add only the manifests, lockfiles, source layout, and tests required by the selected implementation.
11. Replace `LICENSE.template` with the selected license and remove unused template guidance.

## Progressive disclosure

The agent should begin with `SKILL.md`. That file must say exactly when to read each reference, use each asset, or run each helper. Avoid making the agent load all supporting material preemptively.

The same principle applies to maintainers:

- instruction and resource changes should not require reading application-interface documents;
- helper-script changes require the script contract in `SKILL.md` and `RUNTIME.md` only when a separate runtime record exists;
- packaged CLI changes require `RUNTIME.md`, `INTERFACES.md`, and `CLI_INTERFACE.md`;
- MCP changes require `RUNTIME.md`, `INTERFACES.md`, `MCP_INTERFACE.md`, and applicable MCP transport material;
- browser-interface changes require `RUNTIME.md` and `WEB_INTERFACE.md`;
- headless-service changes require the completed `RUNTIME.md` service authority and applicable security, health, API, and deployment material.

## Helper scripts versus public CLIs

A helper script is not automatically a public CLI.

A helper may be narrow, agent-oriented, and documented directly in `SKILL.md`. It still needs a clear invocation, inputs, outputs, side effects, permissions, and failure behavior, but it does not need a public compatibility contract unless callers rely on one.

Select `packaged-cli` and complete `CLI_INTERFACE.md` when command names, structured output, exit codes, or backward compatibility are intentionally maintained for humans, agents, or CI. `INTERFACES.md` then records how an agent selects that CLI relative to any other maintained interface.

## Runtime neutrality

Runtime neutrality means delaying implementation choices until the workflow requires them. It does not mean adding every ecosystem as an alternative.

Do not add competing manifests or lockfiles for unused runtimes. A knowledge-only or instruction-only skill needs no runtime declaration. A script-assisted or application profile selects only the runtime and dependency workflow it actually uses.

## Optional application extensions

CLI, MCP, and Web interfaces remain advanced profiles. When several interfaces expose the same operations, keep adapters thin and share implementation where that separation provides real value. Do not impose an application/domain architecture on a small self-contained helper solely to match an advanced profile.

MCP exact revision, SDK, transport-selection, and startup decisions remain in `RUNTIME.md`; caller-visible negotiation, pagination, result preservation, interaction, cancellation, and transport behavior live in `MCP_INTERFACE.md`. Browser topology remains in `RUNTIME.md`, while browser-visible behavior lives in `WEB_INTERFACE.md`.

## Validation

Run the supported profile-aware validation entry point:

```sh
ruby .github/scripts/validate-profile-contracts.rb
```

The validator parses `SKILL.md` and each retained runtime or interface contract directly through the shared profile contract model. The committed documents remain separate sources of truth; no compatibility adapter, synthesized monolithic interface document, `File.read` monkey patch, or `RUBYOPT` injection is used.

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
