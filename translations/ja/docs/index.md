# Composition ドキュメント索引

> **参考訳（非正本）:** この文書は英語版 `docs/index.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

## ここから始める

- [Website と Web application の選び方](guides/website-webapp-selection.md) — browser-facing product の artifact を static/dynamic、hosting、runtime、PWA 技術ではなく product identity と caller-visible behavior から分類します。
- [Website product walkthrough](guides/website-product-walkthrough.md) — 初めて content/document-oriented Website を作る場合の canonical first-use path です。別 repository の Project Docs を `website` 選択、`inspect -> plan -> apply -> validate`、Website contracts、planning/product evidence、implementation、browser proof まで進めます。
- [Webapp product walkthrough](guides/webapp-product-walkthrough.md) — 初めて Web application を作る場合はここから始めます。別 product repository から Task Ledger を zero-to-one で進め、installation、`composition.json`、`inspect -> plan -> apply -> validate`、ownership、implementation、product tests、evidence、optional Policy、後続 update/upgrade までを追体験します。
- [初見者向け Composition concepts](guides/composition-concepts.md) — recipe、artifact、component、contract、material、lock など、この repository 固有の意味を持つ語の mental model を補助的に説明します。
- [Composition の評価](evaluation-guide.md) — canonical な independent clean-room evaluator entry point です。
- [Composition の利用方法](consumer-guide.md) — consumer repository の作成、inspect、update、upgrade、recovery、ownership、conflict を扱うタスク指向 workflow です。
- [Recipe と component の選び方](../catalog/README.md) — `skill`、`website`、`webapp` を選び、product が実際に必要とする capability または lifecycle behavior だけを選択します。
- [プロダクトリリースの生成](release-guide.md) — product evidence、fixed executable argv、exact candidate revision、transactional release production、rollback、recovery を説明します。
- [Composer リファレンス](reference/composer.md) — 正確な CLI mode/options、inspect states、plan fields、ownership semantics、recovery rules、managed lifecycle diagnostics を説明します。
- [Composition 概要](../README.md) — 現在の authority、lifecycle summary、safety model、documentation entry points を説明します。

## Composition architecture

- [Composition model](architecture/composition-model.md) — foundation、artifact、capability、lifecycle、ownership、intent、lock semantics を説明します。
- [Composer architecture](architecture/composer-mvp.md) — resolver precedence、plan/apply safety、trust boundaries、managed reconciliation、recovery protocol を説明します。
- [Production catalog architecture](architecture/catalog.md) — closed component と recipe inventory を説明します。
- [Generated contract manifest](architecture/generated-contract-manifest.md) — deterministic generated contract registry architecture を説明します。

## 公開境界

- [公開境界](publication-catalog.md) — この provider が統合ドキュメントサイトへ何を公開し、その境界をなぜ設けるかを説明します。

## Agent Skill artifact

- [Skill ドキュメント索引](../components/artifact.skill-core/files/docs/) — Skill-specific profiles、architecture、responsibility map を説明します。
- [Skill contract scaffold](../components/artifact.skill-core/files/SKILL.md) — trigger、workflow、resources、routing、output、validation、safety contract を説明します。

## Shared Web foundation

- [Website / Web application 判断ガイド](guides/website-webapp-selection.md) — artifact selection と shared Web semantics / artifact-specific semantics の境界を説明します。
- [Shared browser identity contract](../components/foundation.web/files/contracts/browser-identity.json) — product-neutral browser identity。
- [Shared routes contract](../components/foundation.web/files/contracts/routes.json) — generalized canonical path、alias、deep-link expectation、navigation accessibility。
- [Shared viewports contract](../components/foundation.web/files/contracts/viewports.json) — responsive viewport と input-capability expectation。

## Website artifact

- [Website product walkthrough](guides/website-product-walkthrough.md) — concrete content/document-oriented Website の canonical first-use path です。
- [Website component descriptor](../components/artifact.website-core/component.json) — Website artifact の dependency、contract、validator、material。
- [Website structure contract](../components/artifact.website-core/files/contracts/site-structure.json) — page inventory、hierarchy、home page、primary navigation、shared-route binding。
- [Website document metadata contract](../components/artifact.website-core/files/contracts/document-metadata.json) — title、description、language、canonical-path policy、indexability、social-preview intent。
- [Website discovery contract](../components/artifact.website-core/files/contracts/site-discovery.json) — canonical origin、robots、sitemap、feed discovery semantics。

## Web application artifact

- [Webapp product walkthrough](guides/webapp-product-walkthrough.md) — concrete Web application の canonical first-use path です。
- [Web application ドキュメント索引](../components/artifact.webapp-core/files/docs/) — shared Web foundation 上の application-specific contract と validation を説明します。
- [Web application template contract](../components/artifact.webapp-core/files/TEMPLATE.md) — framework-neutral browser application obligations を説明します。

## 再利用可能な application capabilities

- [Implementation runtime decision record](../components/capability.runtime/files/RUNTIME.md) — implementation ecosystem、commands、dependencies、environment、distribution、deployment choices を説明します。
- [Implementation runtime の選択](../components/capability.runtime/files/docs/runtime-selection.md) — implementation ecosystem と dependency workflow を選択する criteria を説明します。
- [Progressive Web App capability](../components/capability.pwa/files/PWA.md) — Website / Webapp の双方で利用できる artifact-neutral な installability、offline/freshness、application identity、update behavior。
- [Packaged CLI interface](../components/capability.cli/files/CLI_INTERFACE.md) — caller-visible CLI behavior を説明します。
- [MCP interface](../components/capability.mcp/files/MCP_INTERFACE.md) — MCP protocol、transports、client roles、semantic equivalence を説明します。
- [MCP transport guidance](../components/capability.mcp/files/docs/mcp-transports.md) — stdio と Streamable HTTP の guidance を説明します。
- [MCP Apps extension](../components/capability.mcp-apps/files/MCP_APPS.md) — Host/View bridge、resources、sandbox、fallback contract を説明します。
- [MCP Apps guidance](../components/capability.mcp-apps/files/docs/mcp-apps.md) — MCP Apps の implementation guidance を説明します。
- [Standalone browser interface](../components/capability.web-interface/files/WEB_INTERFACE.md) — browser-facing routing、security、health、failure semantics を説明します。
- [Headless service interface](../components/capability.service/files/SERVICE_INTERFACE.md) — non-browser service behavior、health、security、lifecycle を説明します。

## 再利用可能な lifecycle contracts

- [Composition state](../components/lifecycle.composition-state/files/docs/architecture/composition-state.md) — self-contained resolved-state と material-ownership validation を説明します。
- [Contract evolution](../components/lifecycle.contract-evolution/files/docs/architecture/contract-evolution.md) — closed contract registry、schema binding、version histories、migrations を説明します。
- [Implementation evidence](../components/lifecycle.implementation-evidence/files/docs/architecture/implementation-evidence.md) — implementation boundaries、proofs、commands、release gates を説明します。
- [Release evidence](../components/lifecycle.release-evidence/files/docs/architecture/release-evidence.md) — revision-bound execution provenance と release decisions を説明します。
- [Release bundle](../components/lifecycle.release-bundle/files/docs/architecture/release-bundle.md) — deterministic digest-closed handoff を説明します。

## Historical provenance

- [Composition authority migration](migrations/composition-authority-migration.md) — authority cutover、provider migration、branch retirement、immutable PR provenance の統合 chronology です。

## Machine-readable authorities

- [Production catalog guide](../catalog/README.md) — catalog closure rules、path conventions、consumer recipe/component selection guidance を説明します。
- [Composition schema guide](../schemas/README.md) — component、recipe、configuration、lock、transaction、catalog schema responsibilities を説明します。
