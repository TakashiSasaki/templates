# ADR-0008: Separate review authority from GitHub runtime integration

- Status: Accepted
- Date: 2026-09-02
- Superseded in part by: ADR-0009

> Partial supersession. ADR-0009 is the current authority for review-result representation, including dual semantic/adapter output binding, mandatory adapter renderer/projection identity, and serialization-defined final stability. The trust and provenance machinery remains current. Read ADR-0009 before implementing review output binding or final review completion.

## Context

ADR-0005 established one canonical policy authority and requires generated instructions to remain projections rather than competing handwritten authorities. Shared review semantics already live in `policy/review/*.md`, selected through `profiles/review.yml` and configured review contexts.

The current GitHub-facing generated review document combines semantic review rules with GitHub-specific transport requirements. Recent design work also produced revised Review Guidelines and a revised automated pull-request review prompt outside the repository. Those external documents are not immutable repository authorities, so this migration freezes the complete accepted statement-level input baseline in `docs/review-guidance-inputs.md` and classifies that baseline into existing policy, genuinely missing semantic policy, review procedure, adapter concerns, or explanation.

The migration must also prevent proposed-head content, mutable local caches, writable repository snapshots, and post-verification filesystem races from selecting or changing the policy or procedure used to review a pull request.

## Decision

Automated pull-request review has five responsibility layers:

1. **Semantic review policy** — reviewer-independent obligations and admissibility rules.
2. **Trusted procedure bootstrap** — establishes immutable review-procedure provenance before review execution begins.
3. **Review procedure** — gathers evidence and applies the selected semantic review context.
4. **Platform adapter** — serializes an established semantic result for one provider or protocol.
5. **Platform runtime integration** — files whose location or execution semantics are imposed by the hosting platform.

Each normative requirement has one authority. A lower layer may consume a higher-layer result but may not redefine it.

### Semantic review policy

Canonical review semantics remain atomic modules under `policy/review/*.md`, composed with reusable `policy/core/*` and `policy/security/*` modules through a configured review context.

The frozen inputs in `docs/review-guidance-inputs.md` are migration evidence, not policy. Existing canonical rules are reused whenever they already own a requirement. New semantic modules are created only for genuinely missing, engine- and provider-neutral obligations. GitHub event names, line-side vocabulary, JSON fields, model names, confidence serialization, and similar transport details do not belong in semantic policy.

### Common immutable-execution and authority-input invariant

Every executable authority used by trusted automated review follows the same order:

1. materialize candidate bytes in deployment-managed private staging that repository-controlled and other untrusted review processes cannot modify;
2. establish the deployment's immutable/read-only execution boundary for that candidate;
3. **after immutability is established**, verify the frozen candidate's complete closed path/type inventory and every regular-file digest against independently established expected evidence; and
4. only after successful verification publish the frozen candidate to the next trust layer or execute it.

The same principle applies to repository bytes that define review authority even when those bytes are not executable. A writable checkout or snapshot is only a source candidate. Before configuration, lock, semantic policy, generated procedure, or generated projection bytes can act as authority, trusted bootstrap materializes the exact base commit/tree or the complete closed authority closure required by the review into deployment-private storage, establishes immutability, verifies the already-frozen bytes and path identities against the exact base Git tree/object identities, and only then permits authority reads from that frozen review-run trusted-base snapshot. A later digest check against a mutable source does not satisfy this invariant.

Verification followed by a later freeze is insufficient because bytes can change between the two operations. A read-only directory mode alone is also insufficient when writable aliases, hard links, symlink targets, or another process with equivalent write authority can still change backing bytes. Trusted artifacts therefore use independent regular files, reject symbolic and hard links, require no writable backing aliases within the declared trust model, and are verified only after the deployment immutability boundary is active. An equivalent content-addressed or immutable object-store representation is acceptable only when every later authority read is guaranteed to consume those exact verified bytes.

### Trusted procedure bootstrap

An unverified `pr-review` Skill must never select or authenticate its own executable authority, and an unauthenticated installed `agent-policy` Skill must not be assumed trustworthy merely because it is outside the pull-request head.

