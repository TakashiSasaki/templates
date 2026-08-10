# Language-neutral Agent Skill Template

This repository is a template for developing a portable Agent Skill. Its root is intended to become the installable Skill directory directly:

```text
<project>/.agents/skills/<skill-name>/
```

`SKILL.md` is the only universally required operational file. Keep references, assets, scripts, runtime records, public interfaces, extension contracts, implementation, tests, and service material only when the selected Skill actually needs them.

## Start a concrete Skill

1. Copy the complete template contents into an empty destination so `SKILL.md` is directly under the destination root.
2. Choose a final lowercase hyphenated Skill name and replace the template frontmatter in `SKILL.md`.
3. Rewrite the trigger, exclusions, prerequisites, workflow, outputs, validation, safety rules, and failure behavior around the real task.
4. Replace `Selected profiles: template-scaffold` with `instruction-only` alone or the smallest sufficient compatible profile tags.
5. Add or complete only the resources, runtime, implementation, interfaces, extension contracts, and tests required by those profiles and selected capabilities.
6. Delete every unsupported optional contract and directory rather than retaining placeholder material.
7. Choose the concrete Skill license. Keep `LICENSE` to use MIT-0 or replace it, then remove `LICENSE.template`.
8. Run the included validation before treating the Skill as complete.

Do not retain `template-scaffold` after adding operational resources, executable implementation, runtime manifests, or public interfaces.

## Repository policy is optional

This copyable template is not pre-enrolled in the shared `agent-policy` toolchain. The included `AGENTS.md` describes how to develop and validate the Skill artifact; it is part of this template's artifact-development contract rather than inherited source-maintainer policy.

After copying, the owner of the concrete Skill repository may adopt a shared repository-policy toolchain separately if that operating model is desired. Treat that as an explicit repository-maintenance decision: use a reviewed immutable toolchain revision, preserve the concrete Skill requirements already expressed by this template and its customization, and do not treat policy adoption as part of the copy operation itself.

## Profiles

Profiles are selectable contract patterns, not maturity levels.

| Profile | Typical retained contents | Use when |
|---|---|---|
| `instruction-only` | `SKILL.md` | Existing agent tools and knowledge are sufficient |
| `knowledge-augmented` | `SKILL.md`, declared `references/` | The workflow needs bounded domain knowledge, policy, schemas, or procedures |
| `asset-driven` | `SKILL.md`, declared `assets/` | The workflow consumes or emits static templates and resources |
| `script-assisted` | `SKILL.md`, declared `scripts/`, optional tests and `RUNTIME.md` | A private deterministic helper improves reliability |
| `packaged-cli` | `RUNTIME.md`, `INTERFACES.md`, `CLI_INTERFACE.md`, implementation and tests | A stable command is a maintained public interface |
| `mcp-enabled` | `RUNTIME.md`, `INTERFACES.md`, `MCP_INTERFACE.md`, applicable `mcp/` and tests | Operations are exposed through MCP |
| `browser-interface` | `RUNTIME.md`, `WEB_INTERFACE.md`, implementation and tests | A standalone browser-facing interface is intentional |
| `headless-service` | `RUNTIME.md`, applicable API/deployment material, implementation and tests | An independently reachable non-browser service is intentional |

`instruction-only` is exclusive. Compatible non-`instruction-only` profiles may be combined, and a combination retains the union of their required contracts. A service-enabled Skill may still use knowledge, assets, or helper scripts.

MCP extensions are selected inside the `mcp-enabled` profile rather than becoming additional profile tags. The initial template uses MCP core `2026-07-28`. When `RUNTIME.md` selects `io.modelcontextprotocol/ui`, retain and complete `MCP_APPS.md`; that contract records the independent MCP Apps revision and Host-embedded UI behavior. MCP Apps alone does not select `browser-interface`.

See `docs/skill-profiles.md` for selection, extension activation, retention, removal, and validation rules. See `docs/profile-contract-map.md` for contract ownership.

## Contract ownership

