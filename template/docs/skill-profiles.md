# Agent Skill profiles

This document helps maintainers choose the smallest repository structure that reliably supports a concrete skill. Profiles are selectable patterns, not mandatory maturity levels. Except for `instruction-only`, compatible profiles may be combined.

## Selection rule

Start with `SKILL.md`. Add a resource, runtime, interface, extension contract, or architecture layer only when it solves a demonstrated operational or maintenance problem.

A profile is sufficient when the agent can:

1. recognize when the skill applies;
2. obtain the required inputs and knowledge;
3. perform the workflow deterministically enough for its risk;
4. produce and validate the required result;
5. respect safety, permission, and side-effect boundaries.

Do not select a more complex profile solely because the template contains files for it.

## Machine-readable selection

Every `SKILL.md` must contain exactly one line in this form:

```text
Selected profiles: instruction-only
```

Combine compatible non-`instruction-only` profiles with comma-separated tags, for example:

```text
Selected profiles: knowledge-augmented, asset-driven, script-assisted
```

Allowed concrete-skill tags are:

- `instruction-only`;
- `knowledge-augmented`;
- `asset-driven`;
- `script-assisted`;
- `packaged-cli`;
- `mcp-enabled`;
- `browser-interface`;
- `headless-service`.

The `instruction-only` tag is exclusive and must be selected alone. If the workflow needs retained references, assets, scripts, runtime records, public interfaces, or a service, omit `instruction-only` and select the applicable profiles instead.

MCP extensions are **not profile tags**. An MCP-enabled Skill records selected extension identifiers in `RUNTIME.md`; an extension-specific contract is retained only when that extension is selected. In particular, MCP Apps uses `io.modelcontextprotocol/ui` and does not add an `mcp-apps` profile tag.

The special value `template-scaffold` is valid only while the skill remains the uncustomized `agent-skill-template`. Replace it before adding operational resources, implementation, runtime manifests, or interface contracts.

Structural validation uses the selected tags and MCP extension identifiers to activate the applicable requirements. Required contract ownership is summarized in `docs/profile-contract-map.md`.

## Profile 0: Instruction-only

Typical contents:

```text
SKILL.md
```

Select `instruction-only` by itself when the agent can perform the workflow with its existing tools and general knowledge.

`SKILL.md` should define the trigger, exclusions, prerequisites, workflow, outputs, validation, safety rules, and important edge cases. No runtime, package manager, public CLI, MCP adapter, Web contract, or application architecture is required.

## Profile 1: Knowledge-augmented

Typical contents:

```text
SKILL.md
references/
```

Use when the workflow depends on domain terminology, policy, schemas, compatibility rules, lookup data, or bounded troubleshooting procedures.

Every retained reference must have an exact `Reference:` declaration and explicit read trigger in `SKILL.md`. Record provenance, applicable version, and freshness requirements when those affect correctness. Do not copy broad documentation collections without a concrete operational use.

## Profile 2: Asset-driven

Typical contents:

```text
SKILL.md
assets/
```

Use when the workflow copies, fills, transforms, compares, or emits static templates and resources.

Every asset must have an exact `Asset:` declaration and a handling trigger in `SKILL.md`. State which parts may be modified, which must remain stable, and what output relationship is expected. Assets are not automatically instructions.

Knowledge and asset profiles may be combined without adding executable code.

## Profile 3: Script-assisted

Typical contents:

```text
SKILL.md
scripts/
tests/                 optional, risk-dependent
RUNTIME.md             optional when runtime decisions need a maintained record
```

Use when a small deterministic helper improves reliability, repeatability, parsing, validation, conversion, or file generation.

A helper script may be agent-oriented and private to the skill. It does not automatically require:

- a packaged public CLI;
- `INTERFACES.md` or `CLI_INTERFACE.md`;
- structured JSON output;
- long-term command compatibility;
- an application/domain layer split.

It does require a bounded execution contract covering invocation, working directory, inputs, outputs, diagnostics, exit behavior, side effects, permissions, network use, approval, and retry/idempotency behavior.

Retain `RUNTIME.md` only when runtime installation, dependencies, exact shared commands, distribution, or portability decisions need a separate authority.

