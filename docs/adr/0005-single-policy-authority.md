# ADR-0005: Keep one canonical authority for shared operating policy

- Status: Accepted
- Date: 2026-08-07

## Context

Application-type-independent operating rules are currently distributed across the unrelated `policy`, `skill`, and `webapp` histories. Some rules are already canonical policy modules, while others are embedded in repository-maintainer instructions, review guidance, architecture documents, and generated-template material.

This creates two risks:

- the same semantic rule can evolve independently in more than one branch and drift or conflict; and
- artifact-specific contracts, repository-maintainer rules, review procedures, and agent- or platform-specific output requirements can be mistaken for one another.

The `policy` branch already defines an application-type-independent toolchain that combines shared policy profiles with repository-local policy inputs and renders reproducible agent instructions from a pinned full commit SHA. The same ownership model should govern shared policy consolidation.

## Decision

Each independently applicable normative rule has exactly one canonical authority.

A rule belongs to the shared `policy` corpus when its normative meaning remains substantially unchanged across both of these substitutions:

1. the artifact category changes among Web applications, Agent Skills, command-line tools, libraries, services, and other repository types; and
2. the reasoning or execution engine changes among coding agents, general-purpose agents, automated reviewers, or a human following the same operational procedure.

Artifact-independent rules may still be context-specific. For example, pull-request review rules belong to the shared policy corpus when they describe review semantics rather than one artifact type. Such rules may be selected through a review-specific profile instead of the always-on core profile.

Rules that require repository-local identities, paths, schemas, profiles, publication boundaries, or maintenance invariants remain repository-local policy. Rules that define the artifact itself remain in the corresponding artifact contract system. Requirements whose meaning exists only because of an agent, platform, protocol, or output format are renderer or adapter concerns rather than shared policy.

Shared policy is authored only in the `policy` branch. Other branches may contain generated projections of shared policy, but they must not maintain handwritten semantic copies as independent authorities.

A policy file should contain one independently applicable normative rule with one stable rule ID. Rationale, examples, and failure cases may accompany that rule. If a document contains multiple obligations that can apply, change, or be overridden independently, those obligations are split into separate policy modules.

Repository-local policy may extend shared policy. It may override a shared rule only when the canonical rule explicitly permits overriding and the override is explicit and attributable. A mandatory non-overridable shared rule cannot be replaced by repository-local text.

Documentation may explain or reference canonical rules but must not silently create a competing normative authority. Generated instructions must identify the canonical origin of shared rules and the repository-local origin of local rules.

### Configuration contract consequence

The accepted `agent-policy` configuration contract is schema version 2 only. Its named `contexts` are the semantic authority boundaries that select profiles, repository-local policy, and explicit overrides; named outputs separately bind one context to one renderer. `init` and `adopt prepare` use the same contract by emitting an explicit `default` context when only one semantic context is required.

Schema version 1 is retired rather than retained as a compatibility mode. Its top-level single-context representation and implicit shared-rule override behavior would preserve a second, weaker authority path beside the explicit context and override model adopted here. The validator therefore rejects schema version 1, manifest generators emit only schema version 2, and both validation and rendering require explicit override declarations. This retirement changes only the `agent-policy` configuration contract; independently versioned contracts such as adoption state, generated lock data, renderer response formats, and publication or glossary schemas keep their own version lifecycles.

Because this repository is still pre-release, no configuration migration or backward-compatibility adapter is maintained. Historical schema-version-1 behavior remains available through Git history rather than through the active runtime contract.

## Ownership classification

Every normative statement discovered during consolidation is classified into exactly one of these ownership classes:

- `shared-policy`: application-type- and engine-independent normative behavior owned by `policy`;
- `context-policy`: shared policy that applies only in a named operational context such as review or external-artifact intake;
- `repository-policy`: branch- or repository-maintenance rules that depend on local identities or invariants;
- `artifact-contract`: requirements that define the produced Skill, Web application, or another artifact category;
- `adapter`: agent-, platform-, protocol-, or output-format-specific rendering and interaction requirements;
- `explanatory`: non-normative rationale, examples, history, or guidance.

A statement is not duplicated merely because it is useful in more than one context. Context-specific rules should reference existing canonical rules when the underlying obligation is already defined elsewhere.

## Consequences

- Generic review semantics currently maintained in `skill/.github/REVIEW_GUIDELINES.md` are candidates for decomposition into shared review policy plus a GitHub/Antigravity-specific output adapter.
- Generic source-maintainer rules currently embedded in `skill/AGENTS.md`, `webapp` maintenance documentation, or `policy` maintenance documentation are candidates for shared policy only when they pass the artifact- and engine-independence tests.
- Skill profile contracts, Webapp surface/route/state contracts, and other artifact architecture remain outside the shared corpus.
- Consumer branches adopt reviewed stable policy revisions by full SHA; unrelated branch histories remain unrelated and are not merged, rebased, or cherry-picked to share policy.
- Consolidation is staged so that a shared canonical rule exists and is consumable before handwritten duplicates are removed from another branch.
- Active `agent-policy` configurations have one schema-version-2 authority model; no runtime branch preserves schema-version-1 implicit override semantics.

## Migration order

1. Freeze and inventory the normative sources in `policy`, `skill`, and `webapp` by full branch SHA.
2. Classify each discovered normative statement using the ownership classes above and identify duplicates, conflicts, and mixed documents.
3. Add missing shared policy modules, starting with generic review semantics, without yet deleting consumer-branch copies.
4. Add context-aware policy selection and renderer/adapter separation where one semantic policy set must produce different instruction surfaces.
5. Add validation that rejects undeclared overrides, duplicate authorities, and stale generated outputs.
6. Promote one reviewed stable policy full SHA.
7. Migrate `skill` source-maintainer policy to the stable toolchain and remove handwritten shared-policy duplicates.
8. Migrate `webapp` source-maintainer policy without adding shared coding-agent policy to the Webapp artifact contract.
9. Self-host `policy` repository-maintainer rules separately from the shared corpus.
10. Treat policy adoption inside copyable consumer artifacts such as `skill/template/` as a separate distribution-contract decision.
11. Retire the transitional schema-version-1 configuration path once schema version 2 is the maintained self-hosted and generated configuration contract.

## Verification

The consolidation is complete only when every shared semantic rule has one canonical rule ID and source, repository-local exceptions are explicit, generated projections are traceable to their source revision, and no branch contains an independently maintained handwritten duplicate that can conflict with the canonical shared rule.

For the configuration-contract consequence above, verification additionally requires the schema to declare version 2 with `const`, `init` and `adopt prepare` to generate schema-version-2 configurations, schema version 1 to be rejected, and validation and rendering to enforce the same explicit-override semantics.
