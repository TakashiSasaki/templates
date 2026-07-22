<!--
agent-policy-generated: true
source-skill: intake-validated-artifact
DO NOT EDIT DIRECTLY
-->
---
name: intake-validated-artifact
description: Validate and stage an externally supplied archive or source bundle without broadening its declared intent or activating it implicitly.
---

# Intake a validated artifact

Use this skill when a repository receives source, generated output, vendor content, a historical snapshot, or another external artifact whose bytes and intended use must be verified before application.

1. Read the repository instructions, the artifact contract, and the required verification command before downloading or writing files.
2. Record the expected source identity, destination baseline, artifact digest, declared file intents, allowed change surface, and stop conditions.
3. Confirm that the working state is clean or that every pre-existing change is understood and outside this operation.
4. Download archives, sidecars, reports, and extraction output into temporary storage outside the repository unless they are explicit deliverables.
5. Verify the transport digest before extraction. Treat this only as transport-integrity evidence.
6. Inspect archive entries before extraction and reject absolute paths, parent traversal, drive or UNC paths, unsafe symlinks, duplicate targets, and unsupported file types.
7. Extract into temporary storage and run the repository-authoritative schema and operational validator. Do not substitute a producer report for local validation.
8. Confirm that the validated source and destination baseline match the current task. Stop when the baseline cannot be verified or requires an owner decision.
9. Apply only entries whose declared intent authorizes installation or restoration. Do not install reference-only material or infer undeclared files.
10. Preserve exact bytes during staging and verify destination size and digest. Perform adaptation in a separate change unless it was explicitly authorized.
11. Add only the minimal dependency closure required by the accepted artifact. Preserve unrelated versions, scripts, and configuration.
12. Run focused checks and the repository's required verification. Keep repository-local, environment-dependent, remote CI, and independent-audit results separate.
13. Confirm that incidental archives, sidecars, extraction directories, and reports are absent from the final diff.
14. Do not publish, activate, deploy, or finalize unless those actions were separately authorized and their current preconditions were revalidated.

Stop without applying the artifact when a digest mismatches, an archive path is unsafe, validation fails, the destination conflicts, the baseline is stale or unverifiable, a required dependency is undeclared, a semantic decision is unresolved, or rollback ownership cannot be established.

Report the source claim, verified digests, validator results, exact files staged, dependency changes, checks by evidence layer, remaining uncertainty, rollback state, and whether adaptation or activation remains pending.
