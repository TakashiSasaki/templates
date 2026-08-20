# Glossary terminology inventory

This file is a maintainer working inventory and historical review ledger for the
federated glossary. It is not a canonical glossary source and is intentionally
not listed in any publication catalog. Current canonical terms remain in the
active semantic owners' `docs/glossary.yml` files and in the exact integrated
Site glossary.

Completed tables below record the semantic owner or curator that applied at the
time each expansion was reviewed and promoted. They do **not** define the current
provider topology. The active authority model is now `site`, `composition`, and
`policy`; Skill and Webapp semantics that survived the authority migration are
owned by Composition rather than by active `skill` or `webapp` provider branches.

The inventory is a review aid, not a closed vocabulary. Terms may be added later
without editing this file when their ownership and semantics are already clear.

The original 14-term seed, the reviewed 17-term first expansion, the reviewed
10-term second expansion, and the first reviewed external-term expansion formed
a 42-term promotion baseline at the end of those historical passes. That number
is not a current required count or minimum. The current canonical vocabulary is
defined by the active provider glossaries selected by the Site publication lock.

## Selection rules

A term is a strong candidate for the canonical glossary when one or more of the
following is true:

1. this repository narrows, extends, or independently defines the usual meaning;
2. misunderstanding the term can change an implementation, validation, release,
   or publication decision;
3. the concept crosses branch or artifact boundaries;
4. current canonical documentation distinguishes it from a nearby concept that
   is easy to conflate;
5. an external term is necessary to understand a repository-defined concept and
   needs an explicit upstream or normative authority.

Frequency alone is not sufficient. Ordinary technical nouns are not added merely
because they appear often.

When canonical documentation defines a peer taxonomy or an explicit pair of
contrasting concepts, the inventory should review that set together rather than
including only whichever members happen to fit a smaller pull request.

Stable IDs follow `GLOSSARY.md`: repository-defined concepts use
`templates-<slug>`, and the semantic owner is derived from the provider glossary
that stores the entry rather than being mechanically encoded in the ID. A domain
word such as `skill`, `policy`, or `webapp` belongs in a slug only when it is
needed to identify the concept's semantic scope or avoid conflating a nearby
concept, not merely because that branch currently owns the entry. Consequently,
Policy ownership-taxonomy terms such as `templates-shared-policy` do not acquire
an extra `policy-` segment solely for provider namespacing.

## Original canonical seed

The following table records the original seed as a historical promotion
milestone. It is not a statement that every listed ID remains part of the current
active-provider canonical vocabulary.

| Canonical ID | Owner / curator | Origin | English term |
| --- | --- | --- | --- |
| `templates-publication-catalog` | site | repository | Publication catalog |
| `templates-provider-branch` | site | repository | Provider branch |
| `external-git-branch` | site curator | external | Branch |
| `templates-skill-profile` | skill | repository | Skill profile |
| `templates-skill-template-scaffold` | skill | repository | Skill template scaffold |
| `templates-skill-mcp-extension` | skill | repository | Skill MCP extension |
| `templates-policy-module` | policy | repository | Policy module |
| `templates-policy-profile` | policy | repository | Policy profile |
| `templates-policy-context` | policy | repository | Policy context |
| `templates-policy-renderer` | policy | repository | Policy renderer |
| `templates-webapp-template-mode` | webapp | repository | Template mode |
| `templates-webapp-contract-manifest` | webapp | repository | Contract manifest |
| `templates-webapp-implementation-evidence` | webapp | repository | Implementation evidence |
| `templates-webapp-release-evidence` | webapp | repository | Release evidence |

## Completed first expansion

The following 17 terms were reviewed, added to their semantic owner's canonical
glossary, and promoted through exact provider revisions into the integrated Site
publication. The definitions were derived from the cited canonical source
material rather than from this inventory.

