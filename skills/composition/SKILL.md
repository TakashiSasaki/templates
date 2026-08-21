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

This MVP intentionally uses transient source and Python runtime directories. Each invocation:

1. fetches the selected full SHA from the canonical repository with Git;
2. checks out that revision detached;
3. reads that revision's `requirements-runtime.lock`;
4. for the stable manifest revision, verifies the lock SHA-256 recorded in `runtime-manifest.json`;
5. creates an isolated virtual environment;
6. installs the exact lock with dependency resolution disabled;
7. runs `pip check` and the source revision's runtime-environment verifier; and
8. executes that revision's `scripts/compose.py` with the runner repository injected as `--target`.

The transient implementation is a performance characteristic, not part of the semantic command contract. A later persistent runtime/source cache may replace repeated construction without changing revision selection, Composer arguments, or managed-recovery semantics.

## Safety requirements

- Require Git on `PATH` and CPython 3.11 through 3.14.
- Execute only a full lowercase 40-character commit SHA from `TakashiSasaki/templates`.
- Treat `.template-composition/transaction.json` as authoritative during recovery.
- Never silently fall back to the stable manifest revision when transaction metadata is malformed.
- Do not pass through a second Composer `--target`.
- Do not modify `.template-composition/lock.json` or transaction metadata outside the Composer.
- Review plans before applying mutations.
