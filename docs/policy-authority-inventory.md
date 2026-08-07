# Policy authority consolidation inventory

This document freezes the first cross-branch inventory used by ADR-0005. It is an audit input, not a second policy authority. The semantic rules remain in their canonical policy or repository-local sources until later migration pull requests move them deliberately.

## Frozen source revisions

The initial inventory is based on these exact branch revisions:

| Branch | Full revision |
| --- | --- |
| `policy` | `d9b508004c54e24929b27d9c8813748ae820bf01` |
| `skill` | `63a2ad7ff4ad6396daf269af1536aff53515180d` |
| `webapp` | `1671c5b503377b87d157aeaa714bdf7c43797dc9` |

Later audits must record a new snapshot instead of silently treating changed branch tips as part of this inventory.

## Classification test

For every normative statement, classify ownership in this order:

1. **Artifact-independence test.** Would the requirement retain substantially the same meaning for a Web application, Agent Skill, CLI, library, service, or other repository type? If no, classify it as `artifact-contract` or `repository-policy`.
2. **Engine-independence test.** Would the requirement retain substantially the same meaning when followed by a different coding agent, general-purpose agent, automated reviewer, or a human following the same procedure? If no, classify it as `adapter`.
3. **Context test.** Is it artifact- and engine-independent but applicable only in a named operational situation such as pull-request review or external-artifact intake? If yes, classify it as `context-policy`; otherwise it is a `shared-policy` candidate.
4. **Repository-identity test.** Does the rule depend on local paths, branch identities, schemas, profiles, publication boundaries, release descriptors, or maintenance invariants? If yes, keep that part as `repository-policy` even if a more general rule is shared.
5. **Normativity test.** Does the statement actually impose an obligation or prohibition? Rationale, examples, historical records, and future proposals are `explanatory` and do not become competing authorities.

A mixed document is split conceptually at statement level. The document itself is not assigned one ownership class when different sections have different authorities.

## `policy` branch

### Existing shared corpus

The current `policy/core/*.md`, `policy/security/*.md`, and `policy/artifacts/*.md` files are the primary existing `shared-policy` or `context-policy` candidates. The current core profile already selects twelve atomic core modules. These files require a later atomicity and scope audit, but they are already close to the target one-rule-per-file model.

### Policy-repository maintenance material

The following sources contain normative material about maintaining the policy toolchain itself and therefore must not be mistaken for shared policy merely because they live on the `policy` branch:

| Source | Initial disposition |
| --- | --- |
| `README.md` | split explanatory material from `repository-policy` for policy CI, release promotion, bootstrap trust anchors, and publication ownership |
| `docs/configuration.md` | mostly toolchain contract/explanation; extract only genuinely shared operating semantics if found |
| `docs/release-lifecycle.md` | policy-toolchain release contract; `repository-policy` unless a rule generalizes independently |
| `docs/documentation-publication.md` | policy repository publication rules; `repository-policy` |
| `docs/bootstrap-model.md` | bootstrap/toolchain trust model; toolchain contract plus repository-local maintenance rules |
| `docs/threat-model.md` | explanatory security model plus possible shared-policy candidates to audit statement by statement |
| `skills/bootstrap-agent-policy/**` | operational implementation and trust seed, not a shared-policy source merely because it contains instructions |

## `skill` branch

The `skill` branch contains the highest-priority duplicate-authority candidates.

| Source at frozen revision | Mixed content identified | Initial disposition |
| --- | --- | --- |
| `AGENTS.md` | generic change/verification/security rules plus Skill-source artifact, profile, publication, and projection invariants | shared parts -> `policy`; Skill-specific parts -> `repository-policy`; final file should be generated |
| `.github/REVIEW_GUIDELINES.md` | generic review semantics, security/error/performance/regression review, normative-document conflict handling, plus GitHub/Antigravity JSON and line-anchor protocol | generic semantics -> `context-policy: review`; output protocol -> `adapter`; remove handwritten duplicate after generated replacement exists |
| `CONTRIBUTING.md` | source-maintainer workflow and potentially generic contribution rules | audit statement by statement; generic parts -> `policy`, Skill ownership rules -> `repository-policy` |
| `docs/architecture/distribution-boundary.md` | source/distribution/concrete-Skill ownership and maintainer change rules | Skill-specific `repository-policy` plus explanatory architecture; not shared solely because some safety principles resemble policy |
| `docs/publication-maintenance.md` | cross-branch publication maintenance | `repository-policy` |
| `docs/ruby-to-python-migration.md` | migration history and temporary maintenance constraints | primarily explanatory/historical; active requirements require explicit classification |
| `docs/schema-validator-absence.md` | repository-specific validation decision | explanatory or `repository-policy` depending on active normative language |
| `template/AGENTS.md` | generic verification/security language mixed with concrete Skill profile/runtime/interface requirements | treat separately from source-maintainer migration; Skill artifact rules remain `artifact-contract`; possible shared-policy adoption is a later distribution decision |

The `skill` source repository is migrated before `skill/template/`. The copyable distribution is a separate artifact contract and must not change incidentally during source-policy consolidation.

## `webapp` branch

The current `webapp` branch deliberately excludes coding-agent operating policy from the Webapp artifact contract. That boundary is preserved.

