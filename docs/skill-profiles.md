# Agent Skill profiles

This document helps maintainers choose the smallest repository structure that reliably supports a concrete skill. Profiles are cumulative patterns, not mandatory maturity levels.

## Selection rule

Start with `SKILL.md`. Add a resource, runtime, interface, or architecture layer only when it solves a demonstrated operational or maintenance problem.

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

Combine profiles with comma-separated tags, for example:

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

The special value `template-scaffold` is valid only while the skill name remains `agent-skill-template` and no operational files have been added under `references/`, `assets/`, `scripts/`, or `mcp/`. Replace it before customizing the template. Structural validation uses the selected tags to activate profile-specific contract requirements; `packaged-cli` requires both `RUNTIME.md` and `INTERFACES.md`, and `headless-service` requires a completed `RUNTIME.md`.

## Profile 0: Instruction-only

Typical contents:

```text
SKILL.md
```

Use when the agent can perform the workflow with its existing tools and general knowledge.

`SKILL.md` should define the trigger, exclusions, prerequisites, workflow, outputs, validation, safety rules, and important edge cases.

No runtime, package manager, public CLI, MCP adapter, Web contract, or application architecture is required.

## Profile 1: Knowledge-augmented

Typical contents:

```text
SKILL.md
references/
```

Use when the workflow depends on domain terminology, policy, schemas, compatibility rules, lookup data, or bounded troubleshooting procedures.

Every retained reference must have an explicit read trigger in `SKILL.md`. Record provenance, applicable version, and freshness requirements when those affect correctness.

Do not copy broad documentation collections into `references/` without a concrete operational use.

## Profile 2: Asset-driven

Typical contents:

```text
SKILL.md
assets/
```

Use when the workflow copies, fills, transforms, compares, or emits static templates and resources.

Every asset must have an exact `Asset: assets/...` declaration and a handling trigger in `SKILL.md`. Supplemental detail may live in a directly linked reference, but the reference does not replace the `SKILL.md` declaration. State which parts may be modified, which must remain stable, and what output relationship is expected.

Assets are not automatically instructions.

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
- `INTERFACES.md`;
- structured JSON output;
- long-term command compatibility;
- an application/domain layer split.

It does require a bounded execution contract covering invocation, working directory, inputs, outputs, diagnostics, exit behavior, side effects, permissions, network use, approval, and retry/idempotency behavior.

Retain `RUNTIME.md` when runtime installation, dependencies, exact commands, or portability decisions are substantial enough to need a separate authority. Otherwise document the small helper directly in `SKILL.md`.

## Profile 4: Packaged CLI application

Select the `packaged-cli` tag.

Required profile contents:

```text
SKILL.md
RUNTIME.md
INTERFACES.md
src/
tests/
manifest and lockfile for one selected runtime
```

Use when a stable human, agent, or CI command is an intentionally maintained public interface.

`INTERFACES.md` is required for this profile because the packaged command intentionally maintains public behavior. Private helper scripts remain covered by Profile 3 and do not require that contract.

This profile should define:

- installation and runtime requirements;
- canonical commands and working directories;
- input and output contracts;
- diagnostics and exit codes;
- compatibility and versioning policy;
- representative integration tests.

Separate adapters from reusable application or domain behavior when complexity, multiple commands, or future interfaces justify it.

## Profile 5: MCP-enabled application

Select the `mcp-enabled` tag.

Typical additions:

```text
mcp/
docs/mcp-transports.md
MCP sections in RUNTIME.md and INTERFACES.md
```

Use when operations must be exposed through a native MCP host, stdio server, Streamable HTTP endpoint, or bounded MCP client.

Apply the protocol, negotiation, lifecycle, pagination, lossless-result, cancellation, and transport-security contracts only in this profile.

Supporting MCP does not require supporting both transports, multiple protocol eras, a bundled client, or a Web interface.

## Profile 6: Browser or headless service application

Select `browser-interface`, `headless-service`, or both as applicable.

Required authority for either service profile:

```text
RUNTIME.md
```

Additional required contract when a browser-facing interface exists:

```text
WEB_INTERFACE.md
```

Use when a browser-facing page or independently reachable headless network service is an intentional interface.

A headless service must complete `RUNTIME.md` and record its endpoint, authentication, authorization, exposure, health, lifecycle, shutdown, failure, and deployment decisions there or in directly referenced deployment configuration. It does not retain `WEB_INTERFACE.md` unless a browser-facing surface also exists.

A browser-facing interface must retain `WEB_INTERFACE.md` for browser-visible routing, interaction, security, operation policy, redaction, health semantics, and failure behavior.

The final process, port, container, Pod or task, service, gateway, and reverse-proxy topology may remain deployment-selected. Logical routing, security, health, lifecycle, and failure boundaries must still be explicit.

A debug-only Web page may share the MCP or application process and container. It should normally be disabled unless explicitly enabled.

## Combining profiles

Profiles may be combined selectively. Examples:

- instruction plus references, with no code;
- assets plus one validation helper;
- a packaged CLI with no MCP;
- stdio MCP with no standalone HTTP service;
- a headless HTTP service with no browser contract;
- a Web UI backed by a non-MCP application API;
- a Web verification UI backed by an MCP client.

Do not assume that later profiles supersede earlier resources. A service-enabled skill may still use references, assets, and helper scripts.

## File removal rules

For a concrete skill, remove optional template material when unsupported:

- no operational knowledge: remove `references/`;
- no static resources: remove `assets/`;
- no helpers: remove `scripts/`;
- no runtime-dependent or service profile: remove `RUNTIME.md` when it has no remaining purpose;
- no packaged CLI or MCP contract: remove `INTERFACES.md`;
- no MCP: remove `mcp/` and MCP-specific maintainer guidance if it is not useful;
- no browser-facing interface: remove `WEB_INTERFACE.md`, even when a headless service remains;
- no maintainer need for a document: remove or shorten the applicable file under `docs/`.

Do not retain a large file filled with `NOT SUPPORTED` solely to resemble the full template.

## Validation strategy

Validation should be profile-aware:

| Profile | Minimum validation emphasis |
|---|---|
| Instruction-only | valid frontmatter, clear trigger, complete workflow, output and safety checks |
| Knowledge-augmented | referenced files exist, read triggers are explicit, freshness/authority is handled |
| Asset-driven | assets exist, handling rules are explicit, output preservation is tested where needed |
| Script-assisted | representative execution, failure behavior, side effects, permissions, idempotency |
| Packaged CLI | installation, commands, output, exit codes, compatibility |
| MCP-enabled | protocol and transport contracts, security, cancellation, result preservation |
| Browser-interface | routing, authentication, authorization, browser exposure, health separation, deployment smoke tests |
| Headless-service | endpoint, authentication, authorization, exposure, health, lifecycle, shutdown, deployment smoke tests |

The template's generic structural workflow validates the universal skill core plus requirements activated by `Selected profiles:` and retained operational resources.
