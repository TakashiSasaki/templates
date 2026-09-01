# agent-policy skill

This directory is the single installable agent skill for both repository onboarding and normal `agent-policy` operation.

The skill itself is a small stdlib bootstrap surface. It does not vendor the canonical policy implementation. The canonical CLI and policy engine remain in `src/agent_policy/` at the full commit SHA selected by the skill or by the managed repository's `.agent-policy.lock`.

## Entry points

- `scripts/bootstrap.py` — inspect and adopt an unmanaged repository. Fresh adoption may complete; migration adoption stops after prepare/preview and never finalizes.
- `scripts/run.py` — run normal `agent-policy` commands using the repository-pinned runtime when `.agent-policy.lock` exists.
- `scripts/runtime.py` — select immutable toolchain identity, construct/reuse the persistent runtime cache, and verify its distribution set.
- `scripts/install.py` / `scripts/uninstall.py` — atomically install or remove this skill directory.

## Pin selection

For an unmanaged repository, the runtime manifest provides the reviewed default full SHA. For a managed repository, `.agent-policy.lock` takes precedence. The lock must identify `TakashiSasaki/templates` and a full lowercase 40-character commit SHA. Invalid managed-repository pins fail closed; they do not fall back to the skill default.

`runtime-manifest.json` pins the default toolchain revision and the SHA-256 of that revision's `requirements-runtime.lock`.

## Persistent runtime identity

A runtime cache entry is identified by:

- toolchain repository;
- full toolchain revision;
- SHA-256 of `requirements-runtime.lock`;
- Python major/minor version; and
- platform plus machine architecture.

The default cache root is the platform cache directory (`$XDG_CACHE_HOME`/`~/.cache` on POSIX, `%LOCALAPPDATA%` on Windows). Set `AGENT_POLICY_RUNTIME_CACHE` to override it.

A valid cache entry is reused without network access and without requiring the cache root to be writable. On a cache miss, the runner first verifies that the selected cache root supports directory creation, file writes, cleanup, and same-filesystem atomic rename. If that preflight fails, the consumer-facing error names the cache path and instructs the user to set `AGENT_POLICY_RUNTIME_CACHE` to a writable directory.

The first build for a new identity downloads the runtime lock from the exact full SHA, installs every locked runtime distribution with dependency resolution disabled, installs the same full-SHA `agent-policy` project with dependencies disabled, runs `pip check`, verifies the exact installed distribution set, and writes an identity marker only after validation succeeds. Both pip installation steps use `--no-cache-dir`, so `AGENT_POLICY_RUNTIME_CACHE` is sufficient for controlled or restricted environments; no separate pip cache or XDG cache override is required.

Construction occurs in a sibling staging directory and is renamed into place only after validation. Existing invalid entries are replaced with rollback protection.

For a repository pin different from the skill default, an already validated cache entry for that revision can be reused offline. If no matching entry exists, the exact revision's runtime lock must be fetched once to determine its lock digest and build its runtime.

## Immutable remote installation

Remote installation is supported through a separately published immutable installer. The exact installer command and the current installer-script and skill-source full SHAs are publication metadata, so they are deliberately not embedded in this installed README.

In the source repository, use the current repository-level installation documentation (`README.md`, `docs/getting-started.md`, or `docs/bootstrap.md`) together with `release/skill-installer.json` to identify the published installer. A published command must execute `scripts/install_agent_policy_skill.py` from the descriptor's full immutable installer revision, never from `policy`, a tag, a short SHA, or another mutable reference.

The remote bootstrap downloads only the exact full-SHA archive selected by the published installer, extracts only `skills/agent-policy/`, rejects unsafe archive members, and delegates final target replacement to this directory's `scripts/install.py`.

The distribution deliberately separates three revision roles:

- the **installer script revision** identifies the remotely executed installer and is published outside this installed skill tree;
- the **skill source revision** is embedded by that installer and identifies the downloaded skill tree; and
- the **stable runtime revision** is the independent full SHA in `runtime-manifest.json` used to execute the canonical CLI.

### Installation provenance for trusted automated review

Normal repository-management use does not require a persistent installation attestation. A deployment that intends to use this installed Skill as the trusted bootstrap authority for automated pull-request review has a stronger requirement: it must preserve independent evidence for the complete installed Skill-source tree before those bytes are allowed to select `pr-review`.

Such a deployment executes the remote installer from an independently pinned full-SHA URL and supplies that same trusted installer revision together with a deployment-managed attestation path outside the installed Skill tree:

```text
python <pinned-installer.py> /path/to/agent-policy \
  --installer-revision <pinned-installer-full-sha> \
  --attestation /protected/deployment-state/agent-policy-installation.json
```

The installer writes a deterministic record binding the installer repository/full SHA, embedded Skill-source repository/full SHA, exact installed root, and a **closed path/type inventory of the complete installed Skill tree**, with a SHA-256 digest for every regular file. Verification recomputes the whole tree and requires exact equality. Added or missing files/directories, file↔directory substitutions, symbolic/hard links, or changed bytes therefore invalidate the installation; an unattested import-shadowing file cannot be tolerated merely because the originally attested files are unchanged.

The attestation is not review authority merely because it exists. The deployment must keep it under an independently trusted/protected state boundary and must already trust the installer SHA used to create or verify it. The installer preflights the attestation destination before downloading or replacing the Skill, so a structurally invalid or non-writable protected-state destination fails before the Skill installation is mutated.

Before automated-review bootstrap, the deployment re-fetches or otherwise authenticates the same exact-SHA installer script and verifies the installed tree without reinstalling:

```text
python <pinned-installer.py> /path/to/agent-policy \
  --installer-revision <pinned-installer-full-sha> \
  --attestation /protected/deployment-state/agent-policy-installation.json \
  --verify-only
```

Verification is read-only with respect to the installed Skill and does not download or install runtime material. It uses streaming SHA-256 and enforces the Skill distribution size limit while recomputing the closed tree inventory. A missing, mismatched, linked, oversized, or otherwise tampered installation fails this verification. `runtime-manifest.json` remains a separate runtime-selection contract and cannot substitute for Skill-source installation provenance.

## Installation during repository development

A reviewed checkout can install the skill tree from that checkout:

```text
python skills/agent-policy/scripts/install.py /path/to/agent-skills/agent-policy
```

Use `--replace` only when the existing destination is already an `agent-policy` skill installation.

This local-checkout path is intended for repository development and review. It installs the checkout's current `skills/agent-policy/` subtree and therefore is not necessarily byte-for-byte identical to the currently published remote distribution unless the checkout matches the skill-source revision recorded by the publication descriptor. A local-checkout installation is not eligible as trusted automated-review bootstrap merely because its runtime manifest is valid; it needs the independently authenticated deployment installation provenance described above.