## Profile 4: Packaged CLI application

Select the `packaged-cli` tag.

Required profile contents:

```text
SKILL.md
RUNTIME.md
INTERFACES.md
CLI_INTERFACE.md
src/
tests/
manifest and lockfile for one selected runtime
```

Use when a stable human, agent, or CI command is an intentionally maintained public interface.

The responsibilities are separated:

- `RUNTIME.md`: runtime, dependencies, exact commands, build/package, distribution, environment;
- `INTERFACES.md`: preferred agent route and deterministic fallback order;
- `CLI_INTERFACE.md`: caller-visible command, working directory, structured output, diagnostics, exit codes, side effects, compatibility, versioning, and contract tests.

Private helpers remain covered by Profile 3 and do not require these public contracts.

## Profile 5: MCP-enabled application

Select the `mcp-enabled` tag.

Required profile contents:

```text
SKILL.md
RUNTIME.md
INTERFACES.md
MCP_INTERFACE.md
docs/mcp-transports.md
```

Typical implementation addition:

```text
mcp/
```

Use when operations must be exposed through a native MCP host, stdio server, Streamable HTTP endpoint, or bounded MCP client.

The responsibilities are separated:

- `RUNTIME.md`: exact core protocol revision, selected extension identifiers, SDK, schema dialects, server entry points, commands, bind and lifecycle selections, distribution;
- `INTERFACES.md`: preferred MCP/CLI route and deterministic fallback order;
- `MCP_INTERFACE.md`: caller-visible core MCP negotiation, transport behavior, pagination, lossless results, interaction, cancellation, compatibility, and semantic-equivalence tests;
- `docs/mcp-transports.md`: maintainer-oriented core transport implementation guidance.

The unpublished template baseline is MCP core `2026-07-28`, Modern-only. Supporting MCP does not require supporting both transports, a bundled client, a packaged CLI, a standalone Web interface, or any optional extension.

### MCP Apps extension

When the Skill selects `io.modelcontextprotocol/ui` in `RUNTIME.md`, additionally retain:

```text
MCP_APPS.md
docs/mcp-apps.md          when maintainer guidance is useful
mcp/apps/                 only when bundled App implementation files live there
```

`MCP_APPS.md` owns the exact Apps extension revision, `ui://` resource contract, tool-to-UI linkage, visibility, View↔Host bridge, progressive fallback, sandbox/CSP/permissions, and Apps-specific tests. MCP Apps does not add a profile tag and does not create a separate route in `INTERFACES.md`; it enriches an MCP route when the Host negotiates the extension.

MCP Apps also does **not** select `browser-interface`. A Host-embedded sandboxed App View and a standalone browser-facing page have different lifecycle and security contracts. Select `browser-interface` separately only when an ordinary browser surface is intentionally exposed.

## Profile 6: Browser-interface

Select the `browser-interface` tag.

Required contracts:

```text
RUNTIME.md
WEB_INTERFACE.md
```

Use when a standalone browser-facing page is an intentional interface.

`RUNTIME.md` records supported process, listener, container, service, gateway, origin, and enablement topologies. `WEB_INTERFACE.md` records browser-visible routing, interaction, authentication, authorization, operation policy, redaction, health semantics, failure behavior, and tests.

A debug-only page may share an application or MCP process and container. It should normally be disabled unless explicitly enabled. A separate process, port, or container is optional; logical security and lifecycle boundaries are not. MCP Apps alone is not a reason to select this profile.

## Profile 7: Headless-service

Select the `headless-service` tag.

Required authority:

```text
RUNTIME.md
```

Use when an independently reachable non-browser service is intentional.

Complete the endpoint, authentication, authorization, exposure, limits, concurrency, state, readiness, liveness, cancellation, shutdown, failure, and deployment fields in `RUNTIME.md`. Directly referenced API or deployment material may add details. Do not retain `WEB_INTERFACE.md` unless a standalone browser-facing surface also exists.

## Combining profiles

The `instruction-only` tag does not participate in combinations. Other profiles may be combined selectively. Examples:

