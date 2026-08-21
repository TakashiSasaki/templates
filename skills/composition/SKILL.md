---
name: composition
description: Create, inspect, update, upgrade, recover, and validate repositories with the immutable TakashiSasaki/templates Composition Composer.
---

# Composition

Use this as the single repository-facing entry point for the Composition Composer.

## Choose the operation

1. Resolve the intended consumer repository path.
2. Use `python scripts/run.py --repository <root> inspect` before mutation.
3. Use `plan` before `apply` for initial composition, update, or upgrade.
4. Use `validate` after a successful apply.
5. If inspect reports interrupted managed state, do not delete the transaction marker. Rerun the matching `apply --mode update` or `apply --mode upgrade`; the runner selects the transaction-pinned full SHA automatically.

## Commands

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
6. on a runtime miss or invalid entry, creates an isolated virtual environment, installs the exact lock with dependency resolution disabled, validates it, and atomically installs the cache entry; and
7. executes the selected revision's `scripts/compose.py` with the runner repository injected as `--target`.

A valid source/runtime cache hit performs no network acquisition. `COMPOSITION_RUNTIME_CACHE` may override the cache root for controlled environments and tests. Otherwise platform cache conventions are used under a `composition/runner-v1` namespace.

Cache layout and reuse are performance details. Revision selection, Composer arguments, managed-recovery semantics, lock/transaction semantics, and material ownership remain authoritative outside the cache implementation.

## Safety requirements

- Require Git on `PATH` and CPython 3.11 through 3.14.
- Execute only a full lowercase 40-character commit SHA from `TakashiSasaki/templates`.
- Treat `.template-composition/transaction.json` as authoritative during recovery.
- Never silently fall back to the stable manifest revision when transaction metadata is malformed.
- Do not pass through a second Composer `--target`.
- Treat invalid source/runtime cache entries as misses; never trust a cache marker alone.
- Do not modify `.template-composition/lock.json` or transaction metadata outside the Composer.
- Review plans before applying mutations.
