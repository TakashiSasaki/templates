---
description: Describes shared policy and operating boundaries for safely receiving, validating, and staging external archives, historical source, vendor bundles, generated artifacts, and similar material.
---

# External artifact intake policy profile

The `external-artifact-intake` profile applies when artifacts are received from another repository, an external generation process, a distribution archive, a historical snapshot, a vendor bundle, or a similar source and are introduced into a destination repository.

This profile is not implicitly included in `core`. Product repositories that handle external artifacts select it explicitly in `.agent-policy.yml`.

```yaml
profiles:
  - core
  - external-artifact-intake
```

## Included rules

| Rule ID | Summary |
|---|---|
| `artifacts.distinguish-provenance-integrity` | Treat provenance claims, transfer integrity, source authenticity, and source-set completeness as separate claims. |
| `artifacts.validate-before-use` | Validate metadata and schema first, then inspect paths, symlinks, file types, sizes, and digests. |
| `artifacts.apply-declared-intent-only` | Do not install, activate, or reconstruct an artifact beyond its declared intended use. |
| `artifacts.separate-staging-adaptation-activation` | Treat exact-byte staging, destination adaptation, and runtime activation as separate changes. |
| `artifacts.isolate-transport-material` | Keep archives, sidecars, extraction trees, and reports out of the normal product diff. |
| `artifacts.minimize-dependency-closure` | Do not make the source manifest authoritative for the destination; add only the minimum required dependencies. |

## Keep evidence claims distinct

External-artifact validation requires separating claims that are related but not equivalent.

```text
recorded repository, revision, and URL
  → provenance claim

matching archive SHA-256
  → transfer integrity of the archive bytes that were checked

match to a source-system blob ID or signature
  → byte identity or authenticity relative to that source object

validation of files listed in a manifest
  → internal consistency of the listed set
```

None of these claims alone proves that the complete source repository has been captured. A bounded packet, reference bundle, or selective restore set must be treated and described as bounded.

## Validation order

Validate declared structure before using artifact-controlled paths. The standard order is:

1. Confirm source identity, destination baseline, expected digest, and declared intent.
2. Acquire the archive into a temporary area outside the repository.
3. Verify the transfer digest.
4. Inspect archive entries before extraction.
5. Extract into a temporary area.
6. Run repository-authoritative schema and operational validators.
7. Validate containment, regular-file status, symlinks, sizes, digests, and duplicate destinations.
8. Apply only entries permitted by the declared intent.
9. Validate destination bytes and the dependency diff.
10. Run required repository verification and confirm that transport material is absent from the final diff.

A producer-supplied validation report can be useful evidence, but it does not replace execution of the destination repository's authoritative validators.

## Staging, adaptation, and activation

When staging exact historical source or signed artifacts, do not edit the source until byte-for-byte identity has been checked. Import-path changes, formatting, compatibility wrappers, dependency additions, route wiring, and runtime activation are changes distinct from staging.

```text
transfer validation
  → exact-byte staging
  → destination adaptation
  → runtime activation
  → publish or deploy
```

Each stage has its own scope and evidence. A PASS at one stage does not implicitly authorize the next.

## Operational skills

Repositories that need them may select these skills together with this profile:

```yaml
skills:
  enabled:
    - validate-agent-policy
    - intake-validated-artifact
    - audit-frozen-change
```

`intake-validated-artifact` provides a standard process from download and archive inspection through authoritative validation, declared-intent application, dependency review, and transport cleanup.

`audit-frozen-change` provides stopping conditions for evaluating regression and evidence against an agreed acceptance baseline without inventing new gates during the audit.

## Boundary with product-specific policy

The following belong in product-repository project policy, schemas, validators, tests, or CI rather than in the shared profile:

- concrete manifest fields and versions;
- concrete disposition or action enums;
- allowed source repositories and destination paths;
- the method used to obtain a baseline revision;
- archive formats, size limits, and signature formats;
- file mappings, dependency policy, and activation gates;
- product-specific database, runtime, and migration prohibitions; and
- the concrete acceptance-report format.

Do not use natural-language shared policy as a substitute for an artifact contract. Enforce verifiable requirements in destination-repository validators and CI.
