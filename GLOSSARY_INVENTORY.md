# Glossary terminology inventory

This file is a maintainer working inventory for expanding the federated glossary.
It is not a canonical glossary source and is intentionally not listed in any
publication catalog. Canonical terms remain in the semantic owner's
`docs/glossary.yml`.

The inventory is a review aid, not a closed vocabulary. Terms may be added later
without editing this file when their ownership and semantics are already clear.

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

## Current canonical seed

The following stable IDs are already canonical and remain required seed terms.
The set is required as a subset, not as the complete glossary vocabulary.

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

## Proposed first expansion

The following terms are recommended for the next glossary expansion. Definitions
must be derived from the cited canonical source documents rather than invented in
this inventory.

| Candidate term | Proposed ID | Owner | Origin | Japanese discovery label | Include next | Rationale / canonical source |
| --- | --- | --- | --- | --- | --- | --- |
| Integrated publication | `templates-integrated-publication` | site | repository | 統合公開 | yes | `PUBLISHING.md` defines one Site-owned publication assembled from independently owned provider histories. The distinction affects ownership and deployment decisions. |
| Publication source lock | `templates-publication-source-lock` | site | repository | 公開ソースロック | yes | `PUBLISHING.md` and `publication-sources.json` require reviewed full-SHA provider inputs rather than mutable refs. |
| Runtime decision record | `templates-skill-runtime-decision-record` | skill | repository | ランタイム決定記録 | yes | `template/RUNTIME.md` is a maintained authority for runtime, exact commands, package/distribution choices, protocol selections, and deployment lifecycle. |
| Public interface selection contract | `templates-skill-public-interface-selection-contract` | skill | repository | 公開インターフェース選択契約 | yes | `template/INTERFACES.md` owns preferred agent route and deterministic fallback order while detailed caller-visible behavior belongs elsewhere. |
| Shared policy | `templates-shared-policy` | policy | repository | 共有ポリシー | yes | `docs/policy-authoring.md` defines this ownership class as generally applicable, artifact- and engine-independent operating behavior authored canonically in the Policy corpus. It is one member of the six-class policy-ownership taxonomy reviewed together here. |
| Context policy | `templates-context-policy` | policy | repository | コンテキストポリシー | yes | `docs/policy-authoring.md` defines this ownership class as artifact- and engine-independent policy content selected only for an operational context such as review. It is distinct from `templates-policy-context`: **Context policy is selected policy content; Policy context is the named semantic selector/authority boundary in `.agent-policy.yml` that selects profiles, repository-local policy, and overrides for an output.** |
| Repository-local policy | `templates-repository-local-policy` | policy | repository | リポジトリローカルポリシー | yes | `docs/policy-authoring.md` assigns repository-specific facts, invariants, justified extensions, and explicit permitted overrides to this ownership class. |
| Artifact contract | `templates-artifact-contract` | policy | repository | アーティファクト契約 | yes | `docs/policy-authoring.md` uses this ownership class for requirements that define what a produced Skill, Web application, CLI, library, service, or other artifact must contain or do, separating artifact semantics from coding-agent policy. |
| Adapter/renderer requirement | `templates-adapter-renderer-requirement` | policy | repository | アダプター／レンダラー要件 | yes | `docs/policy-authoring.md` uses this ownership class when behavior depends on a particular agent, platform, protocol, command surface, renderer, or output format rather than shared policy semantics. |
| Explanatory material | `templates-explanatory-material` | policy | repository | 説明資料 | yes | `docs/policy-authoring.md` separates rationale, examples, history, proposals, and other non-normative text from policy and artifact-contract authority. |
| Policy override | `templates-policy-override` | policy | repository | ポリシーオーバーライド | yes | `docs/configuration.md` makes override declarations explicit exception records and separates them from replacement policy text. |
| Template source artifact | `templates-webapp-template-source-artifact` | webapp | repository | テンプレートソースアーティファクト | yes | `docs/architecture/distribution-boundary.md` distinguishes the complete maintainer checkout from the copyable distribution. Confusing the two changes repository ownership. |
| Template distribution artifact | `templates-webapp-template-distribution-artifact` | webapp | repository | テンプレート配布アーティファクト | yes | `docs/architecture/distribution-boundary.md` defines the committed `template/` subtree copied byte-for-byte to a new product repository. |
| Product repository artifact | `templates-webapp-product-repository-artifact` | webapp | repository | プロダクトリポジトリアーティファクト | yes | `docs/architecture/distribution-boundary.md` distinguishes a generated/customized product repository from both source and distribution artifacts. |
| Product mode | `templates-webapp-product-mode` | webapp | repository | プロダクトモード | yes | `template/docs/architecture/implementation-evidence.md` section **Template and product modes** defines when concrete implementation boundaries, proofs, commands, and release gates become required. `template/docs/architecture/release-evidence.md` distinguishes product-mode revision binding, execution provenance, command/gate results, and approval from template residue. `template/docs/architecture/release-bundle.md` likewise defines template/product handoff semantics for the exact candidate and active contract bytes. Together these documents define the product-mode boundary paired with the canonical `templates-webapp-template-mode`. |
| Release bundle | `templates-webapp-release-bundle` | webapp | repository | リリースバンドル | yes | `template/docs/architecture/release-bundle.md` separates exact handoff bytes from release evidence and defines deterministic artifact closure. |
| Contract family | `templates-webapp-contract-family` | webapp | repository | コントラクトファミリー | yes | `template/docs/architecture/contract-completeness.md` and release-bundle guidance use stable contract-family identity, version history, migrations, active/retired state, and evidence coverage. |