For the current architecture there is **exactly one repository-facing bootstrap path**: an installed `agent-policy` Skill whose installation identity is authenticated by the deployment and whose executable review-run image is frozen and verified before use. No repository-policy-root override, procedure/toolchain override, alternate loader, or other out-of-band review-authority path is part of this repository contract.

The bootstrap Skill has two distinct identities that must not be collapsed:

- **Skill-source identity** covers the installed `skills/agent-policy` tree containing the bootstrap algorithm itself.
- **Runtime identity** covers the lock-selected canonical `agent-policy` toolchain and dependency environment that executes repository checks and reproduction.

Before any bootstrap instruction or executable from the installed Skill is trusted, the hosting/deployment dispatcher must verify the installed Skill tree against a **deployment-managed installation attestation stored outside the installed Skill tree and outside the repository under review**. That attestation records the immutable installer repository/full-SHA revision, immutable Skill-source repository/full-SHA revision, exact installed root, and a closed inventory of every installed Skill-tree path and its type, with a cryptographic digest for every regular file. Missing paths, additional paths, type substitutions, symbolic/hard links, or digest mismatches fail closed. The installer and Skill-source identities match independently trusted deployment pins established before the review invocation; neither pull-request base nor head may select or rewrite those pins.

The writable installation is only a source candidate. The dispatcher copies only attested regular-file bytes into private deployment staging, rejects links and aliases, establishes an immutable/read-only **review-run bootstrap image**, and then verifies the already-frozen image against the same closed installation attestation. Only that frozen, post-freeze-verified image is exposed to the review executor. The writable installation is never an execution source for trusted review.

Bootstrap execution also avoids self-mutation. Python bytecode writes are disabled (for example, interpreter `-B` / `PYTHONDONTWRITEBYTECODE=1`) and writable logs, temporary files, state, and caches remain outside the frozen bootstrap image. Those controls supplement but do not replace the freeze-before-verify invariant.

### Lock-selected runtime provenance

A persistent runtime cache is a performance cache, not review authority. Cache metadata, an executable path, a runtime revision string, or a dependency-lock digest does not authenticate mutable cached package/executable bytes.

For trusted review, the lock-selected runtime must therefore have deployment-managed provenance separate from the mutable cache. A trusted runtime attestation binds at least:

- toolchain repository and exact full-SHA revision;
- exact `requirements-runtime.lock` digest;
- Python/platform runtime identity used by the existing runtime contract;
- the validated installed distribution set; and
- a closed path/type inventory with cryptographic digest for every regular file in the executable runtime tree.

The attestation is created only from a canonical runtime construction performed by the authenticated bootstrap path from the exact lock-selected revision and dependency lock, after the existing dependency/distribution validation succeeds, and is stored under deployment-managed state outside the mutable runtime cache and reviewed repository. A pre-existing mutable cache entry without matching protected runtime attestation is not eligible as trusted-review runtime merely because normal repository-management operation can reuse it.

For each trusted review run, a mutable cache entry may at most be a copy source. The deployment materializes independent regular-file runtime bytes into private staging, establishes an immutable/read-only **review-run runtime image**, and only then verifies the frozen image's complete inventory/digests plus runtime identity against the protected runtime attestation. The authenticated bootstrap invokes the managed `agent-policy` CLI only from this frozen, post-freeze-verified runtime image. Runtime mutation or inability to establish this image fails closed.

`runtime-manifest.json` remains responsible for runtime selection; it does not authenticate bootstrap Skill-source bytes or substitute for the runtime-tree attestation required by trusted review.

### Repository-bound bootstrap

Before `pr-review` executes, trusted bootstrap must:

1. authenticate the installed `agent-policy` Skill source against its external closed-tree installation attestation;
2. materialize the bootstrap run image privately, establish deployment immutability, and then verify the frozen image against that attestation;
3. obtain and record stable repository identity and pull-request identity from the hosting/repository system;
4. obtain the exact current target/base commit and tree identity from that system;
5. materialize the exact base tree, or a closed authority closure containing every base-side path that can influence review authority, into deployment-private storage; establish immutability; verify the already-frozen path/object/digest inventory against the exact base Git tree; and use only that **review-run trusted-base snapshot** as the active repository-policy root. A normal writable checkout is never an authority root;
6. read the frozen base's valid `.agent-policy.lock`, require repository/full-SHA agreement with `.agent-policy.yml`, and require the trusted configuration to enable `pr-review` through `skills.enabled`;
7. establish the lock-selected trusted-review runtime attestation, materialize a private runtime candidate, freeze it, verify the already-frozen runtime image against that protected attestation, and execute managed `agent-policy` checks only from that image;
8. require the managed `check` operation against the frozen trusted-base snapshot to succeed, establishing configuration, lock, policy-input, generated-output, and reproduction coherence;
9. require `.agents/skills/pr-review/SKILL.md` and every declared `pr-review` reference in the frozen trusted-base snapshot to resolve lexically inside that root, remain inside the generated `pr-review` tree, contain no parent traversal or reserved namespace, have no symlink component at any path level, end in regular non-link files, and reproduce under the lock-selected verified runtime;
10. use those frozen trusted-base generated paths only as verification sources. Materialize independent regular-file copies of the reproduced Skill and every declared reference into private deployment staging, reject symbolic links, hard links, missing/extra paths, path-type substitutions, and writable aliases, then establish an immutable/read-only **review-run procedure bundle**;
11. after the procedure bundle is frozen, verify its closed inventory and file digests against the exact reproduced trusted-base bytes and lock output digests, record the lock-selected procedure revision plus bundle identity/digests, and hand only that verified immutable bundle to the review executor.

A mutable branch/tag, writable repository checkout, unauthenticated installed Skill, unverified repository-local Skill, mutable persistent runtime cache, or any `agent-policy`/`pr-review` bytes from the proposed head must never participate as review authority for the same review. If any required protected attestation, frozen trusted-base snapshot, frozen image/bundle, post-freeze verification, lock/config agreement, Skill enablement, or reproduction check cannot be established, trusted automated review is unavailable and fails closed.

Trusted bootstrap is not a second review procedure. It may establish installation/bootstrap-image identity, runtime-image identity, repository and pull-request identity, exact base commit/tree and frozen trusted-base identity, configuration/lock validity, procedure-bundle identity/provenance, and handoff evidence only. It must not inspect the proposed change for findings, classify CI or review evidence, choose provider events, decide review completeness, or authorize merge.

### Review procedure

After trusted bootstrap hands control to the frozen and verified `pr-review` procedure bundle, that bundle is the **sole procedural authority for review execution**. It consumes bootstrap evidence but does not retroactively select or authenticate itself. Every Skill/reference byte used during the run is consumed from that immutable bundle; repository-local procedure paths and mutable runtime-cache procedure copies are never reopened after handoff.

At review start the procedure records and verifies:

- stable repository identity matching bootstrap evidence;
- pull-request identity matching bootstrap evidence;
- exact current target/base revision and tree identity matching the frozen trusted repository-policy root;
- exact proposed head revision; and
- the complete set of best common ancestors between base and head.

The best-common-ancestor set must contain exactly one revision. That unique merge base defines the PR-introduced changed surface as **merge-base → proposed head**. Unrelated histories and multiple-best-base/criss-cross histories fail closed; the procedure does not select an arbitrary base or synthesize an unspecified virtual base.

The procedure inspects the complete changed surface plus enough callers, callees, schemas, configuration, tests, CI definitions, migrations, generated artifacts, and normative repository context to establish real behavior when required by semantic policy. Finding causality and changed-location requirements remain semantic-policy concerns.

The Skill references semantic policy rather than copying severity, compatibility, security-impact, confidence, or finding-admissibility definitions.

The retained canonical automated-review prompt is only a thin non-normative invocation surface. It supplies repository/PR identity and output-binding inputs and directs the authenticated trusted bootstrap to the verified procedure bundle. It is neither bootstrap authority nor review procedure. If it conflicts with bootstrap or the verified procedure bundle, bootstrap governs executable provenance and the bundle governs review execution.

### Trusted review authority root and stability

The frozen review-run trusted-base snapshot established by trusted bootstrap, verified against the exact current base commit/tree, is the **only active repository-policy root** for the review. Proposed-head changes to `.agent-policy.yml`, `.agent-policy.lock`, policy modules, generated review instructions, adapters, Skills, or other authority material are review data, never active authority for that same review. No later authority read reopens a writable checkout or another mutable representation of the base.

