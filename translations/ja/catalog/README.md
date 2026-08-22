# Production Composition カタログ

> **参考訳（非正本）:** この文書は英語版 `catalog/README.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

`catalog.json` は、この `composition` revision で利用可能な production component authority と recipe authority の閉じた inventory です。

各 component ID は `components/<component-id>/component.json` に、各 recipe ID は `recipes/<recipe-id>.json` に解決されます。catalog の配列は重複せず辞書順に並び、validation では物理的な authority directory / file と正確に一致することが要求されます。

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
