<!--
agent-policy-generated: true
source-skill: pr-review
DO NOT EDIT DIRECTLY
-->
# Build, provenance, and CI

This is a **provider-neutral procedure-support reference** for `pr-review`. It supports candidate discovery and falsification; semantic policy remains authoritative for trusted evidence, generated artifacts, dependencies, and CI conclusions.

## Trigger

Use this domain when trusted bytes, generated outputs, dependencies, build/runtime selection, workflow/configuration changes, tests, signatures/digests, release descriptors, or CI evidence establish correctness or provenance.

## State and authority model

Model source authority, dependency/runtime identity, generation/build steps, trusted inputs, produced artifacts, integrity/provenance bindings, exact revision covered by evidence, and the consumer that later uses the result.

## Candidate seeds

Generate candidates when:

- generated/derived artifacts can diverge from canonical source without detection;
- mutable references or ambient environment select dependencies/runtime/tooling used as trusted evidence;
- untrusted proposed-head content can redefine the procedure or authority used to evaluate itself;
- CI success covers a different revision, configuration, generated state, platform, or execution path than the reviewed behavior;
- test/workflow changes weaken or bypass an existing regression/security/compatibility guard;
- a build or validation step executes lower-trust content before required provenance/integrity checks;
- publication/release metadata can claim a different artifact identity than the bytes actually produced.

A seed is not a finding.

## Falsification evidence

Trace exact revision and artifact bindings, immutable identities, lock/digest/signature verification, clean-environment behavior, generator reproducibility, workflow applicability, test reachability, and trusted-bootstrap boundaries. Discard candidates when the alleged mismatch is prevented or when the changed evidence still proves the required behavior for the exact reviewed state.

## Closure

Close this domain only after the reviewer can explain which exact source/runtime/artifact identities produced each relied-upon result and why CI/build/provenance evidence applies to the exact behavior and revision under review.