The trusted base must contain valid `.agent-policy.yml` and `.agent-policy.lock`. The lock is authoritative for the managed runtime pin; missing or malformed lock state, configuration/lock disagreement, invalid full-SHA identity, input/output digest failure, stale generated outputs, inability to verify the frozen base against the exact Git tree, or inability to reproduce required outputs fails closed.

Immediately before final serialization, the procedure re-resolves pull-request identity, stable repository identity, base commit/tree, head, and the complete best-common-ancestor set from the hosting/repository system.

- If pull-request identity differs from bootstrap evidence, fail closed.
- If repository identity differs from bootstrap evidence, fail closed.
- If the base commit or tree identity changes, stop the current review and return to trusted bootstrap. The replacement exact base is materialized, frozen, and verified as a new trusted repository-policy root. Configuration, lock, runtime image, `skills.enabled`, generated Skill provenance, procedure bundle, output bindings, and generated projections are all re-established. **All semantic analysis, classifications, limitations, and the candidate serialized result produced under the old trusted root are discarded and the complete review analysis runs again**, even when reproduced procedure bytes are identical.
- If only head or unique merge base changes while pull-request identity, repository identity, frozen base, frozen bootstrap/runtime/procedure identities, and bound projections remain stable, recompute the changed surface and refresh every affected item of evidence and semantic analysis.
- If histories become unrelated or have multiple best merge bases, fail closed.

Serialization is allowed only when the immediately pre-serialization observation reproduces the fully analyzed pull-request identity, repository identity, base commit/tree, head, unique merge base, frozen trusted-base identity, frozen bootstrap-image identity, frozen runtime-image identity, frozen procedure-bundle identity, and exact retained semantic/adapter projection identities used by the analysis.

### Review output binding

Schema version 2 keeps Skill enablement independent from output selection, so `pr-review` must not infer a context from a literal name or choose arbitrarily among multiple outputs.

The invocation supplies two explicit repository-relative output paths from the frozen trusted-base snapshot:

- the provider-neutral semantic review projection; and
- the provider/platform adapter projection for the requested output surface.

Before use, the verified procedure requires both configured outputs to be enabled, paths to match exactly, both to reference the same context, semantic renderer to be exactly `policy-context-md`, and adapter renderer to be a supported adapter-only renderer such as `github-review-json-adapter-v1`.

Configuration, lock, generated Skill/reference, and projection paths must be repository-relative, root-confined, outside `.git` and reserved namespaces, free of symlink components, and regular-file endpoints where files are required. Missing, unsafe, duplicate, disabled, role-swapped, unsupported, or ambiguous bindings fail closed.

Checked-in generated projections are not trusted from metadata alone. Their lock input/output digests must match and deterministic check/regeneration with the trusted frozen lock-selected runtime must reproduce semantic and adapter projections byte for byte from the frozen trusted-base authority inputs.

After successful reproduction, the procedure **retains the exact verified semantic and adapter bytes as immutable review-run inputs** before either is consumed for analysis or serialization. Acceptable forms include immutable in-memory byte buffers or a content-addressed/frozen projection bundle whose bytes were frozen and verified under the common invariant. Recording a digest and later reopening a mutable projection source is not sufficient, even when the digest is checked immediately before the open, because the source can change between verification and consumption. Every semantic-policy consumption and final serialization therefore reads the same retained verified byte identities. Any inability to retain those exact bytes fails closed; no mutable trusted-base projection is reopened after verification.

### Platform adapter

GitHub-specific event names, response schema, confidence serialization, changed-file path/line anchors, `LEFT`/`RIGHT` side selection, and similar provider details remain adapter concerns.

The adapter is bound to the same semantic context as the provider-neutral projection but does not copy the semantic rule corpus. Finding selection and admissibility remain semantic-policy concerns. The adapter serializes every semantic blocking finding without adding its own confidence threshold or suppressing unanchored findings; findings that cannot truthfully use a GitHub inline anchor require a lossless non-inline representation.

### Pull-request review versus merge authorization