- `knowledge-augmented` with no executable code;
- `asset-driven` plus `script-assisted` for an asset and one validation helper;
- a packaged CLI with no MCP;
- stdio MCP with no packaged CLI and no standalone HTTP service;
- MCP plus `io.modelcontextprotocol/ui` without `browser-interface`;
- a packaged CLI plus MCP with one preferred route and explicit fallback;
- a headless HTTP service with no browser contract;
- a standalone Web UI backed by a non-MCP application API;
- a Web verification UI backed by an MCP client;
- one Skill that intentionally has both a Host-embedded MCP App and a separately contracted standalone Web page.

Do not assume that later profiles supersede earlier resources. A service-enabled skill may still use references, assets, and helper scripts.

## Contract retention matrix

| Selected profile or capability | Required contracts |
|---|---|
| `instruction-only` | `SKILL.md` |
| `knowledge-augmented` | `SKILL.md`, declared `references/` files |
| `asset-driven` | `SKILL.md`, declared `assets/` files |
| `script-assisted` | `SKILL.md`, declared `scripts/` files; optional `RUNTIME.md` |
| `packaged-cli` | `RUNTIME.md`, `INTERFACES.md`, `CLI_INTERFACE.md` |
| `mcp-enabled` | `RUNTIME.md`, `INTERFACES.md`, `MCP_INTERFACE.md`, MCP transport guidance |
| `io.modelcontextprotocol/ui` | `MCP_APPS.md` in addition to `mcp-enabled`; Apps implementation/guidance only when retained |
| `browser-interface` | `RUNTIME.md`, `WEB_INTERFACE.md` |
| `headless-service` | `RUNTIME.md`, applicable API/deployment material |

Except for the exclusive `instruction-only` tag, combined profiles retain the union of their requirements. Extension contracts are activated independently by the selected MCP extension identifiers.

## File removal rules

For a concrete skill, remove optional template material when unsupported:

- no operational knowledge: remove `references/`;
- no static resources: remove `assets/`;
- no helpers: remove `scripts/`;
- no runtime-dependent or service profile: remove `RUNTIME.md` when it has no remaining purpose;
- neither packaged CLI nor MCP: remove `INTERFACES.md`;
- no packaged CLI: remove `CLI_INTERFACE.md`;
- no MCP: remove `MCP_INTERFACE.md`, `MCP_APPS.md`, `mcp/`, and MCP-specific maintainer guidance when unused;
- MCP without Apps: remove `MCP_APPS.md`, `mcp/apps/`, and Apps-specific guidance when unused;
- no standalone browser-facing interface: remove `WEB_INTERFACE.md`, even when MCP Apps or a headless service remains;
- no maintainer need for a document: remove or shorten the applicable file under `docs/`.

Do not retain a large file filled with `NOT SUPPORTED` solely to resemble the full template.

## Validation strategy

Validation should be profile- and extension-aware:

| Profile/capability | Minimum validation emphasis |
|---|---|
| Instruction-only | valid frontmatter, clear trigger, complete workflow, output and safety checks |
| Knowledge-augmented | referenced files exist, read triggers are explicit, freshness/authority is handled |
| Asset-driven | assets exist, handling rules are explicit, output preservation is tested where needed |
| Script-assisted | representative execution, failure behavior, side effects, permissions, idempotency |
| Packaged CLI | installation, commands, structured output, exit codes, compatibility |
| MCP-enabled | core protocol and transport contracts, security, cancellation, pagination, result preservation |
| MCP Apps | extension selection, UI resources, linkage, visibility, fallback, bridge lifecycle, sandbox/CSP/permissions |
| Browser-interface | routing, authentication, authorization, browser exposure, health separation, deployment smoke tests |
| Headless-service | endpoint, authentication, authorization, exposure, health, lifecycle, shutdown, deployment smoke tests |

Run the supported profile-aware validation entry point:

```sh
python .github/scripts/validate_profile_contracts.py
```

The entry point runs both focused direct validators and shared-model rule validators against the decomposed contract files. It does not synthesize a monolithic interface document or load a compatibility adapter. Extension-specific focused validators activate only from selected extension identifiers.

The validation host requires Python 3.12 or newer, PyYAML 6.0.3, and Git.