| Canonical term | Canonical ID | Owner | Origin | Japanese discovery label | Rationale / canonical source |
| --- | --- | --- | --- | --- | --- |
| Integrated publication | `templates-integrated-publication` | site | repository | 統合公開 | `PUBLISHING.md` defines one Site-owned publication assembled from independently owned provider histories. The distinction affects ownership and deployment decisions. |
| Publication source lock | `templates-publication-source-lock` | site | repository | 公開ソースロック | `PUBLISHING.md` and `publication-sources.json` require reviewed full-SHA provider inputs rather than mutable refs. |
| Runtime decision record | `templates-skill-runtime-decision-record` | skill | repository | ランタイム決定記録 | `template/RUNTIME.md` is a maintained authority for runtime, exact commands, package/distribution choices, protocol selections, and deployment lifecycle. |
| Public interface selection contract | `templates-skill-public-interface-selection-contract` | skill | repository | 公開インターフェース選択契約 | `template/INTERFACES.md` owns preferred agent route and deterministic fallback order while detailed caller-visible behavior belongs elsewhere. |
| Shared policy | `templates-shared-policy` | policy | repository | 共有ポリシー | `docs/policy-authoring.md` defines this ownership class as generally applicable, artifact- and engine-independent operating behavior authored canonically in the Policy corpus. It is one member of the six-class policy-ownership taxonomy reviewed together here. |
| Context policy | `templates-context-policy` | policy | repository | コンテキストポリシー | `docs/policy-authoring.md` defines this ownership class as artifact- and engine-independent policy content selected only for an operational context such as review. It is distinct from `templates-policy-context`: **Context policy is selected policy content; Policy context is the named semantic selector/authority boundary in `.agent-policy.yml` that selects profiles, repository-local policy, and overrides for an output.** |
| Repository-local policy | `templates-repository-local-policy` | policy | repository | リポジトリローカルポリシー | `docs/policy-authoring.md` assigns repository-specific facts, invariants, justified extensions, and explicit permitted overrides to this ownership class. |
| Artifact contract | `templates-artifact-contract` | policy | repository | アーティファクト契約 | `docs/policy-authoring.md` uses this ownership class for requirements that define what a produced Skill, Web application, CLI, library, service, or other artifact must contain or do, separating artifact semantics from coding-agent policy. |
| Adapter/renderer requirement | `templates-adapter-renderer-requirement` | policy | repository | アダプター／レンダラー要件 | `docs/policy-authoring.md` uses this ownership class when behavior depends on a particular agent, platform, protocol, command surface, renderer, or output format rather than shared policy semantics. |
| Explanatory material | `templates-explanatory-material` | policy | repository | 説明資料 | `docs/policy-authoring.md` separates rationale, examples, history, proposals, and other non-normative text from policy and artifact-contract authority. |
| Policy override | `templates-policy-override` | policy | repository | ポリシーオーバーライド | `docs/configuration.md` makes override declarations explicit exception records and separates them from replacement policy text. |
| Template source artifact | `templates-webapp-template-source-artifact` | webapp | repository | テンプレートソースアーティファクト | `docs/architecture/distribution-boundary.md` distinguishes the complete maintainer checkout from the copyable distribution. Confusing the two changes repository ownership. |
| Template distribution artifact | `templates-webapp-template-distribution-artifact` | webapp | repository | テンプレート配布アーティファクト | `docs/architecture/distribution-boundary.md` defines the committed `template/` subtree copied byte-for-byte to a new product repository. |
| Product repository artifact | `templates-webapp-product-repository-artifact` | webapp | repository | プロダクトリポジトリアーティファクト | `docs/architecture/distribution-boundary.md` distinguishes a generated/customized product repository from both source and distribution artifacts. |
| Product mode | `templates-webapp-product-mode` | webapp | repository | プロダクトモード | `template/docs/architecture/implementation-evidence.md` section **Template and product modes** defines when concrete implementation boundaries, proofs, commands, and release gates become required. `template/docs/architecture/release-evidence.md` distinguishes product-mode revision binding, execution provenance, command/gate results, and approval from template residue. `template/docs/architecture/release-bundle.md` likewise defines template/product handoff semantics for the exact candidate and active contract bytes. Together these documents define the product-mode boundary paired with the canonical `templates-webapp-template-mode`. |
| Release bundle | `templates-webapp-release-bundle` | webapp | repository | リリースバンドル | `template/docs/architecture/release-bundle.md` separates exact handoff bytes from release evidence and defines deterministic artifact closure. |
| Contract family | `templates-webapp-contract-family` | webapp | repository | コントラクトファミリー | `template/docs/architecture/contract-completeness.md` and release-bundle guidance use stable contract-family identity, version history, migrations, active/retired state, and evidence coverage. |

