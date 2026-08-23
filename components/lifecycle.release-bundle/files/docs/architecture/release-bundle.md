# Release bundle lifecycle

`lifecycle.release-bundle` provides a deterministic provider-neutral handoff record for exact contract bytes associated with an approved release candidate.

Product mode binds the bundle subject to the same immutable revision as `release_evidence` and contains one digest entry for every active registered contract except the bundle document itself. Artifact order follows the generated contract manifest.

The bundle never digests itself. It does include `release_evidence`, closing the approved execution record without creating a self-reference cycle. Packaging, signing, attestation, encryption, archival, deployment, and artifact-store decisions remain product-owned.

## Managed release orchestration

For the normal product release path, execute proof commands, produce revision-bound release evidence, and publish the digest-closed bundle as one recoverable operation:

```sh
python -I .template-composition/release/produce_release.py --revision <40-hex-revision>
```

The orchestrator acquires the shared repository-local release lifecycle lock before recovery or mutation. It snapshots the exact pre-operation `contracts/release-evidence.json` and `contracts/release-bundle.json` bytes into `.git`-local backups, makes those backups durable, and then publishes a durable transaction marker before invoking either producer's already-locked primitive. It never invokes the standalone producer CLIs while holding the lock, so it does not recursively acquire the same lock.

The evidence stage executes the product-owned fixed argv and performs exact-candidate and revision-bound evidence validation. Only after that succeeds does the bundle stage digest the approved evidence and all other active registered contracts. Before the transaction marker is removed, both canonical outputs are fsynced. Removing the durable marker is the transaction commit point; backup files remaining after that point are non-authoritative cleanup state and are removed on the current or next invocation.

If either stage fails or the process is interrupted while Python can still run cleanup, both lifecycle outputs are restored to their exact pre-operation bytes before the lock is released. If the process is killed or the machine stops after the marker became durable, the next invocation detects the marker and restores both outputs from digest-verified backups before doing any new release work. Recovery can also be requested without running proofs:

```sh
python -I .template-composition/release/produce_release.py --recover-only
```

A transaction marker is authoritative only while present. Orphan backup or marker-temporary files without a transaction marker are safe to remove because lifecycle output mutation begins only after the complete marker has been atomically published. Malformed markers, missing backups, backup digest mismatches, symbolic transaction files, and unsafe canonical output paths fail closed rather than guessing a recovery state.

The transaction state lives under `.git` and is therefore outside the candidate worktree byte claim. The orchestrator still relies on the existing exact-candidate verifier for product inputs and on the shared lifecycle lock for cooperating producer serialization; the transaction files do not broaden either trust boundary.

## Standalone bundle producer

After approved revision-bound release evidence has already been produced, the bundle stage can still be invoked independently:

```sh
python -I .template-composition/release/produce_release_bundle.py --revision <40-hex-revision>
```

Before snapshotting release lifecycle outputs, the producer acquires the same repository-local shared lifecycle lock used by release-evidence production. It holds that lock through evidence validation, digest collection, bundle publication, revision-bound validation, and rollback. Cooperating evidence and bundle producers therefore serialize the complete lifecycle critical section rather than racing over the canonical evidence or bundle files.

The producer requires the named revision to equal repository `HEAD`. `contracts/release-evidence.json` and `contracts/release-bundle.json` are treated explicitly as lifecycle outputs, so either may differ from the candidate seed while all other tracked candidate bytes must still match the revision. This makes bundle generation safely rerunnable for the same approved candidate without requiring the user to restore the template bundle seed first.

Once locked, the producer snapshots the exact current evidence and bundle bytes. It validates the approved evidence, derives artifact order from `contracts/manifest.json`, hashes the current bytes of every active registered contract except `release_bundle`, and chooses a generation timestamp strictly after the evidence generation timestamp. The approved evidence and pre-existing canonical bundle are required to remain unchanged while those inputs are collected.

After writing the new bundle, the producer re-verifies the repository with only the two declared lifecycle outputs excluded from the candidate byte comparison, confirms the approved evidence snapshot is still unchanged, and runs revision-bound bundle validation. Any abort, unexpected lifecycle-input change, or validation failure restores the exact bundle bytes present at operation start before releasing the shared lifecycle lock.

The standalone producer disables Python bytecode writes so loading managed release helpers does not create new untracked repository state. It intentionally does not rerun proof commands; use `produce_release.py` when evidence and bundle publication should form one recoverable user-facing operation.
