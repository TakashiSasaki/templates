# Agent Skill profiles

Skill profiles describe only Skill-specific resource structure. Application runtime and public interfaces are composition capabilities, not profiles.

## Selection rule

Start with `SKILL.md`. Add only the resource structures the workflow demonstrably needs.

Every concrete Skill uses exactly one `Selected profiles:` line. `instruction-only` is exclusive; the other profiles may be combined.

## Profile 0: instruction-only

Typical semantic content:

```text
SKILL.md
```

Use when the agent can perform the workflow with its existing tools and general knowledge. No references, assets, helper scripts, runtime, or public interface is required.

## Profile 1: knowledge-augmented

Create `references/` only when the workflow depends on maintained terminology, policy, schemas, compatibility rules, lookup data, or troubleshooting procedures.

Every retained reference must have a `Reference:` declaration in `SKILL.md` with an explicit read trigger and authority/freshness notes when relevant.

## Profile 2: asset-driven

Create `assets/` only when the workflow copies, fills, transforms, compares, or emits static resources.

Every retained asset must have an `Asset:` declaration in `SKILL.md` describing its trigger, handling, and preservation requirements.

## Profile 3: script-assisted

Create `scripts/` only when a bounded helper improves reliability, repeatability, parsing, validation, conversion, or file generation.

Every retained helper needs a `Script:` declaration in `SKILL.md` covering exact invocation, inputs, outputs, diagnostics, side effects, permissions, network access, approval, and retry/idempotency.

A helper script does not automatically become a public CLI. Select `capability.runtime` only when runtime/dependency decisions need a maintained authority, and select `capability.cli` only when a stable public command is intentionally maintained.

## Application capabilities

These are selected by composition, not by `Selected profiles:`:

| Capability | Materialized contract |
|---|---|
| `capability.runtime` | `RUNTIME.md` |
| `capability.cli` | `CLI_INTERFACE.md` |
| `capability.mcp` | `MCP_INTERFACE.md` |
| `capability.mcp-apps` | `MCP_APPS.md` |
| `capability.web-interface` | `WEB_INTERFACE.md` |
| `capability.service` | `SERVICE_INTERFACE.md` |

Dependencies are resolved by composition. For example, selecting `capability.mcp-apps` also resolves `capability.mcp` and `capability.runtime`.

The Skill records only the preferred agent route and fallback conditions in `SKILL.md`. This prevents Skill-specific routing policy from becoming authority inside a reusable generic capability.

## Removed legacy profile tags

The following old Skill profile tags are intentionally retired:

- `packaged-cli`;
- `mcp-enabled`;
- `browser-interface`;
- `headless-service`.

Do not preserve them for compatibility. Repositories using the composition model represent those concerns with `capability.*` selection.

## Validation

Run:

```sh
python scripts/validate_skill.py .
```

The validator checks the four-profile model, declared resources, and capability-file relationships. When a composition lock exists, it also checks the known Skill projection of resolved capabilities.
