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

A valid cache entry is reused without network access. The first build for a new identity downloads the runtime lock from the exact full SHA, installs every locked runtime distribution with dependency resolution disabled, installs the same full-SHA `agent-policy` project with dependencies disabled, runs `pip check`, verifies the exact installed distribution set, and writes an identity marker only after validation succeeds.

Construction occurs in a sibling staging directory and is renamed into place only after validation. Existing invalid entries are replaced with rollback protection.

For a repository pin different from the skill default, an already validated cache entry for that revision can be reused offline. If no matching entry exists, the exact revision's runtime lock must be fetched once to determine its lock digest and build its runtime.

## Installation during repository development

From a reviewed checkout:

```text
python skills/agent-policy/scripts/install.py /path/to/agent-skills/agent-policy
```

Use `--replace` only when the existing destination is already an `agent-policy` skill installation. One-line remote installation is intentionally handled by the follow-up installer work rather than by this runtime-consolidation change.