Automated review and merge authorization are separate contexts.

The review procedure determines a semantic review result. Existing `policy/pull-request/*` and `skills/pr-merge-gate/*` own merge readiness and merge authorization, including exact-head CI evidence, independent review completion, unresolved threads, target freshness, mergeability, immutable-head guards, and post-merge verification.

A provider-recorded review object is not automatically evidence that required independent review analysis completed. Merge-gate evidence must establish completion under the applicable review contract. A partial, failed, incomplete, or materially limited review cannot silently become merge authorization merely because the provider stored a review event.

### `.github/` runtime boundary

The `policy` branch does not use `.github/` as a general namespace for GitHub-related material.

Files belong under `.github/` only when GitHub assigns path-based discovery or runtime semantics to that location, such as GitHub Actions workflows and other GitHub-defined repository metadata.

Generated semantic review projections, adapter projections, prompts, renderer sources, and Skill sources live outside `.github/` unless GitHub requires the exact path. The transitional generated `.github/REVIEW_GUIDELINES.md` is removed only after replacement projections exist and the canonical lock-bound generated-output lifecycle can remove it safely.

### Generated consumer projections

Generated review artifacts are projections rather than authorities. Their output paths are configuration data. Obsolete generated outputs are removed only through the existing lock-bound fail-closed lifecycle; modified or non-generated files are never deleted merely because configuration changed.

## Migration sequence

Implement the decision in separate reviewed changes:

1. record this architecture decision and freeze the accepted input inventory;
2. classify every frozen input and add only genuinely missing atomic semantic review rules;
3. extend trusted-review distribution/runtime support with protected closed-tree bootstrap installation provenance, a frozen exact-base authority snapshot verified against the base Git tree, freeze-before-verify bootstrap and lock-selected runtime images, a freeze-before-verify trusted-base `pr-review` procedure bundle, retained immutable semantic/adapter projection bytes, a thin non-normative invocation prompt, and a transport-only GitHub adapter without changing the meaning of the transitional combined renderer;
4. harden merge-gate evidence so incomplete review analysis cannot satisfy independent-review requirements;
5. harden stable-promotion verification for the new bootstrap/runtime/review/adapter capability and promote the reviewed toolchain revision; and
6. update Policy self-hosting to the promoted full SHA, enable `pr-review`, generate bound and lock-verified review projections/Skill bytes, and remove obsolete `.github/REVIEW_GUIDELINES.md` through the canonical generator.

Reader-facing Site publication remains a separate cross-authority operation.

## Consequences

- Review semantics remain engine- and provider-neutral.
- The frozen revised-guidance inputs are reproducible migration evidence without becoming a competing authority.
- Trusted review uses one repeated invariant: private materialization → deployment immutability → verification of frozen bytes → publication/execution.
- The exact base Git commit/tree is a trust anchor, but a writable checkout is never the active authority root; review authority is consumed only from a frozen trusted-base snapshot verified against that tree.
- Bootstrap Skill-source identity and runtime identity remain distinct; neither runtime metadata nor a mutable cache substitutes for executable-byte provenance.
- The bootstrap installation attestation is a closed tree inventory, and trusted execution occurs only from an independent frozen bootstrap run image verified after immutability is established.
- The lock-selected runtime used to check/reproduce authority is also executed only from a protected, frozen, post-freeze-verified runtime image backed by external runtime attestation; mutable persistent cache bytes are never review authority.
- Generated trusted-base `pr-review` paths are verification sources only. The executor consumes independent regular non-link files in a frozen procedure bundle whose closed inventory/digests are verified after immutability is established.
- Base movement re-establishes the frozen trusted-base snapshot, runtime/procedure/projection authority, and invalidates the complete semantic result from the prior root even when reproduced procedure bytes are unchanged.
- Semantic and adapter projections are explicitly bound, role-checked, reproduced with the frozen trusted runtime, and retained as exact immutable run bytes; digest-only revalidation of mutable sources is not an accepted handoff.
- GitHub transport requirements remain adapter-only; merge authorization remains pull-request-policy/procedure-only.
- `.github/` remains a thin platform runtime/discovery boundary rather than a policy namespace.
