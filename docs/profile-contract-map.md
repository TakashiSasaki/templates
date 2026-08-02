# Profile contract ownership

This document records which file is authoritative for each decision after the Phase 2 contract split. It is a maintainer map, not an operational resource loaded by the skill.

## Authority matrix

| Decision or behavior | Source of truth | Activated by |
|---|---|---|
| Skill trigger, workflow, operational resources, helper execution, outputs, safety | `SKILL.md` | every skill |
| Runtime, minimum version, dependency manager, manifest, lockfile, source layout, supported OS | `RUNTIME.md` | retained runtime record |
| Install, test, lint, format, build, start, stop, and readiness commands | `RUNTIME.md` | applicable runtime-backed profile |
| Preferred agent route and deterministic fallback order | `INTERFACES.md` | `packaged-cli` or `mcp-enabled` |
| Packaged CLI command, working directory, structured output, diagnostics, exit codes, compatibility | `CLI_INTERFACE.md` | `packaged-cli` |
| MCP caller-visible negotiation, transport behavior, pagination, lossless results, interaction, cancellation, compatibility | `MCP_INTERFACE.md` | `mcp-enabled` |
| Exact MCP revisions, SDK, schema dialects, server entry points, bind and lifecycle selections | `RUNTIME.md` | `mcp-enabled` |
| Browser-visible routing, authentication, authorization, operation policy, redaction, health and failure behavior | `WEB_INTERFACE.md` | `browser-interface` |
| Browser process/listener/container topology and enablement | `RUNTIME.md` | `browser-interface` |
| Headless-service endpoint, security, limits, state, health, lifecycle, shutdown and topology | `RUNTIME.md` and directly referenced deployment/API material | `headless-service` |

## Former monolithic interface sections

The following material formerly lived in `INTERFACES.md`:

| Former section | New authority |
|---|---|
| Human CLI | `CLI_INTERFACE.md` |
| Structured output | `CLI_INTERFACE.md` |
| Exit codes | `CLI_INTERFACE.md` |
| In-place agent launcher | `CLI_INTERFACE.md` |
| MCP protocol reference | `MCP_INTERFACE.md` |
| stdio MCP server variant | `MCP_INTERFACE.md` |
| Streamable HTTP MCP server variant | `MCP_INTERFACE.md` |
| Bundled ad hoc MCP tool client | `MCP_INTERFACE.md` |
| MCP pagination, result, interaction, cancellation and workspace rules | `MCP_INTERFACE.md` |
| Preferred interface and fallback order | remains in `INTERFACES.md` |
| Cross-interface semantic equivalence | summarized in `INTERFACES.md`; detailed tests remain in profile-specific contracts |

## Retention matrix

| Selected profile | Required contract files |
|---|---|
| `instruction-only` | `SKILL.md` |
| `knowledge-augmented` | `SKILL.md` plus declared `references/` files |
| `asset-driven` | `SKILL.md` plus declared `assets/` files |
| `script-assisted` | `SKILL.md`, declared `scripts/` files, optional `RUNTIME.md` |
| `packaged-cli` | `SKILL.md`, `RUNTIME.md`, `INTERFACES.md`, `CLI_INTERFACE.md` |
| `mcp-enabled` | `SKILL.md`, `RUNTIME.md`, `INTERFACES.md`, `MCP_INTERFACE.md`, `docs/mcp-transports.md` |
| `browser-interface` | `SKILL.md`, `RUNTIME.md`, `WEB_INTERFACE.md` |
| `headless-service` | `SKILL.md`, `RUNTIME.md`, applicable deployment/API material |

The `instruction-only` tag is exclusive and cannot participate in a combined selection. Other combined profiles retain the union of their required files. Remove `CLI_INTERFACE.md` when `packaged-cli` is not selected and remove `MCP_INTERFACE.md` when `mcp-enabled` is not selected.

## Validation architecture

`.github/scripts/validate-profile-contracts.rb` is the supported validation entry point. It runs the focused direct validators and the shared-model rule validators once each.

All rule validators parse `SKILL.md`, `RUNTIME.md`, `INTERFACES.md`, `CLI_INTERFACE.md`, `MCP_INTERFACE.md`, and `WEB_INTERFACE.md` directly through `.github/scripts/lib/profile_contracts.rb`. No in-memory monolithic interface document, `File.read` monkey patch, or `RUBYOPT` compatibility injection is used.
