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
| Public interface selection contract | `templates-skill-interface-selection-contract` | skill | repository | 公開インターフェース選択契約 | yes | `template/INTERFACES.md` owns preferred agent route and deterministic fallback order while detailed caller-visible behavior belongs elsewhere. |
| Shared policy | `templates-shared-policy` | policy | repository | 共有ポリシー | yes | `docs/policy-authoring.md` distinguishes shared, context, repository-local, artifact-contract, adapter, and explanatory ownership classes. |
| Context policy | `templates-context-policy` | policy | repository | コンテキストポリシー | yes | `docs/policy-authoring.md` defines artifact- and engine-independent behavior selected only for an operational context such as review. |
| Repository-local policy | `templates-repository-local-policy` | policy | repository | リポジトリローカルポリシー | yes | `docs/policy-authoring.md` assigns repository-specific facts, invariants, extensions, and explicit permitted overrides to this class. |
| Policy override | `templates-policy-override` | policy | repository | ポリシーオーバーライド | yes | `docs/configuration.md` makes override declarations explicit exception records and separates them from replacement policy text. |
| Template source artifact | `templates-webapp-template-source-artifact` | webapp | repository | テンプレートソースアーティファクト | yes | `docs/architecture/distribution-boundary.md` distinguishes the complete maintainer checkout from the copyable distribution. Confusing the two changes repository ownership. |
| Template distribution artifact | `templates-webapp-template-distribution-artifact` | webapp | repository | テンプレート配布アーティファクト | yes | `docs/architecture/distribution-boundary.md` defines the committed `template/` subtree copied byte-for-byte to a new product repository. |
| Product repository artifact | `templates-webapp-product-repository-artifact` | webapp | repository | プロダクトリポジトリアーティファクト | yes | `docs/architecture/distribution-boundary.md` distinguishes a generated/customized product repository from both source and distribution artifacts. |
| Release bundle | `templates-webapp-release-bundle` | webapp | repository | リリースバンドル | yes | `template/docs/architecture/release-bundle.md` separates exact handoff bytes from release evidence and defines deterministic artifact closure. |
| Contract family | `templates-webapp-contract-family` | webapp | repository | コントラクトファミリー | yes | `template/docs/architecture/contract-completeness.md` and release-bundle guidance use stable contract-family identity, version history, migrations, active/retired state, and evidence coverage. |

## Deferred repository candidates

These concepts are meaningful but are intentionally deferred until the first
expansion above is reviewed. Deferral keeps the first content PRs small and makes
concept boundaries easier to review.

| Candidate term | Proposed ID | Likely owner | Reason to defer |
| --- | --- | --- | --- |
| Stable release | `templates-policy-stable-release` | policy | Important lifecycle concept, but its boundary with release descriptor and promoted toolchain revision should be reviewed together. |
| Bootstrap trust seed | `templates-policy-bootstrap-trust-seed` | policy | Security-sensitive concept; should be added with release/trust terminology as one coherent group. |
| Managed repository | `templates-policy-managed-repository` | policy | Widely used in Policy docs, but the exact transition boundary from unmanaged/prepared/finalized should be stated precisely first. |
| Product mode | `templates-webapp-product-mode` | webapp | Natural counterpart to Template mode, but should be reviewed with evidence contract mode semantics across all contract families. |
| Candidate revision | `templates-webapp-candidate-revision` | webapp | `release-bundle.md` defines several revision roles; they should be added as one related set rather than piecemeal. |
| Merge-test revision | `templates-webapp-merge-test-revision` | webapp | Same revision-role group as Candidate revision. |
| Released revision | `templates-webapp-released-revision` | webapp | Same revision-role group as Candidate revision. |
| Deployed revision | `templates-webapp-deployed-revision` | webapp | Same revision-role group as Candidate revision. |
| Guided navigation | `templates-guided-navigation` | site | Useful Site term, but less likely than publication ownership terms to change provider implementation decisions. |

## External terminology candidates

External terms are not repository-owned definitions. They require a stable
external semantic domain plus upstream, normative, or conventional authority.
They should be added only when their presence materially improves discovery of a
repository-specific concept.

| Candidate term | Proposed ID | Curator | Initial decision | Notes |
| --- | --- | --- | --- | --- |
| Model Context Protocol | `external-mcp-model-context-protocol` | skill/site | defer | Skill uses MCP extensively, but authority/version selection should be curated from current official MCP specifications before creating the entry. |
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
