---
name: composition
description: Create, inspect, update, upgrade, recover, and validate repositories with the immutable TakashiSasaki/templates Composition Composer.
---

# Composition

Use this as the single repository-facing entry point for the Composition Composer. Normal consumers do not clone `TakashiSasaki/templates` or any provider branch. The installed Skill acquires the selected immutable Composition revision as an HTTPS archive for each Composer invocation, verifies a snapshot inventory, executes it from an OS temporary directory, and removes that source snapshot on exit.

## Choose the operation

1. Resolve the intended consumer repository path.
2. Use `python scripts/run.py --repository <root> doctor` when you need a human-readable prerequisite/cache diagnosis before source or runtime acquisition. Use `doctor --format json` for machine-readable output.
3. Use `python scripts/run.py --repository <root> provenance` when you need to identify the installed Skill source, stable toolchain, selected execution source, consumer lock source, or recovery source.
4. Use `python scripts/run.py --repository <root> inspect` before mutation.
5. Use `plan` before `apply` for initial composition, update, or upgrade.
6. Use `validate` after a successful apply.
7. If inspect reports interrupted managed state, do not delete the transaction marker. Rerun the matching `apply --mode update` or `apply --mode upgrade`; the runner selects the transaction-pinned full SHA automatically.

## Consumer prerequisites

Normal consumer execution requires:

- CPython 3.11, 3.12, 3.13, or 3.14; and
- HTTPS access when the selected immutable source archive or Python packages must be acquired.

Normal consumers do **not** need Git, `git clone`, `curl`, `wget`, a templates checkout, a manually created virtual environment, or knowledge of the `site` / `composition` / `policy` branch topology. Git remains appropriate for Composition authority maintainers who deliberately run the Composer from a reviewed source checkout.

## Commands

To diagnose local runner prerequisites and runtime-cache write capability without downloading source or contacting package indexes:

```text
python scripts/run.py --repository <root> doctor
python scripts/run.py --repository <root> doctor --format json
```

`doctor` is repository-read-only and performs no network acquisition. It probes the effective persistent runtime-cache parent with the same transient write-plus-atomic-rename capability required by runtime construction, then removes probe artifacts. Source acquisition is reported as `ephemeral`: normal execution obtains a fresh full-SHA archive in an OS temporary directory rather than creating a persistent source cache. Doctor deliberately reports remote/package-source availability as `not-probed`; `READY` means only that locally observable prerequisites do not block the normal path.

To inspect provenance without source or runtime acquisition:

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

## Doctor versus validation

`doctor` answers whether the installed runner has locally observable prerequisites to run or acquire its selected immutable toolchain. It is not a Composer validation result and must not be used as a release/readiness proof. In particular:

- `status: ready` means supported local CPython and runtime-cache conditions do not currently block normal execution; it does not guarantee GitHub or package-index availability;
- `checks.git.status: not-required` is intentional for normal consumer execution;
- `checks.source_cache.status: ephemeral` means no persistent Composition source checkout is expected;
- runtime-cache state is only a performance/runtime-acquisition signal and never changes source selection or Composer semantics;
- `package_source.status: not-probed` is intentional because doctor performs no remote/package-index requests; and
- the canonical repository operation remains the exact `inspect`, `plan`, `apply`, or `validate` command selected by the runner, while materialized `.template-composition/validate.py` remains consumer validation authority after composition.

Use doctor to explain bootstrap failures, then execute the canonical command. Do not edit lock, transaction, installation-receipt, or runtime-cache markers to force a green report.

## Provenance and trust roles

`provenance` prints deterministic machine-readable JSON. The revision roles are intentionally separate and are not expected to share one SHA:

| Role | Authority | Meaning |
| --- | --- | --- |
| `skill_source` | `installation-receipt.json` | Immutable repository revision from which the installed Skill tree was acquired. The remote installer writes this receipt. A direct local/development copy reports `unrecorded` rather than guessing a revision. |
| `stable_toolchain` | `runtime-manifest.json` | Default immutable Composer source and runtime-lock identity selected by this Skill distribution. |
| `selected_toolchain` | transaction, explicit `--revision`, or stable manifest | Exact Composer source that this runner invocation would execute, using the same precedence as normal execution. |
| `consumer_lock` | `.template-composition/lock.json` | Source revision that materialized the currently managed consumer state. It is absent for an unmanaged repository. |
| `transaction` | `.template-composition/transaction.json` | Recovery source authority while an update or upgrade transaction is interrupted. |

