# Composition ドキュメント索引

> **参考訳（非正本）:** この文書は英語版 `docs/index.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

## ここから始める

- [Webapp product walkthrough](guides/webapp-product-walkthrough.md) — **初めて Web application を作る場合はここから始めます。** 別 product repository から Task Ledger を zero-to-one で進め、installation、`composition.json`、`inspect -> plan -> apply -> validate`、ownership、implementation、product tests、evidence、optional Policy、後続 update/upgrade までを一つの経路で追体験します。
- [Composition の利用方法](consumer-guide.md) — consumer repository の作成、inspect、update、upgrade、recovery、ownership、conflict を扱うタスク指向の workflow です。
- [Recipe と component の選び方](../catalog/README.md) — `skill` と `webapp` のどちらを使うかを決め、product が実際に必要とする application capability または lifecycle behavior だけを選択します。
- [プロダクトリリースの生成](release-guide.md) — product evidence、fixed executable argv、exact candidate revision、transactional release production、rollback、recovery を説明します。
- [Composer リファレンス](reference/composer.md) — 正確な CLI mode/options、inspect states、plan fields、ownership semantics、recovery rules、managed lifecycle diagnostics を説明します。
- [Composition 概要](../README.md) — 現在の authority、lifecycle summary、safety model、documentation entry points を説明します。

first-use walkthrough を architecture / contract reference より前に置いています。新しい consumer は最初の task を完了してから、判断に必要な時点で deeper model を参照できます。

## Composition architecture

- [Composition model](architecture/composition-model.md) — artifact、capability、lifecycle、ownership、intent、lock semantics を説明します。
- [Composer MVP](architecture/composer-mvp.md) — resolver precedence、plan/apply safety、trust boundaries、managed reconciliation、recovery protocol を説明します。
- [Production catalog architecture](architecture/catalog.md) — closed component と recipe inventory を説明します。
- [Generated contract manifest](architecture/generated-contract-manifest.md) — deterministic generated contract registry architecture を説明します。

## 公開境界

- [公開境界](publication-catalog.md) — この provider が統合ドキュメントサイトへ何を公開し、その境界をなぜ設けるかを説明します。

## Agent Skill artifact

- [Skill ドキュメント索引](../components/artifact.skill-core/files/docs/) — Skill-specific profiles、architecture、responsibility map を説明します。
- [Skill contract scaffold](../components/artifact.skill-core/files/SKILL.md) — trigger、workflow、resources、routing、output、validation、safety contract を説明します。

## 再利用可能な application capabilities

- [Implementation runtime decision record](../components/capability.runtime/files/RUNTIME.md) — implementation ecosystem、commands、dependencies、environment、distribution、deployment choices を説明します。
- [Implementation runtime の選択](../components/capability.runtime/files/docs/runtime-selection.md) — implementation ecosystem と dependency workflow を選択するための criteria を説明します。
- [Packaged CLI interface](../components/capability.cli/files/CLI_INTERFACE.md) — caller-visible CLI behavior を説明します。
- [MCP interface](../components/capability.mcp/files/MCP_INTERFACE.md) — MCP protocol、transports、client roles、semantic equivalence を説明します。
- [MCP transport guidance](../components/capability.mcp/files/docs/mcp-transports.md) — stdio と Streamable HTTP の guidance を説明します。
- [MCP Apps extension](../components/capability.mcp-apps/files/MCP_APPS.md) — Host/View bridge、resources、sandbox、fallback contract を説明します。
- [MCP Apps guidance](../components/capability.mcp-apps/files/docs/mcp-apps.md) — MCP Apps の implementation guidance を説明します。
- [Standalone browser interface](../components/capability.web-interface/files/WEB_INTERFACE.md) — browser-facing routing、security、health、failure semantics を説明します。
- [Headless service interface](../components/capability.service/files/SERVICE_INTERFACE.md) — non-browser service behavior、health、security、lifecycle を説明します。

## Web application artifact

- [Webapp product walkthrough](guides/webapp-product-walkthrough.md) — concrete Web application の canonical first-use path です。
- [Web application ドキュメント索引](../components/artifact.webapp-core/files/docs/) — Web-specific contracts と validation を説明します。
- [Web application template contract](../components/artifact.webapp-core/files/TEMPLATE.md) — framework-neutral browser product obligations を説明します。

## 再利用可能な lifecycle contracts

- [Composition state](../components/lifecycle.composition-state/files/docs/architecture/composition-state.md) — self-contained resolved-state と material-ownership validation を説明します。
- [Contract evolution](../components/lifecycle.contract-evolution/files/docs/architecture/contract-evolution.md) — closed contract registry、schema binding、version histories、migrations を説明します。
- [Implementation evidence](../components/lifecycle.implementation-evidence/files/docs/architecture/implementation-evidence.md) — implementation boundaries、proofs、commands、release gates を説明します。
- [Release evidence](../components/lifecycle.release-evidence/files/docs/architecture/release-evidence.md) — revision-bound execution provenance と release decisions を説明します。
- [Release bundle](../components/lifecycle.release-bundle/files/docs/architecture/release-bundle.md) — deterministic digest-closed handoff を説明します。

## Historical provenance

- [Composition authority migration](migrations/composition-authority-migration.md) — authority cutover、provider migration、branch retirement、immutable PR provenance の統合 chronology です。stage-specific implementation notes は repository maintenance のためだけに保持され、reader publication pages には含まれません。

## Machine-readable authorities

- [Production catalog guide](../catalog/README.md) — catalog closure rules、path conventions、consumer recipe/component selection guidance を説明します。
- [Composition schema guide](../schemas/README.md) — component、recipe、configuration、lock、transaction、catalog schema responsibilities を説明します。
