# Release bundle lifecycle

`lifecycle.release-bundle` provides a deterministic provider-neutral handoff record for exact contract bytes associated with an approved release candidate.

Product mode binds the bundle subject to the same immutable revision as `release_evidence` and contains one digest entry for every active registered contract except the bundle document itself. Artifact order follows the generated contract manifest.

The bundle never digests itself. It does include `release_evidence`, closing the approved execution record without creating a self-reference cycle. Packaging, signing, attestation, encryption, archival, deployment, and artifact-store decisions remain product-owned.
