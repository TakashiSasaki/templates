# Language-neutral Agent Skill Template

This repository is a template for developing a portable Agent Skill. Its root is intended to become the installable Skill directory directly:

```text
<project>/.agents/skills/<skill-name>/
```

`SKILL.md` is the only universally required operational file. Keep references, assets, scripts, runtime records, public interfaces, implementation, tests, and service material only when the selected Skill actually needs them.

## Start a concrete Skill

1. Copy the complete template contents into an empty destination so `SKILL.md` is directly under the destination root.
2. Choose a final lowercase hyphenated Skill name and replace the template frontmatter in `SKILL.md`.
3. Rewrite the trigger, exclusions, prerequisites, workflow, outputs, validation, safety rules, and failure behavior around the real task.
4. Replace `Selected profiles: template-scaffold` with `instruction-only` alone or the smallest sufficient compatible profile tags.
5. Add or complete only the resources, runtime, implementation, interfaces, and tests required by those profiles.
6. Delete every unsupported optional contract and directory rather than retaining placeholder material.
7. Choose the concrete Skill license. Keep `LICENSE` to use MIT-0 or replace it, then remove `LICENSE.template`.
8. Run the included validation before treating the Skill as complete.

Do not retain `template-scaffold` after adding operational resources, executable implementation, runtime manifests, or public interfaces.

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
| `browser-interface` | `RUNTIME.md`, `WEB_INTERFACE.md`, implementation and tests | A browser-facing interface is intentional |
| `headless-service` | `RUNTIME.md`, applicable API/deployment material, implementation and tests | An independently reachable non-browser service is intentional |

`instruction-only` is exclusive. Compatible non-`instruction-only` profiles may be combined, and a combination retains the union of their required contracts. A service-enabled Skill may still use knowledge, assets, or helper scripts.

See `docs/skill-profiles.md` for selection, retention, removal, and validation rules. See `docs/profile-contract-map.md` for contract ownership.

## Contract ownership

- `SKILL.md`: trigger, workflow, resources, helper invocation, outputs, validation, safety, and selected profiles.
- `RUNTIME.md`: runtime identity, dependencies, exact commands, packaging, protocol selections, process lifecycle, and deployment topology when retained.
- `INTERFACES.md`: preferred agent route and deterministic fallback when packaged CLI or MCP is selected.
- `CLI_INTERFACE.md`: caller-visible packaged CLI behavior.
- `MCP_INTERFACE.md`: caller-visible MCP negotiation, transport, pagination, results, interaction, cancellation, and compatibility.
- `WEB_INTERFACE.md`: browser-visible routing, security, operation policy, health, and failure behavior.
- `references/`: operational knowledge declared by exact path in `SKILL.md`.
- `assets/`: static resources declared by exact path in `SKILL.md`.
- `scripts/`: private helpers or stable in-place launchers declared by exact path in `SKILL.md`.
- `src/`, `mcp/`, and `tests/`: implementation and evidence required by the selected profiles.

Do not duplicate one decision across several authorities. Cross-reference the owning contract.

## Validation

Run the supported profile-aware validation entry point:

```sh
ruby .github/scripts/validate-profile-contracts.rb
```

This entry point executes focused direct validators and shared-model rule validators against the retained contract files. Some focused direct validators retain their own bounded Markdown parsing for contract-specific checks, while the rule validators share `.github/scripts/lib/profile_contracts.rb`.

For complete repository validation, run:

```sh
ruby .github/scripts/validate-skill-repository.rb
```

The repository entry point checks frontmatter, the machine-readable profile selection, exact operational-resource declarations, retained contract requirements, unresolved placeholders, public-interface consistency, runtime/interface alignment, Git link boundaries, and concrete-Skill completion rules. It also invokes the supported profile-aware validation entry point.

The validation host requires CRuby 3.1 or newer and Git. When a flattened archive has no Git metadata, the validator creates an ephemeral empty index outside the Skill root only for the metadata-only gitlink check. It must not mutate the Skill or a caller-owned alternate index.

The included GitHub Actions workflow runs the same complete repository validation. Retain, replace, or remove that workflow according to the concrete repository’s CI policy; it is not an operational Skill resource.

## Resource discipline

Every retained file under `references/`, `assets/`, or `scripts/` must be a regular non-symlink file and must have an exact corresponding declaration in `SKILL.md`. State when the agent reads, uses, or executes it and what it provides or modifies.

Do not use Git submodules or symlinks for operational resources. Do not install runtimes, package managers, or dependencies silently. Keep network access, permissions, side effects, approval, idempotency, diagnostics, and retry behavior explicit.

## Runtime neutrality

Runtime neutrality means delaying an implementation choice until the workflow requires one. It does not mean retaining competing manifests for unused ecosystems.

An instruction-only, knowledge-augmented, or asset-driven Skill may need no runtime. A small helper does not automatically become a packaged CLI. MCP, browser, and service interfaces remain optional and require their applicable contracts only when intentionally supported.

## Completion checklist

Before treating the result as a concrete Skill:

- replace the template name, description, workflow, and `template-scaffold` marker;
- retain only supported profiles and the union of their required contracts;
- declare every operational resource by exact path;
- remove unsupported contracts, directories, examples, and placeholders;
- complete runtime and public-interface decisions where applicable;
- choose the final license and remove `LICENSE.template`;
- run representative success, failure, side-effect, permission, and compatibility tests proportionate to the selected profile;
- run the repository validator; and
- verify that the repository can be installed with `SKILL.md` directly at the Skill root.
