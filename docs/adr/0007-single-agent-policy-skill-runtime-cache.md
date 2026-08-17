# ADR-0007: Use one agent-policy skill with a persistent immutable runtime cache

- Status: Accepted
- Date: 2026-08-17
- Supersedes: ADR-0004

## Context

ADR-0004 integrated a separately installed `bootstrap-agent-policy` trust-seed skill into the `policy` branch. That design kept onboarding safe, but it exposed two repository-facing concepts for one toolchain lifecycle: a bootstrap skill before adoption and normal `agent-policy` operation afterward. It also created a temporary virtual environment for repeated bootstrap/toolchain use rather than sharing a validated persistent runtime.

The policy implementation itself is already centralized in `src/agent_policy/`, and onboarding is already modeled as one public adoption operation with fresh and migration strategies selected from repository state. Maintaining a separate bootstrap skill therefore adds conceptual and operational duplication without adding a distinct policy authority.

A managed repository also already records an immutable toolchain revision in `.agent-policy.lock`. The installed repository-facing skill can use that pin directly instead of requiring a second installation or a mutable global toolchain.

## Decision

Maintain one installable repository-facing skill at `skills/agent-policy/` for both unmanaged onboarding and managed operation.

The skill is an immutable runtime selector and orchestrator, not a second implementation of policy mechanics. Canonical CLI, schema, rendering, adoption, and lock behavior remain in `src/agent_policy/`.

### Bootstrap operation

For an unmanaged repository, `scripts/bootstrap.py` uses read-only inspection to derive the adoption strategy:

- `unmanaged-empty` selects fresh adoption;
- `unmanaged-existing` selects migration adoption;
- `managed` exits bootstrap and transfers normal operation to `scripts/run.py`;
- `inconsistent` refuses mutation.

Fresh adoption may use the hidden `init` primitive internally. Migration bootstrap may prepare and preview only. Neither `runtime-manifest.json` nor the bootstrap orchestration exposes a finalize route. Migration finalization remains a separate explicit managed command.

### Managed operation

For a managed repository, `scripts/run.py` reads `.agent-policy.lock` and requires `TakashiSasaki/templates` at a full lowercase 40-character commit SHA. A malformed, mutable, or unsupported managed pin fails closed; it is not replaced by the skill's default stable pin.

### Stable skill trust anchor

`skills/agent-policy/runtime-manifest.json` replaces the old bootstrap manifest as the skill-side stable trust anchor. It records:

- the stable `TakashiSasaki/templates` full commit SHA;
- the path and SHA-256 of that revision's `requirements-runtime.lock`;
- stable project distribution/executable metadata; and
- the closed bootstrap route set.

`release/toolchain.json` and the runtime manifest must carry the same stable toolchain object. Release verification extracts the pinned stable tree and confirms the recorded runtime-lock digest against that tree.

### Persistent runtime cache

A validated runtime cache entry is identified by:

- toolchain repository and full commit SHA;
- SHA-256 of `requirements-runtime.lock`;
- Python major/minor version; and
- platform plus machine architecture.

A valid cache hit is reusable without network access. A cache miss is constructed in a sibling staging directory with inherited Python/pip package-selection inputs removed. The exact runtime lock is installed with dependency resolution disabled, the exact full-SHA project is installed with dependencies disabled, `pip check` and exact installed-set verification run, and the cache marker is written only after successful verification. The staging directory is then atomically renamed into the cache identity with rollback protection.

For the stable default, the runtime-lock digest is already present in `runtime-manifest.json`, so a valid cache can be recognized before network access. For another full SHA selected by a managed repository, an already validated cache for that revision/Python/platform may be reused offline; otherwise that revision's runtime lock is fetched once to derive the cache identity.

## Release and consumer boundaries

Stable release promotion and consumer pin movement remain separate operations. A candidate commit is reviewed first; a later promotion change records the candidate SHA and matching runtime-lock digest. Existing managed repositories are not rewritten by promotion and continue to follow their own `.agent-policy.lock` pins until a separately reviewed consumer update.

## Consequences

- Users and agents have one repository-facing skill before and after adoption.
- The separate `skills/bootstrap-agent-policy/` package and bootstrap manifest are removed.
- Fresh and migration adoption remain state-derived strategies of one public adoption operation.
- Migration finalization retains separate explicit authorization.
- Repeated operations reuse a validated runtime instead of rebuilding a temporary environment every time.
- Runtime identity is immutable and environment-specific, so incompatible Python/platform/runtime-lock combinations do not share cache entries.
- The runtime cache is derived execution state, not policy authority; authoritative inputs remain the full commit SHA, runtime-lock digest, and managed repository lock.
- One-line remote installation is a separate distribution concern and may be added without changing this runtime or trust model.