### Policy ownership-taxonomy boundary

The six ownership classes above are peers from `docs/policy-authoring.md` and were
reviewed as one set:

1. Shared policy;
2. Context policy;
3. Repository-local policy;
4. Artifact contract;
5. Adapter/renderer requirement; and
6. Explanatory material.

They classify where a requirement or piece of documentation belongs. They do not
replace the runtime/configuration concept `Policy context`. A Policy context is a
named semantic authority boundary that selects policy inputs and a renderer for
an output; Context policy is one class of policy content that may be selected for
an operational context. The canonical entries relate those concepts so search
and review do not treat the reversed names as synonyms.

## Cross-provider relation policy

`related_terms` is untyped stable-ID navigation metadata rather than a formal
ontology. Provider-local glossary files are federated inputs and are not required
to contain definitions for every related ID they reference. Cross-provider
targets remain defined by exactly one canonical owner and are resolved by the
Site parser only after the exact provider revisions are integrated.
A cross-provider relation is appropriate only when at least one of these is true:

1. two canonical concepts have similar labels and an explicit relation materially
   reduces the risk of conflating them; or
2. a concrete provider concept is clearly an instance or application of a
   canonical cross-provider classification and the link improves navigation.

Shared words alone are insufficient. Relations need not be symmetric. Peer
concepts may link reciprocally for disambiguation, while concrete-to-generic
classification links normally point only from the concrete term to the generic
term so the generic taxonomy does not become an open-ended instance registry.

### Completed first cross-provider relation pass

The following reviewed relations complete the deferred relation pass of the first
expansion:

| Source term | Related term | Relation rationale |
| --- | --- | --- |
| `templates-skill-profile` | `templates-policy-profile` | Reciprocal peer link between two distinct profile systems that share the lexical head “profile”. |
| `templates-policy-profile` | `templates-skill-profile` | Reciprocal peer link for the same disambiguation boundary. |
| `templates-skill-public-interface-selection-contract` | `templates-artifact-contract` | The Skill contract is a concrete artifact-level contract governed by the generic Policy ownership classification. |
| `templates-skill-public-interface-selection-contract` | `templates-adapter-renderer-requirement` | Its semantics depend on the retained public interface/agent surface and therefore intersect the adapter/interface-specific requirement class. |
| `templates-webapp-implementation-evidence` | `templates-artifact-contract` | The Webapp implementation-evidence contract defines artifact-level proof obligations. |
| `templates-webapp-release-evidence` | `templates-artifact-contract` | The revision-specific release-evidence contract is part of the produced Webapp artifact contract system. |
| `templates-webapp-release-bundle` | `templates-artifact-contract` | The handoff bundle is explicitly a Webapp contract governing exact artifact bytes. |

Deliberately omitted weak relations include `Contract manifest` or `Contract
family` merely because they contain the word “contract”, publication catalog ↔
contract manifest based only on registry similarity, and Template mode ↔ Skill
template scaffold based only on shared template vocabulary.

### Completed second cross-provider relation review

After all ten second-expansion targets were available for exact-revision
integration, the likely cross-provider pairs were reviewed again. **No additional
cross-provider `related_terms` were added.** The vocabulary overlap is not strong
enough to assert an untyped semantic edge:

- `templates-policy-promoted-toolchain-revision` and
  `templates-webapp-candidate-revision` are revision roles in different release
  systems; neither is a generic or concrete instance of the other.
- `templates-policy-stable-release` and `templates-webapp-released-revision`
  distinguish a selected executable Policy release state from an immutable source
  identity published by a release system.
