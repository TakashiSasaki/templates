# Contributing

## Before implementation

1. Read `AGENTS.md` and `SKILL.md`.
2. Confirm that `SKILL.md` contains exactly one concrete `Selected profiles:` declaration matching the intended repository shape. Replace `template-scaffold` before adding operational resources or treating the repository as a concrete skill.
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

During the Phase 2 validation transition, run:

```sh
ruby .github/scripts/validate-profile-contracts.rb
```

Reduced repository fixtures under `.github/fixtures/profiles/` exercise the four resource-shape profiles and the `packaged-cli`, `mcp-enabled`, `browser-interface`, and `headless-service` application profiles. The packaged CLI fixture must pass complete repository validation, its unit tests, gem build and isolated installation, and an installed-command structured-output check. The MCP-enabled fixture must pass complete repository validation, install the pinned official Ruby SDK, initialize the selected revision over stdio, exercise tool discovery and calls, distinguish protocol and tool-validation errors, preserve stdout/stderr separation, prove bounded shutdown, and reject missing implementation or required contract artifacts. The browser-interface fixture must pass complete repository validation, install the pinned Web runtime, remain disabled by default, bind only to loopback, enforce Host and same-origin request policy, preserve security headers and input redaction, separate Web readiness from operation failures, prove startup and PID-based shutdown, and reject missing implementation or required contract artifacts. The headless-service fixture must pass complete repository validation, install the pinned service runtime, bind only to loopback, load authentication material from a permission-checked external file, enforce authorization and non-browser request policy, bound request size and concurrency, separate readiness from liveness and request failures, prove identity-verified shutdown, and reject missing implementation or unsupported browser contracts.

## Documentation publication compatibility

Pull requests to `main` that change canonical Markdown, `docs/`, or `assets/` are assembled and built against the current `site` branch by **Check documentation site compatibility**. The pull-request run uses GitHub's proposed merge commit, records both exact source commits in the generated artifact, and never deploys it.

The same non-deploying check runs weekly and can be started manually to detect drift between `main` and `site`. Publication after a merge remains the responsibility of **Publish template documentation**.

## Pull requests

Describe:

- the selected profile tags and behavior changed;
- the operational resource or interface affected;
- the source-of-truth files changed;
- the runtime or dependency impact, or state that none applies;
- the tests and profile-aware validation executed;
- any compatibility, security, permission, or portability implications.
