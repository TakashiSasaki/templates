# Contributing

## Before implementation

1. Read `AGENTS.md` and `SKILL.md`.
2. Confirm that `SKILL.md` contains exactly one concrete `Selected profiles:` declaration matching the intended repository shape. Replace `template-scaffold` before adding operational resources or treating the repository as a concrete skill. The `instruction-only` tag is exclusive and must not be combined with resource, executable, or service profiles.
3. Use `docs/skill-profiles.md` and `docs/profile-contract-map.md` to verify the smallest sufficient tags and the applicable sources of truth.
4. Read and update only the contracts that apply:
   - operational references, assets, or helper scripts: their exact entries and handling instructions in `SKILL.md`;
   - helper scripts with substantial runtime dependencies: `RUNTIME.md` when a separate runtime record is retained;
   - `packaged-cli`: completed `RUNTIME.md`, `INTERFACES.md`, and `CLI_INTERFACE.md`;
   - `mcp-enabled`: completed `RUNTIME.md`, `INTERFACES.md`, `MCP_INTERFACE.md`, and `docs/mcp-transports.md`;
   - `browser-interface`: completed `RUNTIME.md`, `WEB_INTERFACE.md`, and applicable architecture/deployment documentation;
   - `headless-service`: completed `RUNTIME.md` and applicable API, security, health, lifecycle, and deployment configuration.
5. Do not retain unsupported placeholder contracts merely to satisfy a generic checklist.
6. Avoid adding unused ecosystem boilerplate.

## Change process

- Keep operational instructions in `SKILL.md` concise and explicit.
- Put runtime-loaded detail in `references/`.
- Put static workflow resources in `assets/`.
- Use `scripts/` for bounded helpers or stable launchers when needed.
- Declare every retained reference, asset, and script by exact path in `SKILL.md`; linked references may supplement but not replace those declarations.
- Do not use symlinks or Git submodules/gitlinks under `references/`, `assets/`, or `scripts/`; retained operational resources must be regular files inside the installable skill.
- Keep preferred-route and fallback policy in `INTERFACES.md`.
- Keep packaged CLI caller behavior in `CLI_INTERFACE.md` and MCP caller behavior in `MCP_INTERFACE.md`.
- Keep exact runtime, command, package, protocol-selection, and deployment decisions in `RUNTIME.md`.
- Keep CLI, MCP, and Web adapters thin only when those interfaces exist.
- Add tests at the lowest layer that can establish the behavior.
- Update only the public contracts activated by `Selected profiles:`.

Run the supported profile-aware validation entry point:

```sh
ruby .github/scripts/validate-profile-contracts.rb
```

Reduced repository fixtures under `.github/fixtures/profiles/` exercise the four single resource-shape profiles, one script-assisted optional-runtime variant, one combined resource profile selecting `knowledge-augmented`, `asset-driven`, and `script-assisted`, one intentionally invalid unsupported-combination fixture proving that `instruction-only` is exclusive, the four single application profiles, and one combined application fixture selecting `packaged-cli` and `mcp-enabled`. The unsupported-combination fixture must contain only a complete `SKILL.md` and fail repository validation with the exact exclusive-profile diagnostic, so unrelated structural failures cannot satisfy the regression. The script-assisted optional-runtime fixture must retain only a complete `SKILL.md`, a completed `RUNTIME.md`, its declared helper, and its declared executable test; pass complete repository validation and the exact distributed test command; require no manifest or lockfile; and reject an unselected or placeholder-bearing retained runtime. The combined resource fixture must pass complete repository validation, execute its declared helper deterministically, and fail when any retained resource directory loses its required selected profile. The combined CLI/MCP fixture must retain the union of both public contracts, use one shared domain implementation behind thin CLI and MCP adapters, pass actual CLI and stdio MCP execution, prove semantic equivalence, build and install the packaged command, and fail when either profile-specific contract is removed. The packaged CLI fixture must pass complete repository validation, its unit tests, gem build and isolated installation, and an installed-command structured-output check. The MCP-enabled fixture must pass complete repository validation, install the pinned official Ruby SDK and HTTP runtime, initialize revision `2025-11-25` over both stdio and authenticated loopback Streamable HTTP, share one server factory and domain operation, exercise discovery and calls, prove transport equivalence, distinguish protocol, tool, authentication, request-policy, size-limit, and capacity failures, validate Host and Origin on every reused-connection request, preserve stdio stdout/stderr separation, prove bounded stdio shutdown and graceful HTTP shutdown/restart, and reject missing shared or transport implementation and required contract artifacts. The browser-interface fixture must pass complete repository validation, install the pinned Web runtime, remain disabled by default, bind only to loopback, enforce Host and same-origin request policy, preserve security headers and input redaction, separate Web readiness from operation failures, prove startup and PID-based shutdown, and reject missing implementation or required contract artifacts. The headless-service fixture must pass complete repository validation, install the pinned service runtime, bind only to loopback, load authentication material from a permission-checked external file, enforce authorization and non-browser request policy, bound request size and concurrency, separate readiness from liveness and request failures, prove identity-verified shutdown, and reject missing implementation or unsupported browser contracts.

This fixture matrix is the stable baseline for the current profile model. Additional transport variants, bundled clients, or production deployment modes require their own explicit contracts and proportionate executable fixtures; they do not reopen the completed validator-consolidation transition.

## Documentation publication compatibility

Pull requests to `main` that change canonical Markdown, `docs/`, or `assets/` are assembled and built against the current `site` branch by **Check documentation site compatibility**. The pull-request run uses GitHub's proposed merge commit, records both exact source commits in the generated artifact, and never deploys it.

The same non-deploying check runs weekly and can be started manually to detect drift between the current `main` and `site` branches. Publication after a merge remains the responsibility of **Publish template documentation**.

## Pull requests

Describe:

- the selected profile tags and behavior changed;
- the operational resource or interface affected;
- the source-of-truth files changed;
- the runtime or dependency impact, or state that none applies;
- the tests and profile-aware validation executed;
- any compatibility, security, permission, or portability implications.
