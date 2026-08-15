# Glossary terminology inventory

This file is a maintainer working inventory for expanding the federated glossary.
It is not a canonical glossary source and is intentionally not listed in any
publication catalog. Canonical terms remain in the semantic owner's
`docs/glossary.yml`.

The inventory is a review aid, not a closed vocabulary. Terms may be added later
without editing this file when their ownership and semantics are already clear.

The original 14-term seed and the reviewed 17-term first expansion are now
canonical. The integrated glossary therefore has a required 31-term baseline at
this stage, while remaining open to later vocabulary growth.

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

The original seed remains a required subset of the canonical vocabulary.

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

The following reviewed relations complete the deferred step 7 of the first
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

## Proposed second expansion

The next repository-defined expansion is a coherent set of ten terms whose
boundaries are already explicit in canonical documentation or executable
classification logic. The Policy release/trust terms are reviewed together, the
Webapp revision roles are reviewed together, and the Site navigation concept is
independent. Cross-provider relations among these terms remain deferred until all
new targets exist in the exact locked integrated set.

| Candidate term | Proposed ID | Owner | Origin | Japanese discovery label | Include next | Rationale / canonical source |
| --- | --- | --- | --- | --- | --- | --- |
| Stable release | `templates-policy-stable-release` | policy | repository | 安定版リリース | yes | `docs/architecture.md` explicitly separates the advancing `policy` development branch from the executable stable release selected by the stable descriptor. A stable release is therefore the currently selected executable Policy toolchain release, not the current branch tip or the later promotion-state commit. |
| Stable release descriptor | `templates-policy-stable-release-descriptor` | policy | repository | 安定版リリース記述子 | yes | `docs/architecture.md` identifies `release/toolchain.json` as the stable release descriptor. The file records `channel: stable`, the toolchain repository and exact promoted revision, plus synchronized contract versions and verifier requirements. |
| Promoted toolchain revision | `templates-policy-promoted-toolchain-revision` | policy | repository | 昇格済みツールチェーンリビジョン | yes | `docs/architecture.md` defines promotion as writing one reviewed candidate full SHA into both the stable release descriptor and bootstrap manifest. The promoted revision is a strict ancestor of the later promotion-state commit, preventing recursive self-reference. |
| Bootstrap trust seed | `templates-policy-bootstrap-trust-seed` | policy | repository | ブートストラップ信頼シード | yes | `docs/architecture.md` and `skills/bootstrap-agent-policy/README.md` define `skills/bootstrap-agent-policy/` as the installable trust seed that invokes one immutable Policy toolchain revision through a closed route set. `bootstrap-manifest.yml` pins the same full SHA as the stable release descriptor and intentionally exposes no finalization route. |
| Managed repository | `templates-policy-managed-repository` | policy | repository | 管理対象リポジトリ | yes | `docs/configuration.md` makes `.agent-policy.yml` the sole semantic configuration entry point in a managed product repository. `src/agent_policy/adoption.py::inspect_repository` classifies a repository as `managed` when that canonical config path resolves to an existing regular file; partial/conflicting generated state without a valid config is classified as `inconsistent`. Managed repositories use normal `validate`, `render`, and `check` rather than onboarding bootstrap. |
| Candidate revision | `templates-webapp-candidate-revision` | webapp | repository | 候補リビジョン | yes | `template/docs/architecture/release-bundle.md` defines the candidate as the immutable source revision whose reviewed commands ran and whose approval is recorded by release evidence. Product-mode release bundle v1 binds this exact revision and requires equality with the explicit expected revision and release-evidence subject. |
| Merge-test revision | `templates-webapp-merge-test-revision` | webapp | repository | マージテストリビジョン | yes | `template/docs/architecture/release-bundle.md` defines a temporary or synthetic revision used to test a proposed merge result. A pull-request merge ref is an example; it is useful validation evidence but is not automatically the release candidate unless selected explicitly. |
| Released revision | `templates-webapp-released-revision` | webapp | repository | リリース済みリビジョン | yes | `template/docs/architecture/release-bundle.md` defines the immutable source identity published by a release system. It may equal the candidate or a later merge commit, and the release system must retain an auditable mapping rather than silently relabel an earlier candidate bundle. |
| Deployed revision | `templates-webapp-deployed-revision` | webapp | repository | デプロイ済みリビジョン | yes | `template/docs/architecture/release-bundle.md` defines the immutable source identity observed in a target environment after deployment. It belongs to deployment/post-deployment verification rather than the pre-release handoff contract and should be compared with the released revision in product-owned deployment evidence. |
| Index-guided navigation | `templates-index-guided-navigation` | site | repository | インデックス誘導ナビゲーション | yes | `PUBLISHING.md` defines `/guided/` as a bounded Site projection of provider-owned `index.md` navigation metadata from exact reviewed provider revisions. It preserves provider grouping/order/labels, is neither a second publication catalog nor a replacement for Site-authored reader navigation, and uses `/guided/graph.json` as its schema-versioned read model. |

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
`Released revision` is the source identity published by the release system, and
a `Deployed revision` is the source identity observed in an environment after
deployment. Equality between roles is possible in a particular workflow but is
never inferred from the role names themselves.

`Index-guided navigation` is Site-owned because Site generates, validates, and
publishes the projection, while the navigation semantics being projected remain
provider-owned. Its stable identity must not imply that provider `index.md`
becomes a publication catalog or that Site takes ownership of provider navigation
semantics.

## External terminology candidates

External terms are not repository-owned definitions. They require a stable
external semantic domain plus upstream, normative, or conventional authority.
They should be added only when their presence materially improves discovery of a
repository-specific concept. Each external term has exactly one local curator so
its provenance is unambiguous and duplicate stable IDs cannot be authored by
multiple provider glossaries.

| Candidate term | Proposed ID | Curator | Initial decision | Notes |
| --- | --- | --- | --- | --- |
| Model Context Protocol | `external-mcp-model-context-protocol` | skill | defer | Skill is the single local curator because its canonical contracts define MCP-enabled Skill behavior and already own the repository-specific MCP-extension concept. Authority/version selection must still be curated from current official MCP specifications before creating the external entry. |
| Service Worker | `external-web-service-worker` | site | defer | Relevant to Site PWA behavior, but not required to understand the repository-defined second expansion. |
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

## Expansion implementation sequence

The first expansion established the owner-first and exact-revision promotion
model. The second repository-defined expansion should use the same dependency
order:

1. review this inventory change before editing any canonical provider glossary;
2. add the Site-owned `Index-guided navigation` term;
3. add the five Policy-owned release/trust/onboarding terms as one coherent set;
4. add the four Webapp-owned revision-role terms as one coherent set;
5. validate every provider revision through provider-local checks and the Site
   compatibility workflow;
6. promote the reviewed provider merge SHAs through a coordinated Site lock
   update and verify the integrated JSON and human glossary viewer; and
7. only after all new targets exist in the exact locked integrated set, review
   any useful cross-provider `related_terms` rather than inferring them from
   shared words.

External-term expansion remains a separate curation pass because authority URLs
and version-sensitive upstream semantics must be verified against current
official sources when the entry is created.