| Source at frozen revision | Mixed content identified | Initial disposition |
| --- | --- | --- |
| `README.md` | template description plus branch-maintainer validation procedure and maintenance rules | Webapp artifact explanation remains local; generic maintainer rules are candidates for shared policy; repository-specific validation remains `repository-policy` |
| `TEMPLATE.md` | Webapp product/template contract plus required customization sequence | `artifact-contract`; do not move Webapp semantics into shared policy |
| `docs/operationalization.md` | generated-product workflow, baseline freezing, validator isolation, product evidence and release procedure | mostly Webapp/product contract; audit generic operational fragments without duplicating artifact-specific semantics |
| `docs/architecture/responsibility-boundaries.md` | explicit separation of Webapp concerns from coding-agent and organization policy | architectural authority that preserves the boundary; explanatory plus Webapp `artifact-contract` |
| `docs/architecture/validation-toolchain.md` | repository-local clean validation environment and dependency update procedure | `repository-policy` where tied to this toolchain; extract only semantics that remain identical across unrelated runtimes/toolchains |
| `docs/architecture/contract-evolution.md` | Webapp contract version/migration semantics | `artifact-contract` |
| `docs/architecture/implementation-evidence.md` | Webapp implementation-evidence contract | `artifact-contract` |
| `docs/architecture/release-evidence.md` | Webapp release-evidence contract | `artifact-contract` |
| `docs/architecture/release-bundle.md` | Webapp handoff contract | `artifact-contract` |

The root source repository may later adopt the policy toolchain for its maintainers, but `template/` remains policy-neutral unless a separate reviewed distribution decision changes that contract.

## First duplicate families to normalize

The first statement-level audit should prioritize these semantic families because they already appear in more than one branch:

| Semantic family | Existing canonical candidate | Duplicate or specialized locations to audit |
| --- | --- | --- |
| change scope | `policy/core/change-scope.md` | `skill/AGENTS.md`, contribution/maintenance docs |
| required verification | `policy/core/testing.md` | `skill/AGENTS.md`, `webapp` validation docs |
| regression-test integrity | `policy/core/regression-safety.md` | `skill/.github/REVIEW_GUIDELINES.md`, Skill validation rules |
| compatibility preservation | `policy/core/compatibility.md` | review guidance and artifact-specific compatibility contracts |
| truthful evidence/status | `policy/core/evidence-layers.md`, `policy/core/truthful-reporting.md` | review completion rules, Webapp implementation/release evidence descriptions |
| generated-artifact synchronization | `policy/core/generated-artifacts.md` | Skill validator projections, generated instructions, Webapp derived evidence |
| trust-boundary validation | `policy/security/input-validation.md` | review security section, Skill resource validation, Webapp validation bootstrap |
| secrets | `policy/security/secrets.md` | Skill completion criteria and security review |
| destructive/live-state safety | `policy/core/destructive-actions.md`, `policy/core/transaction-ownership.md` | branch/release/finalization procedures |
| normative-rule conflict analysis | no atomic shared rule yet | `skill/.github/REVIEW_GUIDELINES.md` sections 9.1-9.7 |
| blocking review evidence threshold | no atomic shared review profile yet | `skill/.github/REVIEW_GUIDELINES.md` sections 1-12 |

Artifact-specific contracts may instantiate or enforce a general principle without becoming duplicate policy authority. For example, a Webapp release-evidence schema can enforce exact revision binding while the shared policy separately states how agents must report evidence. The audit must distinguish those layers rather than deleting domain contracts merely because they resemble a shared rule.

## Estimated pull-request sequence

The current estimate is eight to ten reviewed pull requests:

1. **Authority baseline** (`policy`): ADR-0005, this frozen inventory, classification rules, and migration roadmap.
2. **Atomic review policy** (`policy`): decompose generic review semantics from the frozen Skill review document; reuse existing core/security rules rather than cloning them.
3. **Context and adapter model** (`policy`): add review-context selection and separate semantic rules from GitHub/Antigravity output rendering. This may require a configuration-schema version transition.
4. **Conflict and provenance enforcement** (`policy`): validate explicit overrides, canonical origins, duplicate authorities, and generated-output freshness.
5. **Stable policy promotion** (`policy`): promote one reviewed candidate full SHA using the existing two-step stable-release model.
6. **Skill source adoption** (`skill`): add the pinned policy configuration and Skill-source local policy, generate source-maintainer instructions/review output, and remove handwritten shared-policy duplicates.
7. **Webapp source adoption** (`webapp`): add pinned source-maintainer policy while preserving the policy-neutral Webapp artifact contract.
8. **Policy self-hosting** (`policy`): separate policy-repository maintenance rules from the shared corpus and consume the promoted shared policy for policy maintenance.
9. **Skill distribution decision** (`skill`, conditional): decide whether `template/` should itself ship a pinned policy configuration; if yes, change and validate the distribution contract separately.
10. **Follow-up cleanup/publication** (conditional): remove obsolete explanatory duplicates or update cross-branch publication only when the preceding migrations prove the new authority graph is closed.

Items 9 and 10 are conditional. The core consolidation can complete in eight pull requests if no consumer-distribution change or separate cleanup PR is needed.

## Completion evidence for this inventory phase

This phase does not claim that every normative sentence has already been extracted. It establishes the accepted classification model, fixed source revisions, high-risk source set, duplicate-family priorities, and bounded PR sequence. The next pull request performs the statement-level decomposition of generic review policy against these frozen inputs.
