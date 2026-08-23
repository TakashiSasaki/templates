# Release bundle lifecycle

`lifecycle.release-bundle` provides a deterministic provider-neutral handoff record for exact contract bytes associated with an approved release candidate.

Product mode binds the bundle subject to the same immutable revision as `release_evidence` and contains one digest entry for every active registered contract except the bundle document itself. Artifact order follows the generated contract manifest.

The bundle never digests itself. It does include `release_evidence`, closing the approved execution record without creating a self-reference cycle. Packaging, signing, attestation, encryption, archival, deployment, and artifact-store decisions remain product-owned.

## Managed producer

After approved revision-bound release evidence has been produced, generate the digest-closed handoff with:

```sh
python -I .template-composition/release/produce_release_bundle.py --revision <40-hex-revision>
```

The producer requires the named revision to equal repository `HEAD`. `contracts/release-evidence.json` and `contracts/release-bundle.json` are treated explicitly as lifecycle outputs, so either may differ from the candidate seed while all other tracked candidate bytes must still match the revision. This makes bundle generation safely rerunnable for the same approved candidate without requiring the user to restore the template bundle seed first.

At operation start the producer snapshots the exact current evidence and bundle bytes. It validates the approved evidence, derives artifact order from `contracts/manifest.json`, hashes the current bytes of every active registered contract except `release_bundle`, and chooses a generation timestamp strictly after the evidence generation timestamp. The approved evidence and pre-existing canonical bundle are required to remain unchanged while those inputs are collected.

After writing the new bundle, the producer re-verifies the repository with only the two declared lifecycle outputs excluded from the candidate byte comparison, confirms the approved evidence snapshot is still unchanged, and runs revision-bound bundle validation. Any abort, concurrent lifecycle-input change, or validation failure restores the exact bundle bytes present at operation start.

The producer itself disables Python bytecode writes so loading managed release helpers does not create new untracked repository state. This standalone producer intentionally does not rerun proof commands. A later orchestration layer may combine evidence and bundle production into one user-facing transaction while preserving these lifecycle boundaries.