### Policy ownership-taxonomy boundary

The six ownership classes above are peers from `docs/policy-authoring.md` and are
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
an operational context. The canonical entries should relate those concepts so
search and review do not treat the reversed names as synonyms.

## Deferred repository candidates

These concepts are meaningful but are intentionally deferred until the first
expansion above is reviewed. Deferral is based on semantic grouping or unresolved
boundaries rather than pull-request size alone.

| Candidate term | Proposed ID | Likely owner | Reason to defer |
| --- | --- | --- | --- |
| Stable release | `templates-policy-stable-release` | policy | `docs/architecture.md` distinguishes the evolving development branch from the stable executable release. Review this together with the stable release descriptor and promoted toolchain revision below. |
| Stable release descriptor | `templates-policy-stable-release-descriptor` | policy | `docs/architecture.md` identifies `release/toolchain.json` as the stable release descriptor that may continue pointing at an earlier reviewed commit while the `policy` branch advances. Its identity and lifecycle boundary should be reviewed with Stable release and Promoted toolchain revision. |
| Promoted toolchain revision | `templates-policy-promoted-toolchain-revision` | policy | `docs/architecture.md` describes the reviewed candidate full SHA written into the release descriptor and integrated bootstrap manifest during promotion. Review its role relative to the stable release identity and the later promotion-state commit as one lifecycle set. |
| Bootstrap trust seed | `templates-policy-bootstrap-trust-seed` | policy | Security-sensitive concept; should be added with release/trust terminology as one coherent group. |
| Managed repository | `templates-policy-managed-repository` | policy | Widely used in Policy docs, but the exact transition boundary from unmanaged/prepared/finalized should be stated precisely first. |
| Candidate revision | `templates-webapp-candidate-revision` | webapp | `release-bundle.md` defines several revision roles; they should be added as one related set rather than piecemeal. |
| Merge-test revision | `templates-webapp-merge-test-revision` | webapp | Same revision-role group as Candidate revision. |
| Released revision | `templates-webapp-released-revision` | webapp | Same revision-role group as Candidate revision. |
| Deployed revision | `templates-webapp-deployed-revision` | webapp | Same revision-role group as Candidate revision. |
| Index-guided navigation | `templates-index-guided-navigation` | site | `PUBLISHING.md` defines this specifically as the projection driven by provider-owned `index.md` structure. It is deferred because publication ownership terms are the higher-priority Site expansion, not because its boundary is unclear. |

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
| Service Worker | `external-web-service-worker` | site | defer | Relevant to Site PWA behavior, but not required to understand the first terminology expansion. |
| Progressive Web App | `external-web-progressive-web-app` | site | defer | Same reason as Service Worker; add when PWA terminology becomes a glossary navigation need. |

## Japanese-label policy for this inventory

Japanese text in the table is discovery metadata only. The canonical entry must
still use English `term` plus English repository `definition`, or English
external `summary` plus `authority`.

A proposed Japanese label is not automatically accepted merely because it is in
this inventory. Before committing it, prefer terminology already used naturally
in repository documentation or standard Japanese technical usage. Alternative
spellings may be stored as `localized_labels.ja.aliases` when they improve
lookup. No Japanese definition is required.

## Implementation order after inventory review

1. Add the Site-owned terms to `site/docs/glossary.yml`.
2. Add Skill-owned terms to `skill/docs/glossary.yml`.
3. Add Policy-owned terms to `policy/docs/glossary.yml`.
4. Add Webapp-owned terms to `webapp/docs/glossary.yml`.
5. For every provider PR, run the provider-local checks and the Site compatibility
   workflow against the exact proposed revision.
6. After provider merges, promote their exact full SHAs through a coordinated
   Site lock update and verify the integrated JSON and human glossary viewer.
7. Add cross-provider `related_terms` only after every referenced term exists in
   the locked integrated set.

External-term expansion is a separate curation pass because its authority URLs
and version sensitivity require current upstream verification.
