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
- Keep exact runtime, command, package, protocol-selection, lifecycle, and deployment decisions in `RUNTIME.md`.
- Keep CLI, MCP, and Web adapters thin only when those interfaces exist.
- Keep lifecycle controllers outside domain operations and caller protocols; do not expose start, stop, restart, health, PID, or secret management as MCP tools.
- Add tests at the lowest layer that can establish the behavior.
- Update only the public contracts activated by `Selected profiles:`.

Run the supported profile-aware validation entry point:

```sh
ruby .github/scripts/validate-profile-contracts.rb
```

Run complete repository validation from the skill root or pass an explicit adopted skill root:

```sh
ruby .github/scripts/validate-skill-repository.rb
ruby /path/to/canonical-template/.github/scripts/validate-skill-repository.rb \
  /path/to/project/.agents/skills/<skill-name>
```

The explicit-root form must resolve every contract and operational resource relative to the supplied skill root rather than the caller's current working directory. It clears inherited `GIT_DIR`, `GIT_WORK_TREE`, and `GIT_INDEX_FILE` overrides before discovering the target's Git context. If the target is inside a Git worktree, the validator inspects that worktree's real index for forbidden operational-resource gitlinks. If a flattened archive target has no Git metadata, the supported orchestrator supplies a dedicated temporary empty index only for that metadata-only check; every filesystem, declaration, symlink, profile, and contract rule still executes against the target, and validation must not write into either the target or a caller-owned alternate index. The repository probe uses a stable C locale.

Reduced repository fixtures under `.github/fixtures/profiles/` exercise the four single resource-shape profiles, one script-assisted optional-runtime variant, one combined resource profile selecting `knowledge-augmented`, `asset-driven`, and `script-assisted`, one intentionally invalid unsupported-combination fixture proving that `instruction-only` is exclusive, the four single application profiles, and one combined application fixture selecting `packaged-cli` and `mcp-enabled`. The unsupported-combination fixture must contain only a complete `SKILL.md` and fail repository validation with the exact exclusive-profile diagnostic, so unrelated structural failures cannot satisfy the regression. The script-assisted optional-runtime fixture must retain only a complete `SKILL.md`, a completed `RUNTIME.md`, its declared helper, and its declared executable test; pass complete repository validation and the exact distributed test command; require no manifest or lockfile; and reject an unselected or placeholder-bearing retained runtime. The combined resource fixture must pass complete repository validation, execute its declared helper deterministically, and fail when any retained resource directory loses its required selected profile. The combined CLI/MCP fixture must retain the union of both public contracts, use one shared domain implementation behind thin CLI and MCP adapters, pass actual CLI and stdio MCP execution, prove semantic equivalence, build and install the packaged command, and fail when either profile-specific contract is removed. The packaged CLI fixture must pass complete repository validation, its unit tests, gem build and isolated installation, and an installed-command structured-output check.

The canonical adoption smoke under `.github/scripts/test-template-adoption.rb` is separate from the reduced fixture matrix. It must copy the actual repository root, exclude source `.git/` metadata, customize nested `.agents/skills/<name>/` targets, and prune them into one `instruction-only` repository containing only `SKILL.md` and one `script-assisted` repository containing only `SKILL.md` plus its declared deterministic helper. Both targets must pass complete validation from their own root and from an unrelated working directory through the explicit skill-root argument. The smoke must prove that no wrapper directory, runtime record, public interface contract, network behavior, implicit dependency installation, or input mutation is introduced, and must reject a renamed canonical `SKILL.md`, unresolved placeholders, unnecessary runtime contracts, invalid UTF-8, and undeclared helpers. The smoke is a deterministic regression harness, not a generator CLI or interactive scaffolding interface.

The installation-mode smoke under `.github/scripts/test-installation-modes.rb` must materialize one concrete `script-assisted` skill from the canonical root, commit it once, and install that exact commit by direct clone, project submodule, and prefixed Git archive extraction. The archive must be flattened so `SKILL.md` is directly under the final `.agents/skills/<name>/` directory. All three installations must have identical non-Git inventories, file bytes, and Git-significant executable modes; pass complete validation from an unrelated working directory; and execute the same deterministic helper without input mutation, network use, or dependency installation. The smoke must verify real clone and submodule metadata, verify that archive validation requires no repository metadata in the target, preserve a caller-owned alternate Git index, reject an unflattened archive wrapper, and reject undeclared operational files in every mode. It does not publish releases, fetch remote archives, select profiles or licenses, or create a generator interface.

