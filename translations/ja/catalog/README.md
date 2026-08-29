# Production Composition カタログ

> **参考訳（非正本）:** この文書は英語版 `catalog/README.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

`catalog.json` は、この `composition` revision で利用可能な production component authority と recipe authority の閉じた inventory です。

各 component ID は `components/<component-id>/component.json` に、各 recipe ID は `recipes/<recipe-id>.json` に解決されます。catalog の配列は重複せず辞書順に並び、validation では物理的な authority directory / file と正確に一致することが要求されます。

## Consumer 向け選択ガイド

recipe は、言語、framework、deployment platform ではなく、作成する artifact の種類から選択します。

| 作成するもの | Recipe | 基本 material と挙動 | Lifecycle の基準 |
| --- | --- | --- | --- |
| Agent Skill repository | `skill` | `SKILL.md` を含む Skill 構造、開発ガイダンス、Skill 固有 validation | `lifecycle.composition-state` のみ。application capability と contract/release lifecycle component は opt-in |
| browser-facing Web application repository | `webapp` | route、surface、可視 UI state、viewport、Web 固有 validation、framework-neutral な browser application 構造 | `lifecycle.composition-state` + implementation evidence + contract evolution。release lifecycle は `lifecycle.release-bundle` による opt-in |

optional application capability は、外部から見える product の挙動に基づいて選択します。必要な capability を直接 include すれば、Composer が dependency を推移的に解決します。

| 必要なもの | Include | 自動的に追加されるもの | 追加される契約 |
| --- | --- | --- | --- |
| 維持対象となる implementation runtime、dependency/distribution 規則、command、environment、deployment lifecycle | `capability.runtime` | — | runtime の選択・保守契約 |
| packaged command-line interface | `capability.cli` | `capability.runtime` + implementation evidence（および contract evolution） | executable-proof enforcement を伴う machine-readable caller-visible CLI contract |
| MCP protocol endpoint/interface | `capability.mcp` | `capability.runtime` + implementation evidence（および contract evolution） | executable protocol-proof enforcement を伴う machine-readable MCP transport / operation contract と、定性的な client / security / semantic-equivalence guidance |
| MCP Apps extension UI | `capability.mcp-apps` | `capability.mcp`、したがって `capability.runtime` + implementation evidence（および contract evolution） | protocol / browser / end-to-end proof enforcement を伴う machine-readable Apps extension / View / tool-association contract と、定性的な bridge / visibility / sandbox / fallback guidance |
| installable な Progressive Web App として、network loss、freshness、mobile application icon、update behavior を意図的に定義する | `capability.pwa` (`webapp`) | implementation evidence（および contract evolution） | cache algorithm や service-worker library を規定せず、Web App Manifest、offline/freshness、Android/iOS application identity compatibility、update lifecycle の contract を追加 |
| 独立して到達可能な non-browser service | `capability.service` | `capability.runtime` + implementation evidence（および contract evolution） | machine-readable service operation contract と executable-proof enforcement |
| application runtime によって提供される standalone browser-facing interface | `capability.web-interface` | `capability.runtime` + implementation evidence（および contract evolution） | browser/executable proof-strength enforcement を伴う machine-readable external endpoint contract と、定性的な security / failure-isolation guidance |

browser-facing artifact であることだけでは、`capability.runtime` や `capability.web-interface` は必要になりません。たとえば static/CDN Webapp は optional component なしで `webapp` recipe を使用できます。runtime-bound capability は、product が実際にその挙動を公開するときだけ追加します。

lifecycle component は product workflow に応じて選択します。`skill` recipe は各 lifecycle level を独立して公開します。`webapp` recipe は contract evolution と implementation evidence を baseline に含み、`lifecycle.release-bundle` を top-level の release choice として公開します。recipe が公開している必要な lifecycle behavior のうち最上位のものを選択すれば、その prerequisite は自動解決されます。

| 必要なもの | Include | Dependency closure |
| --- | --- | --- |
| versioned contract evolution と migration | `lifecycle.contract-evolution` (`skill`) | contract evolution のみ |
| implementation boundary、proof、authoritative command、release gate | `lifecycle.implementation-evidence` (`skill`; Webapp baseline) | implementation evidence -> contract evolution |
| product-owned fixed-argv release execution と candidate verification | `lifecycle.release-execution` (`skill`) | release execution -> implementation evidence -> contract evolution |
| revision-bound release evidence production | `lifecycle.release-evidence` (`skill`) | release evidence -> release execution -> implementation evidence -> contract evolution |
| deterministic release bundle と one-command release orchestration | `lifecycle.release-bundle` (`skill` または `webapp`) | release bundle -> release evidence -> release execution -> implementation evidence -> contract evolution |

したがって最小の static Webapp は空の include list を使用し、browser contract と implementation-evidence / contract-evolution support を受け取りますが、release execution / evidence / bundle material は含みません。

```json
{
  "schema_version": 1,
  "recipe": "webapp",
  "components": {"include": [], "exclude": []},
  "parameters": {}
}
```

release-ready Webapp は top-level の release component だけを選択します。

```json
{
  "schema_version": 1,
  "recipe": "webapp",
  "components": {
    "include": ["lifecycle.release-bundle"],
    "exclude": []
  },
  "parameters": {}
}
```

Composition release lifecycle を使用しない runtime-backed Webapp では、runtime を独立して選択できます。

```json
{
  "schema_version": 1,
  "recipe": "webapp",
  "components": {
    "include": ["capability.runtime"],
    "exclude": []
  },
  "parameters": {}
}
```

MCP Apps UI を公開し、完全な release workflow を使用する Skill では、最上位の2つだけを要求できます。resolver が prerequisite を追加します。

```json
{
  "schema_version": 1,
  "recipe": "skill",
  "components": {
    "include": ["capability.mcp-apps", "lifecycle.release-bundle"],
    "exclude": []
  },
  "parameters": {}
}
```

### Webapp v3 から v4 への upgrade

`artifact.webapp-core` v4 では artifact dependency closure が変わるため、既存の managed Webapp が v3 から移行する場合は明示的な component-version compatibility boundary を越えます。ordinary `update` ではなく `upgrade` を使用してください。

v3 が推移的に選択していた完全な release lifecycle を repository で維持する場合、v4 の upgrade configuration で `lifecycle.release-bundle` を明示的に include する必要があります。release execution / evidence / bundle behavior が不要なら include せず、apply 前に upgrade plan を確認してください。

v3 の release contract file は `seed` material だったため、release lifecycle を deselect する upgrade でも、Composer は consumer-owned bytes を自動削除せず保存します。apply 後に保存されている `contracts/release-execution.json`、`contracts/release-evidence.json`、`contracts/release-bundle.json` は、v4 baseline では登録済み contract ではありません。contract registry は意図的に closed なので、consumer がこれらを `contracts/` の外（たとえば `release-history/`）へ archive するか、履歴として不要であることを確認して削除するまで validation は失敗します。この cleanup は consumer-owned です。upgrade apply の後に cleanup を行い、その後 `validate` を再実行してください。

repository に同名の lifecycle file が残っているだけで release validator が選択されることはありません。selection authority は `.template-composition/lock.json` の resolved component set です。上記 cleanup が必要なのは closed な contract-document inventory のためであり、release-validator dispatch のためではありません。

`apply` の前に `plan` を使い、正確に解決された component closure と materialized file action を確認してください。直接選択可能な component の machine-readable source of truth は recipe descriptor です。

## Closure rules

Production catalog validation は次を保証します。

- descriptor / recipe / schema が妥当であること。
- component source file の宣言が正確であること。
- dependency / conflict の target が存在し、dependency graph が非巡回であること。
- generic capability / lifecycle が artifact-specific authority から独立していること。
- recipe reference が妥当で、required / default / optional selection が互いに素であること。
- 登録された contract ID、document path、schema path が repository 全体で一意であること。
- 登録された各 contract document / schema / migration を1つの component が所有すること。
- `contracts/manifest.json` に対する generated owner が一意であること。
- 解決済み `contract_registrations` から manifest が deterministic に render されること。
- composition lock では解決された各 component に file-ownership witness が必要なため、解決可能なすべての production component が少なくとも1つの materialized file を所有すること。
- material destination が portable で、単一 owner を持つこと。
- production Skill composition と Webapp composition の materialized validation が成功すること。

catalog は source authority であり、consumer material でも execution-hook registry でもありません。

Composer はこの閉じた source graph を検証し、1つの正確で clean な Git revision に対して recipe と consumer configuration を解決し、initial materialization が成功した後に得られた component / file closure を `.template-composition/lock.json` に書き込みます。Generated material は allowlist に含まれる declarative generator ID を通じてのみ dispatch されます。

unmanaged target では、initial composition は managed-state transition を推測せず、既存の composition lock がある場合は拒否します。既存の managed repository では代わりに明示的な operation を使います。`update` は lock schema v2 に記録された normalized intent を維持したまま descendant の Composition source revision へ進み、`upgrade` は recipe、component selection、parameter、component version などを変更するための明示的な新しい configuration を受け取ります。どちらの operation も汎用 merge engine ではありません。local で変更された `managed` / `generated` material や、owner / ownership-mode transition は上書きや推測を行わず fail closed します。