An advanced `--revision <full-sha>` may be supplied with `provenance`, `doctor`, or normal Composer execution. A recovery transaction remains authoritative and rejects a conflicting explicit revision exactly as normal execution does.

## Immutable source selection

- The normal source revision is the full SHA in `runtime-manifest.json`.
- A managed recovery transaction overrides that default with the exact full SHA in `.template-composition/transaction.json`.
- An advanced `--revision <full-sha>` override is accepted only when no recovery transaction requires another revision.
- Mutable branch and tag names are never accepted as executable source identities.
- The canonical executable repository is always `TakashiSasaki/templates`.

## Source snapshot and runtime behavior

For the selected full SHA the runner:

1. downloads `https://codeload.github.com/TakashiSasaki/templates/tar.gz/<full-sha>` with Python's standard library;
2. rejects unsafe archive paths, symbolic/hard links, duplicate or portable-colliding paths, unsupported member types, and configured download/extraction/member-count limits;
3. extracts the immutable source into an OS temporary directory and records a SHA-256 inventory of every regular source file;
4. passes repository identity, full revision, and that inventory to the Composer as source-context metadata; Composer authority reads must remain inside the snapshot, be present in the inventory, and retain their acquired digest;
5. reads that snapshot revision's `requirements-runtime.lock` and, for the stable manifest revision, verifies the lock SHA-256 recorded in `runtime-manifest.json`;
6. derives a persistent runtime-cache identity from repository, revision, lock SHA-256, CPython major/minor version, and platform/machine;
7. reuses a matching runtime only after validating its marker, lock digest, Python/platform identity, `pip check`, and the source revision's runtime-environment verifier; otherwise it builds and atomically installs a fresh isolated runtime with dependency resolution and pip's download cache disabled;
8. executes the selected revision's `scripts/compose.py` with `--target` injected from runner `--repository`; and
9. removes the source snapshot/context temporary directory when the invocation exits normally or through a handled exception.

`COMPOSITION_RUNTIME_CACHE` may override the persistent runtime-cache root for controlled environments and tests. The default follows platform cache conventions under `composition/runner-v1`. Source snapshots are not stored there.

A normal Composer command therefore requires GitHub source-archive availability for each invocation, even when the Python runtime cache is warm. `doctor` and `provenance` remain network-free. A materialized consumer validator can be invoked independently according to the validation contract generated into the consumer repository.

Managed `update` / `upgrade` additionally verify that the selected new full SHA descends from the lock's old full SHA. Snapshot-backed consumer execution performs that revision-transition check with GitHub's compare API and fails closed on unavailable, malformed, rate-limited, or non-descendant results. Reviewed-checkout authority-maintainer execution may perform the same semantic check using local Git history.

## Filesystem hygiene

Intentional persistent state is limited to:

- the installed Composition Skill when the user chose to install it;
- the consumer repository material and `.template-composition/**` state produced by Composition; and
- the named validated Python runtime cache used as a performance optimization.

The selected templates source checkout is not consumer state. Normal execution treats it as disposable acquisition material and does not create a persistent clone or source cache. Temporary download/extraction/build staging is cleaned after normal completion and handled failures; an OS/process crash can still leave ordinary operating-system temporary artifacts and is not claimed to be transactionally erasable.

## Safety requirements

- Require only supported CPython for normal consumer bootstrap/runtime; do not introduce Git as a hidden consumer prerequisite.
- Execute only a full lowercase 40-character commit SHA from `TakashiSasaki/templates`.
- Reject unsafe archive structure and source bytes that differ from the acquisition inventory.
- Treat GitHub ancestry-verification failure as a managed-transition blocker rather than guessing history.
- Treat `.template-composition/transaction.json` as authoritative during recovery.
- Never silently fall back to the stable manifest revision when transaction metadata is malformed.
- Do not pass through a second Composer `--target`.
- Treat invalid runtime-cache entries as misses; never trust a cache marker alone.
- Treat a present but malformed installation receipt, consumer lock, transaction, or source-context document as an error rather than inventing provenance.
- Do not modify `.template-composition/lock.json` or transaction metadata outside the Composer.
- Treat doctor as diagnostic only; a ready doctor report does not replace `validate` or prove remote acquisition will succeed.
- Review plans before applying mutations.