The MCP-enabled fixture must pass complete repository validation, install the pinned official Ruby SDK and HTTP runtime, initialize revision `2025-11-25` over both stdio and authenticated loopback Streamable HTTP, share one server factory and domain operation, exercise discovery and calls, prove transport equivalence, distinguish protocol, tool, authentication, request-policy, size-limit, and capacity failures, validate Host and Origin on every reused-connection request, preserve stdio stdout/stderr separation, prove bounded stdio shutdown and graceful HTTP shutdown/restart, and reject missing shared or transport implementation and required contract artifacts. Its private tools-only client executes real initialization, discovery, one and sequential `tools/call` operations over stdio and authenticated loopback HTTP, preserves ordered raw pages and complete results including additive fields, distinguishes transport, timeout, authentication, request-policy, JSON-RPC, tool-result, capacity, invalid-result, and pagination outcomes, and confirms that the client never exposes `packaged-cli`, arbitrary server commands, caller-selected request IDs, implicit HTTP startup, lifecycle control, or unbounded retries.

The MCP-enabled fixture also includes one optional managed local lifecycle variant around the same loopback HTTP adapter. Its distributed test must execute real start, readiness, liveness, restart, and stop; require a permission-checked external token file; publish and verify an owner-only PID plus Linux process-start record; safely replace stale records without signaling unrelated processes; reject symlinked or overly permissive secrets and unsafe PID records before listener creation; redact the token from argv, records, and logs; and prove bounded TERM-to-KILL process-group escalation. It must not claim OS service installation, automatic restart, non-loopback exposure, reverse-proxy trust, TLS, containerization, persistence, or orchestration.

The combined MCP/systemd-service fixture selects `mcp-enabled` and `headless-service` to establish one separate OS service-manager topology. It must render a fixed no-shell systemd system unit without installing it implicitly, retain the authenticated loopback Streamable HTTP contract, load the Bearer token through `LoadCredential=`, publish readiness through `Type=notify`, keep systemd as the sole process and control-group owner, restart unexpected failure within bounded start limits, suppress restart for permanent application configuration exit 78, apply explicit service hardening, and execute real start, discovery, sequential tool calls, explicit restart, KILL-triggered restart, stop, and journal-redaction smoke tests. It must not claim non-loopback exposure, proxy trust, TLS, socket activation, containers, persistence, multiple workers, metrics, zero-downtime rollout, or orchestration.

The browser-interface fixture must pass complete repository validation, install the pinned Web runtime, remain disabled by default, bind only to loopback, enforce Host and same-origin request policy, preserve security headers and input redaction, separate Web readiness from operation failures, prove startup and PID-based shutdown, and reject missing implementation or required contract artifacts. The headless-service fixture must pass complete repository validation, install the pinned service runtime, bind only to loopback, load authentication material from a permission-checked external file, enforce authorization and non-browser request policy, bound request size and concurrency, separate readiness from liveness and request failures, prove identity-verified shutdown, and reject missing implementation or unsupported browser contracts.

This fixture matrix is the stable baseline for the current profile model. The canonical adoption and installation-mode smokes extend that baseline with template-consumption and concrete-installation paths. Additional transport variants, remote-client modes, trusted reverse proxies, TLS boundaries, further OS service integrations, containers, persistence, release publication, distribution services, or other production deployment concerns require their own explicit contracts and proportionate executable fixtures. One PR should normally add one clear trust boundary, deployment topology, adoption boundary, installation boundary, or maintainer concern; it must not reopen the completed validator-consolidation transition.

## Documentation publication compatibility

Pull requests to `main` that change canonical Markdown, `docs/`, or `assets/` are assembled and built against the current `site` branch by **Check documentation site compatibility**. The pull-request run uses GitHub's proposed merge commit, records both exact source commits in the generated artifact, and never deploys it.

The same non-deploying check runs weekly and can be started manually to detect documentation drift. No workflow on `main` deploys GitHub Pages; publication is outside this branch's authority.

## Pull requests

Describe:

- the selected profile tags and behavior changed;
- the operational resource, interface, trust boundary, deployment topology, adoption boundary, installation boundary, or maintainer concern affected;
- the source-of-truth files changed;
- the runtime or dependency impact, or state that none applies;
- the tests and profile-aware validation executed;
- any compatibility, security, permission, portability, lifecycle, deployment, installation, or template-consumption implications;
- modes explicitly unsupported by the PR.