- `templates-policy-managed-repository` and
  `templates-webapp-product-repository-artifact` are not equivalent states. The
  former is an agent-policy adoption classification based on `.agent-policy.yml`;
  the latter is an artifact class and does not imply that Policy management has
  been adopted.

These omissions are deliberate. Future cross-provider links may still be added
when a stronger semantic or disambiguation need is established.

## Completed second expansion

The following ten terms were reviewed as the second repository-defined expansion,
added to their semantic owners' canonical glossaries, validated by provider-local
checks plus Site compatibility, and promoted through exact provider revisions
into the integrated Site publication.

| Canonical term | Canonical ID | Owner | Origin | Japanese discovery label | Rationale / canonical source |
| --- | --- | --- | --- | --- | --- |
| Stable release | `templates-policy-stable-release` | policy | repository | 安定版リリース | `docs/architecture.md` separates the advancing `policy` branch from the executable stable release selected by the stable descriptor. A stable release is the currently selected executable Policy toolchain release, not the branch tip or the later promotion-state commit. |
| Stable release descriptor | `templates-policy-stable-release-descriptor` | policy | repository | 安定版リリース記述子 | `docs/architecture.md` identifies `release/toolchain.json` as the stable release descriptor. It records `channel: stable`, the toolchain repository and exact promoted revision, synchronized contract versions, and verifier requirements. |
| Promoted toolchain revision | `templates-policy-promoted-toolchain-revision` | policy | repository | 昇格済みツールチェーンリビジョン | Policy promotion writes one reviewed candidate full SHA into both the stable release descriptor and bootstrap manifest. The promoted revision is a strict ancestor of the later promotion-state commit, preventing recursive self-reference. |
| Bootstrap trust seed | `templates-policy-bootstrap-trust-seed` | policy | repository | ブートストラップ信頼シード | `docs/architecture.md` and `skills/bootstrap-agent-policy/README.md` define `skills/bootstrap-agent-policy/` as the installable trust seed that invokes one immutable Policy toolchain revision through a closed route set; its manifest pins the same promoted revision as the stable descriptor and exposes no finalization route. |
| Managed repository | `templates-policy-managed-repository` | policy | repository | 管理対象リポジトリ | `docs/configuration.md` and `src/agent_policy/adoption.py::inspect_repository` classify a repository as `managed` when canonical `.agent-policy.yml` resolves to an existing regular file. This classification is distinct from later semantic validation; partial or conflicting generated state is `inconsistent`. |
| Candidate revision | `templates-webapp-candidate-revision` | webapp | repository | 候補リビジョン | `template/docs/architecture/release-bundle.md` defines the immutable source revision whose reviewed commands ran and whose approval is recorded by release evidence. Product-mode release bundle v1 binds the same exact revision. |
| Merge-test revision | `templates-webapp-merge-test-revision` | webapp | repository | マージテストリビジョン | `template/docs/architecture/release-bundle.md` defines a temporary or synthetic revision used to test a proposed merge result. It can provide validation evidence but is not automatically the release candidate. |
| Released revision | `templates-webapp-released-revision` | webapp | repository | リリース済みリビジョン | `template/docs/architecture/release-bundle.md` defines the immutable source identity published by a release system. If mapping an accepted bundle to the released revision changes the source revision, the prior candidate bundle cannot be silently relabeled; fresh release evidence and a fresh bundle are required for the newly selected candidate. |
| Deployed revision | `templates-webapp-deployed-revision` | webapp | repository | デプロイ済みリビジョン | `template/docs/architecture/release-bundle.md` defines the immutable source identity observed in a target environment after deployment. It belongs to deployment/post-deployment verification and should be compared with the released revision in product-owned deployment evidence. |
| Index-guided navigation | `templates-index-guided-navigation` | site | repository | インデックス誘導ナビゲーション | `PUBLISHING.md` defines `/guided/` as a bounded Site projection of provider-owned `index.md` navigation metadata from exact reviewed provider revisions. It preserves provider grouping/order/labels, is neither a publication catalog nor a replacement for Site-authored reader navigation, and uses `/guided/graph.json` as its schema-versioned read model. |

