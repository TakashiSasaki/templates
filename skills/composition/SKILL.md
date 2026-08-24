---
name: composition
description: Create, inspect, update, upgrade, recover, and validate repositories with the immutable TakashiSasaki/templates Composition Composer.
---

# Composition

Use this as the single repository-facing entry point for the Composition Composer.

## Choose the operation

1. Resolve the intended consumer repository path.
2. Use `python scripts/run.py --repository <root> provenance` when you need to identify the installed Skill source, stable toolchain, selected execution source, consumer lock source, or recovery source.
3. Use `python scripts/run.py --repository <root> inspect` before mutation.
4. Use `plan` before `apply` for initial composition, update, or upgrade.
5. Use `validate` after a successful apply.
6. If inspect reports interrupted managed state, do not delete the transaction marker. Rerun the matching `apply --mode update` or `apply --mode upgrade`; the runner selects the transaction-pinned full SHA automatically.

## Commands

To inspect provenance without acquiring a source checkout or runtime:

```text
python scripts/run.py --repository <root> provenance
```

For a new repository:

```text
python scripts/run.py --repository <root> plan --config <composition.json>
python scripts/run.py --repository <root> apply --config <composition.json>
python scripts/run.py --repository <root> validate
```

For a managed update that preserves recorded intent:

```text
python scripts/run.py --repository <root> plan --mode update
python scripts/run.py --repository <root> apply --mode update
python scripts/run.py --repository <root> validate
```

For an explicit intent or compatibility-boundary change:

```text
python scripts/run.py --repository <root> plan --mode upgrade --config <composition.json>
python scripts/run.py --repository <root> apply --mode upgrade --config <composition.json>
python scripts/run.py --repository <root> validate
```

The runner owns the Composer target argument. Do not pass `--target`; use `--repository` on the runner.

## Provenance and trust roles

`provenance` prints deterministic machine-readable JSON. The revision roles are intentionally separate and are not expected to share one SHA:

| Role | Authority | Meaning |
| --- | --- | --- |
| `skill_source` | `installation-receipt.json` | Immutable repository revision from which the installed Skill tree was acquired. The remote installer writes this receipt. A direct local/development copy reports `unrecorded` rather than guessing a revision. |
| `stable_toolchain` | `runtime-manifest.json` | Default immutable Composer source and runtime-lock identity selected by this Skill distribution. |
| `selected_toolchain` | transaction, explicit `--revision`, or stable manifest | Exact Composer source that this runner invocation would execute, using the same precedence as normal execution. |
| `consumer_lock` | `.template-composition/lock.json` | Source revision that materialized the currently managed consumer state. It is absent for an unmanaged repository. |
| `transaction` | `.template-composition/transaction.json` | Recovery source authority while an update or upgrade transaction is interrupted. |

The output also reports whether the selected toolchain matches the stable toolchain and, when a consumer lock exists, whether the lock source matches the currently selected toolchain. These comparisons explain differences; they do not change source-selection semantics.

An advanced `--revision <full-sha>` may be supplied with `provenance` to inspect which source would be selected. A recovery transaction remains authoritative and rejects a conflicting explicit revision exactly as normal Composer execution does.

## Immutable source selection

- The normal source revision is the full SHA in `runtime-manifest.json`.
- A managed recovery transaction overrides that default with the exact full SHA in `.template-composition/transaction.json`.
- An advanced `--revision <full-sha>` override is accepted only when no recovery transaction requires another revision.
- Mutable branch and tag names are not accepted as executable source identities.
- The canonical executable repository is always `TakashiSasaki/templates`.

## Runtime behavior

The runner persistently caches source checkouts and isolated Python runtimes without changing source-selection or Composer semantics.

For the selected full SHA it:

1. reuses a validated source cache when available, otherwise fetches that exact revision from the canonical repository with Git and records it in a cache keyed by revision;
2. verifies the cached checkout is detached at the expected full SHA, has the canonical remote, is byte-clean, uses LF-preserving checkout settings, and retains traversable ancestor history;
3. reads that revision's `requirements-runtime.lock` and, for the stable manifest revision, verifies the lock SHA-256 recorded in `runtime-manifest.json`;
4. derives a runtime-cache identity from repository, revision, lock SHA-256, CPython major/minor version, and platform/machine;
5. reuses a matching runtime only after checking its marker, lock digest, Python/platform identity, `pip check`, and the source revision's runtime-environment verifier;
6. on a runtime miss or invalid entry, creates an isolated virtual environment, installs the exact lock with dependency resolution and pip's download cache disabled, validates it, and atomically installs the cache entry; and
7. executes the selected revision's `scripts/compose.py` with the runner repository injected as `--target`.

A valid source/runtime cache hit performs no network acquisition. `COMPOSITION_RUNTIME_CACHE` may override the cache root for controlled environments and tests. Otherwise platform cache conventions are used under a `composition/runner-v1` namespace.

A cache miss requires a writable cache parent with atomic rename support. The runner probes those capabilities before acquisition/build work. If the selected cache path cannot support them, the runner reports an actionable error naming the path and `COMPOSITION_RUNTIME_CACHE` instead of exposing a raw filesystem traceback. Runtime dependency installation uses `pip --no-cache-dir`, so changing `COMPOSITION_RUNTIME_CACHE` is sufficient; no separate pip/XDG cache override is required for the Composition runner.

Cache layout and reuse are performance details. Revision selection, Composer arguments, managed-recovery semantics, lock/transaction semantics, and material ownership remain authoritative outside the cache implementation.

## Safety requirements

- Require Git on `PATH` and CPython 3.11 through 3.14 for Composer execution.
- Execute only a full lowercase 40-character commit SHA from `TakashiSasaki/templates`.
- Treat `.template-composition/transaction.json` as authoritative during recovery.
- Never silently fall back to the stable manifest revision when transaction metadata is malformed.
- Do not pass through a second Composer `--target`.
- Treat invalid source/runtime cache entries as misses; never trust a cache marker alone.
- Treat a present but malformed installation receipt, consumer lock, or transaction as an error rather than inventing provenance.
- Do not modify `.template-composition/lock.json` or transaction metadata outside the Composer.
- Review plans before applying mutations.
