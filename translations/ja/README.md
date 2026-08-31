# Composition

> **参考訳（非正本）:** この文書は英語版 `README.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

Composition は `TakashiSasaki/templates` における canonical authority であり、再利用可能な Agent Skill、Website、Web application の artifact semantics、shared foundation、application capability、lifecycle contract、recipe、schema、および deterministic Composer を管理します。

consumer repository は、artifact recipe と明示的な consumer intent から生成されます。Composer は deterministic な component closure を解決し、source files と generated files を materialize し、解決済み状態を `.template-composition/lock.json` に記録して、consumer repository を自己完結した状態にします。

## ここから始める

**browser-facing product を作る場合**は、まず [Website と Web application の選び方](docs/guides/website-webapp-selection.md) を参照してください。artifact は product identity と caller-visible behavior から選びます。content/document の discovery と navigation が中心なら `website`、task/state/action-oriented な browser product なら `webapp` です。static generation、server rendering、client rendering、CDN hosting、runtime selection、PWA 技術は artifact type の判定条件ではありません。

artifact を選んだ後は、対応する zero-to-one path を進めます。

- [Website product walkthrough](docs/guides/website-product-walkthrough.md) — 別 product repository から content/document-oriented Website を作成し、Composition lifecycle、Website contract、implementation evidence、browser proof まで進めます。Webapp-only の surface や UI state は導入しません。
- [Webapp product walkthrough](docs/guides/webapp-product-walkthrough.md) — 別 product repository から interactive Web application を作成し、installation、`composition.json`、`inspect -> plan -> apply -> validate`、ownership、implementation、product test、evidence まで進めます。
- [Agent Skill first-use walkthrough](docs/guides/skill-first-use-walkthrough.md) — Composition architecture を先に学ばず reusable Agent Skill を作成する first-use path です。

**独立した clean-room evaluation を実行する場合**は、[Evaluating Composition](docs/evaluation-guide.md) から始めてください。これは formal protocol、scorecard guide、scorecard schema、および output sequence への canonical evaluator entry point です。この maintainer/evaluator path は通常の consumer onboarding とは分離され、consumer bootstrap contract を変更しません。

既存 managed repository の保守、Composition update/upgrade、recovery、ownership、conflict handling には [Using Composition](docs/consumer-guide.md) を使用します。

通常の consumer は installable な `skills/composition/` runner を使用し、`TakashiSasaki/templates` や provider branch を clone しません。local prerequisite は CPython 3.11 から 3.14 であり、通常の consumer execution に Git は不要です。runner は immutable な full-SHA Composition revision を選択し、その revision の GitHub HTTPS archive を OS の temporary directory に取得して source-file digest inventory を検証し、正確に validation 済みの Python runtime を構築または再利用し、consumer repository を target として Composer を呼び出した後、source snapshot を削除します。Composition authority 保守者は direct reviewed-source-checkout entrypoint を引き続き利用でき、その path では Git が authority-maintenance prerequisite です。

名前付き runtime cache は performance のため意図的に persistent ですが、通常の source acquisition は disposable です。templates checkout は consumer state ではなく、runner cache に保持されません。archive snapshot から実行する managed `update` / `upgrade` は、old-to-new revision ancestry を GitHub compare API で検証し、ancestry を確立できない場合は fail closed します。

正確な CLI options、inspect states、plan fields、ownership semantics、recovery rules、diagnostic codes、および exit behavior については、[Composer reference](docs/reference/composer.md) を参照してください。

architecture、provider-specific documentation、および machine-readable authority guides については、[Composition documentation index](docs/index.md) を参照してください。

## Lifecycle の概要

公開されている Composer workflow は次のとおりです。

```text
inspect -> plan -> apply -> validate
```

`initial` は、明示的な consumer configuration から新しい managed repository を作成します。`update` は、lock に記録済みの normalized intent を維持したまま、descendant である Composition source revision へ repository を reconcile します。`upgrade` は明示的な新しい consumer intent を受け取り、component-version の変更など compatibility boundary を越える変更で必須です。managed mutation が中断された場合は、任意の local state を推測または merge するのではなく、durable transaction marker から deterministic に roll-forward して recovery します。

Composition は意図的に fail-closed です。planning は read-only であり、mutation の前には完全な plan が作成されます。Composition-owned bytes に対する local changes は暗黙に上書きされず、未対応の ownership transition や component transition は推測せず拒否されます。

## Foundation、artifact、capability、lifecycle

production catalog は、再利用可能な authority を四つの reusable component role に分離します。

- `foundation.*` は artifact が推移的に導入する shared mandatory baseline semantics を定義します。`foundation.web` は Website / Webapp が共通に利用する browser identity、generalized routes、viewports を所有します。
- `artifact.*` は何を作るかを定義します。現在は `artifact.skill-core`、`artifact.website-core`、`artifact.webapp-core` があります。browser artifact はそれぞれ、自身の domain-specific contract と、その artifact-owned semantics に対する evidence-target derivation / validator logic を所有します。
- `capability.*` は runtime、CLI、MCP、MCP Apps、PWA、standalone browser interface、headless service など再利用可能な optional behavior を定義します。
- `lifecycle.*` は composition-state、contract-evolution、implementation-evidence、checkpoint、release-evidence、release-bundle behavior を定義します。`lifecycle.implementation-evidence` は artifact / capability validator が利用する artifact-neutral evidence machinery を所有します。

recipe は artifact をちょうど1つ選択します。foundation component は consumer が直接選ぶものではなく、artifact dependency から推移的に解決されます。`recipes/skill.json` は `artifact.skill-core` を選択します。`recipes/website.json` は `artifact.website-core` を選択し、`foundation.web` 上に Website page structure、document metadata、discovery、Website-specific evidence を追加します。`recipes/webapp.json` は `artifact.webapp-core` を選択し、同じ shared foundation 上に application-specific route、surface、UI state、Webapp evidence を追加します。

browser delivery topology は artifact identity と直交します。statically generated な documentation / publishing product は runtime capability なしで `website` を利用できます。CDN-hosted stateful SPA は runtime capability なしで `webapp` を利用できます。`capability.pwa` は Website / Webapp のどちらからも選択でき、artifact identity を変更しません。runtime、interface、release capability も同様に独立した明示的 choice です。

すべての artifact は `lifecycle.composition-state` を必要とします。これにより、自己完結した consumer validator と lock schema が `.template-composition/` 以下に materialize されます。

詳細な設計については、[Composition model](docs/architecture/composition-model.md)、[production catalog architecture](docs/architecture/catalog.md)、および [generated contract manifest architecture](docs/architecture/generated-contract-manifest.md) を参照してください。

## Material ownership と safety model

materialize される各ファイルには、1つの component owner と1つの ownership mode があります。

- Managed material (`managed`) は引き続き Composition-owned であり、guard された managed-state reconciliation を通じてのみ変更できます。
- Generated material (`generated`) は resolved composition から deterministic に再計算され、引き続き Composition-owned です。
- Seed material (`seed`) は initial materialization 後に consumer ownership へ移るため、その後の consumer または Policy による編集は保持されます。

consumer-time validation では、`managed` および `generated` ファイルが lock digest と一致する必要があります。active な `seed` ファイルは存在し続ける必要がありますが、ownership transfer 後は元の bytes と異なっていても構いません。component owner または ownership mode の変更は推測されません。component-version の変更には明示的な upgrade が必要であり、component-version を変更せずに descriptor bytes が変化した場合は source invariant violation として拒否されます。

完全な operational contract については [Composer reference](docs/reference/composer.md) を、resolver、reconciliation、transaction、および recovery の詳細については [Composer architecture](docs/architecture/composer-mvp.md) を参照してください。

## Authority boundaries

coding-agent operating policy は独立した `policy` authority です。Composition は Policy profiles、`.agent-policy.yml`、`.agent-policy.lock`、または `.agent-policy/**` を解釈せず、Composer が `agent-policy` CLI を呼び出すこともありません。Policy-owned metadata paths は Composition にとって foreign reserved destinations です。

Skill artifact は `AGENTS.md` を `seed` として materialize します。initial composition の後は consumer-owned となり、その後 Policy が adopt または rewrite しても、Composition が Policy state の ownership を取得することはありません。cross-authority の canonical rules は Site が [Policy–Composition coexistence contract](https://templates.moukaeritai.work/coexistence/) として管理します。

Site は reader-facing information architecture、publication mapping、および generic schema-v3 publication protocol を別途担当します。Composition は provider declarations と provider-specific validation を所有し、Site は review 済みの正確な Composition revision を lock して公開します。provider contract については [publication boundary](docs/publication-catalog.md) を参照してください。

## Composition authority 保守者向けリファレンス

ここでいう **Composition authority 保守者** とは、`TakashiSasaki/templates` の `composition` authority 自体を変更・保守する人を指します。たとえば Composer、production catalog、schemas、architecture、provider publication contract などを変更する側です。consumer Agent Skill、Website、Web application repository の保守者を意味するものではありません。consumer repository を保守する場合は、まず [Using Composition](docs/consumer-guide.md) と対応する first-use walkthrough を参照してください。

主要な詳細リファレンスは次のとおりです。

- [Composition documentation index](docs/index.md)
- [Composition model](docs/architecture/composition-model.md)
- [Production catalog architecture](docs/architecture/catalog.md)
- [Generated contract manifest](docs/architecture/generated-contract-manifest.md)
- [Composer architecture](docs/architecture/composer-mvp.md)
- [Production catalog guide](catalog/README.md)
- [Composition schema guide](schemas/README.md)

過去の migration provenance は、現在の operation および architecture documentation から意図的に分離されています。reader-facing summary は [Composition authority migration history](docs/migrations/composition-authority-migration.md) です。stage-specific implementation notes は portal pages ではなく、Composition authority の保守記録として保持されます。