### Second-expansion semantic groups

The five Policy terms form one release/onboarding trust boundary rather than five
unrelated nouns. `Stable release` is the selected executable release state;
`Stable release descriptor` is the committed descriptor that records the exact
selection; `Promoted toolchain revision` is the reviewed candidate SHA selected
by promotion; `Bootstrap trust seed` is the installable immutable entry route
that pins that same revision; and `Managed repository` is the downstream state in
which normal configuration-driven operation replaces bootstrap onboarding.

The four Webapp revision-role terms are peers and must not be collapsed. A
`Candidate revision` is the explicitly approved source subject, a `Merge-test
revision` is validation input that is not automatically the candidate, a
`Released revision` is the source identity published by the release system, and a
`Deployed revision` is the source identity observed in an environment after
deployment. Equality between roles is possible in a particular workflow but is
never inferred from the role names themselves.

`Index-guided navigation` is Site-owned because Site generates, validates, and
publishes the projection, while the navigation semantics being projected remain
provider-owned. Its stable identity does not imply that provider `index.md`
becomes a publication catalog or that Site takes ownership of provider navigation
semantics.

## Completed external terminology expansion

The first external-term curation pass adds the generic protocol concept needed to
navigate from the repository-defined Skill MCP extension to its external semantic
basis. External semantic authority remains outside this repository even though
Skill is the single local curator of the entry.

| Canonical term | Canonical ID | Curator | Origin | Japanese discovery label | Authority / rationale |
| --- | --- | --- | --- | --- | --- |
| Model Context Protocol | `external-mcp-model-context-protocol` | skill | external | モデルコンテキストプロトコル | The official Model Context Protocol specification dated `2026-07-28` is the version-pinned normative authority. Skill already uses that core protocol revision as its current baseline. `templates-skill-mcp-extension` links one-way to this generic external concept; the reverse relation is deliberately omitted so the external term does not become an open-ended registry of repository-specific concepts. |

## External terminology candidates

External terms are not repository-owned definitions. They require a stable
external semantic domain plus upstream, normative, or conventional authority.
They should be added only when their presence materially improves discovery of a
repository-specific concept. Each external term has exactly one local curator so
its provenance is unambiguous and duplicate stable IDs cannot be authored by
multiple provider glossaries.

| Candidate term | Proposed ID | Curator | Initial decision | Notes |
| --- | --- | --- | --- | --- |
| Service Worker | `external-web-service-worker` | site | defer | Relevant to Site PWA behavior, but not required to understand the current repository-defined glossary baseline. |
| Progressive Web App | `external-web-progressive-web-app` | site | defer | Same reason as Service Worker; add when PWA terminology becomes a glossary navigation need. |

## Japanese-label policy for this inventory

Japanese text in the tables is discovery metadata only. The canonical entry must
still use English `term` plus English repository `definition`, or English
external `summary` plus `authority`.

A proposed Japanese label is not automatically accepted merely because it is in
this inventory. Before committing it, prefer terminology already used naturally
in repository documentation or standard Japanese technical usage. Alternative
spellings may be stored as `localized_labels.ja.aliases` when they improve
lookup. No Japanese definition is required.

## Expansion workflow

Future repository-defined expansions should preserve the owner-first and
exact-revision promotion model:

1. review ambiguous ownership or taxonomy groups before editing canonical data;
2. add terms to the semantic owner's `docs/glossary.yml` without requiring a
   central vocabulary edit;
3. keep provider-authored relations provider-local until any cross-provider
   targets exist in the exact integrated set;
4. run provider-local checks and the Site compatibility workflow;
5. merge provider changes and promote the reviewed full merge SHAs through
   `publication-sources.json`;
6. verify the integrated machine-readable glossary and human viewer while
   treating the established canonical IDs as a required subset rather than a
   closed vocabulary; and
7. review useful cross-provider `related_terms` only after all referenced targets
   exist in the locked integrated set.

External-term expansion remains a separate curation pass because authority URLs
and version-sensitive upstream semantics must be verified against current
official sources when each external entry is created.