- `SKILL.md`: trigger, workflow, resources, helper invocation, outputs, validation, safety, and selected profiles.
- `RUNTIME.md`: runtime identity, dependencies, exact commands, packaging, core MCP revision, selected MCP extension identifiers, process lifecycle, and deployment topology when retained.
- `INTERFACES.md`: preferred agent route and deterministic fallback when packaged CLI or MCP is selected. MCP Apps does not create a separate route.
- `CLI_INTERFACE.md`: caller-visible packaged CLI behavior.
- `MCP_INTERFACE.md`: caller-visible core MCP negotiation, transport, pagination, results, interaction, cancellation, and compatibility.
- `MCP_APPS.md`: exact MCP Apps extension revision, `ui://` resources, tool-to-UI linkage, visibility, View↔Host bridge, fallback, sandbox/CSP/permissions, and Apps-specific tests when `io.modelcontextprotocol/ui` is selected.
- `WEB_INTERFACE.md`: standalone browser-visible routing, security, operation policy, health, and failure behavior. It is independent of Host-embedded MCP Apps.
- `references/`: operational knowledge declared by exact path in `SKILL.md`.
- `assets/`: static resources declared by exact path in `SKILL.md`.
- `scripts/`: private helpers or stable in-place launchers declared by exact path in `SKILL.md`.
- `src/`, `mcp/`, and `tests/`: implementation and evidence required by the selected profiles and extensions.

Do not duplicate one decision across several authorities. Cross-reference the owning contract. Core MCP revision and extension revision are deliberately separate authorities.

## Validation

Run the supported profile-aware validation entry point:

```sh
python .github/scripts/validate_profile_contracts.py
```

This entry point executes focused direct validators and shared-model rule validators against the retained contract files. Some focused direct validators retain their own bounded Markdown parsing for contract-specific checks, while the rule validators share `.github/scripts/lib/profile_contracts.py`. MCP extension validators activate from the exact extension identifiers selected in `RUNTIME.md`.

For complete repository validation, run:

```sh
python .github/scripts/validate_skill_repository.py
```

The repository entry point checks frontmatter, the machine-readable profile selection, exact operational-resource declarations, retained contract requirements, unresolved placeholders, public-interface and extension consistency, runtime/interface alignment, Git link boundaries, and concrete-Skill completion rules. It also invokes the supported profile-aware validation entry point.

The validation host requires Python 3.12 or newer, PyYAML 6.0.3, and Git. When a flattened archive has no Git metadata, the validator creates an ephemeral empty index outside the Skill root only for the metadata-only gitlink check. It must not mutate the Skill or a caller-owned alternate index.

The included GitHub Actions workflow installs the pinned validator dependency and runs the same complete repository validation. Retain, replace, or remove that workflow according to the concrete repository’s CI policy; it is not an operational Skill resource.

## Resource discipline

Every retained file under `references/`, `assets/`, or `scripts/` must be a regular non-symlink file and must have an exact corresponding declaration in `SKILL.md`. State when the agent reads, uses, or executes it and what it provides or modifies.

Do not use Git submodules or symlinks for operational resources. Do not install runtimes, package managers, or dependencies silently. Keep network access, permissions, side effects, approval, idempotency, diagnostics, and retry behavior explicit.

## Runtime neutrality

Runtime neutrality means delaying an implementation choice until the workflow requires one. It does not mean retaining competing manifests for unused ecosystems.

An instruction-only, knowledge-augmented, or asset-driven Skill may need no runtime. A small helper does not automatically become a packaged CLI. MCP, MCP extensions, standalone browser, and service interfaces remain optional and require their applicable contracts only when intentionally supported.

## Completion checklist

Before treating the result as a concrete Skill:

- replace the template name, description, workflow, and `template-scaffold` marker;
- retain only supported profiles and the union of their required contracts;
- select only MCP extensions actually implemented and remove unselected extension contracts/resources;
- declare every operational resource by exact path;
- remove unsupported contracts, directories, examples, and placeholders;
- complete runtime, public-interface, and selected extension decisions where applicable;
- choose the final license and remove `LICENSE.template`;
- run representative success, failure, side-effect, permission, protocol, and compatibility tests proportionate to the selected profile and extensions;
- run the repository validator; and
- verify that the repository can be installed with `SKILL.md` directly at the Skill root.
