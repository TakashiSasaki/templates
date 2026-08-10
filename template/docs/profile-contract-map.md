# Profile contract ownership

This document records which file is authoritative for each decision after the contract split. It is a maintainer map, not an operational resource loaded by the skill.

## Authority matrix

| Decision or behavior | Source of truth | Activated by |
|---|---|---|
| Skill trigger, workflow, operational resources, helper execution, outputs, safety | `SKILL.md` | every skill |
| Runtime, minimum version, dependency manager, manifest, lockfile, source layout, supported OS | `RUNTIME.md` | retained runtime record |
| Install, test, lint, format, build, start, stop, and readiness commands | `RUNTIME.md` | applicable runtime-backed profile |
| Preferred agent route and deterministic fallback order | `INTERFACES.md` | `packaged-cli` or `mcp-enabled` |
| Packaged CLI command, working directory, structured output, diagnostics, exit codes, compatibility | `CLI_INTERFACE.md` | `packaged-cli` |
| MCP core caller-visible negotiation, transport behavior, pagination, lossless results, interaction, cancellation, compatibility | `MCP_INTERFACE.md` | `mcp-enabled` |
| Exact MCP core revision, SDK, schema dialects, selected extension identifiers, server entry points, bind and lifecycle selections | `RUNTIME.md` | `mcp-enabled` |
| MCP Apps extension revision, `ui://` resources, tool-to-UI linkage, visibility, View↔Host bridge, sandbox/CSP/permissions, fallback | `MCP_APPS.md` | `mcp-enabled` plus `io.modelcontextprotocol/ui` selected in `RUNTIME.md` |
| Browser-visible routing, authentication, authorization, operation policy, redaction, health and failure behavior | `WEB_INTERFACE.md` | standalone `browser-interface` |
| Browser process/listener/container topology and enablement | `RUNTIME.md` | `browser-interface` |
| Headless-service endpoint, security, limits, state, health, lifecycle, shutdown and topology | `RUNTIME.md` and directly referenced deployment/API material | `headless-service` |

Core MCP revision and MCP extension revisions are separate authorities. `RUNTIME.md` records which extension identifiers are selected; the retained extension-specific contract records the exact extension revision and its public semantics.

## Interface and extension boundaries

| Surface | Authority |
|---|---|
| Human CLI | `CLI_INTERFACE.md` |
| Structured CLI output | `CLI_INTERFACE.md` |
| Exit codes | `CLI_INTERFACE.md` |
| In-place agent launcher | `CLI_INTERFACE.md` |
| Core MCP protocol reference | `MCP_INTERFACE.md` |
| stdio MCP server variant | `MCP_INTERFACE.md` |
| Streamable HTTP MCP server variant | `MCP_INTERFACE.md` |
| Bundled ad hoc MCP tool client | `MCP_INTERFACE.md` |
| MCP pagination, result, MRTR, cancellation and workspace rules | `MCP_INTERFACE.md` |
| MCP Apps `io.modelcontextprotocol/ui` behavior | `MCP_APPS.md` |
| Standalone browser interface | `WEB_INTERFACE.md` |
| Preferred interface and fallback order | `INTERFACES.md` |
| Cross-interface semantic equivalence | summarized in `INTERFACES.md`; detailed tests remain in profile- or extension-specific contracts |

MCP Apps is not an additional profile and not a routing category. A Host-embedded App View enriches an MCP route. A standalone Web page remains a separate `browser-interface` selection even when frontend implementation code is shared.

## Retention matrix

| Selected profile or capability | Required contract files |
|---|---|
| `instruction-only` | `SKILL.md` |
| `knowledge-augmented` | `SKILL.md` plus declared `references/` files |
| `asset-driven` | `SKILL.md` plus declared `assets/` files |
| `script-assisted` | `SKILL.md`, declared `scripts/` files, optional `RUNTIME.md` |
| `packaged-cli` | `SKILL.md`, `RUNTIME.md`, `INTERFACES.md`, `CLI_INTERFACE.md` |
| `mcp-enabled` without Apps | `SKILL.md`, `RUNTIME.md`, `INTERFACES.md`, `MCP_INTERFACE.md`, `docs/mcp-transports.md` |
| `mcp-enabled` + `io.modelcontextprotocol/ui` | MCP files above plus `MCP_APPS.md`; retain Apps implementation files/guidance only when used |
| `browser-interface` | `SKILL.md`, `RUNTIME.md`, `WEB_INTERFACE.md` |
| `headless-service` | `SKILL.md`, `RUNTIME.md`, applicable deployment/API material |

The `instruction-only` tag is exclusive and cannot participate in a combined selection. Other combined profiles retain the union of their required files. Remove `CLI_INTERFACE.md` when `packaged-cli` is not selected, remove `MCP_INTERFACE.md` when `mcp-enabled` is not selected, and remove `MCP_APPS.md` plus `mcp/apps/` implementation files when `io.modelcontextprotocol/ui` is not selected.

## Validation architecture

`.github/scripts/validate_profile_contracts.py` is the supported validation entry point. It runs the focused direct validators and the shared-model rule validators once each.

Core profile validators parse `SKILL.md`, `RUNTIME.md`, `INTERFACES.md`, `CLI_INTERFACE.md`, `MCP_INTERFACE.md`, and `WEB_INTERFACE.md` through `.github/scripts/lib/profile_contracts.py`. Extension-specific validators read only the contracts activated by the selected extension identifiers. No in-memory monolithic interface document or compatibility parser shim is used.

The orchestrator clears inherited `GIT_DIR`, `GIT_WORK_TREE`, and `GIT_INDEX_FILE` values before detecting the skill root's Git context, and uses a stable C locale for that probe. Rule validators inspect the discovered worktree's real index so operational-resource gitlinks remain rejectable. A flattened archive has no index to inspect; in that case the orchestrator creates a dedicated ephemeral empty index outside the skill root and uses it only for the gitlink query. Filesystem existence, regular-file, symlink, exact declaration, selected-profile, extension-selection, and contract checks continue to use the extracted skill root. The temporary context must not modify the skill or any caller-owned alternate index, and the orchestrator must fail rather than silently skip metadata validation when Git is unavailable or returns an unexpected error.
