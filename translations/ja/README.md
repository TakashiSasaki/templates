# Composition

> **参考訳（非正本）:** この文書は英語版 `README.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

Composition は `TakashiSasaki/templates` における canonical authority であり、再利用可能な Skill および Web アプリケーションの artifact semantics、application capabilities、lifecycle contracts、recipes、schemas、および deterministic Composer を管理します。

consumer repository は、artifact recipe と明示的な consumer intent から生成されます。Composer は deterministic な component closure を解決し、source files と generated files を materialize し、解決済み状態を `.template-composition/lock.json` に記録して、consumer repository を自己完結した状態にします。

## ここから始める

**初めて Web application を作る場合**は、[Webapp product walkthrough](docs/guides/webapp-product-walkthrough.md) から始めてください。これは canonical な zero-to-one path です。別 product repository を作り、prerequisites を確認し、Composition を install し、`composition.json` を作成し、`inspect -> plan -> apply -> validate` を進め、editing boundary を理解した後、product implementation と evidence まで続きます。開始前に Composition architecture を理解する必要はありません。

Agent Skill の作成、既存 managed repository の保守、Composition update/upgrade、recovery、ownership、conflict handling など、その他の consumer work には [Using Composition](docs/consumer-guide.md) を使用します。

通常の consumer は installable な `skills/composition/` runner を使用します。Git と CPython 3.11 から 3.14 が対応 prerequisite です。runner は immutable な full-SHA Composition source revision を選択し、dependency resolution を無効にして正確な `requirements-runtime.lock` environment を構築し、consumer repository を target として既存の Composer を呼び出します。Composition authority 自体を保守する担当者は direct source-checkout entrypoint も引き続き利用でき、clean consumer-runtime matrix では Ubuntu 24.04 と Windows Server 2022 を検証しています。

正確な CLI options、inspect states、plan fields、ownership semantics、recovery rules、diagnostic codes、および exit behavior については、[Composer reference](docs/reference/composer.md) を参照してください。

architecture、provider-specific documentation、および machine-readable authority guides については、[Composition documentation index](docs/index.md) を参照してください。

## Lifecycle の概要

公開されている Composer workflow は次のとおりです。

```text
inspect -> plan -> apply -> validate
```

`initial` は、明示的な consumer configuration から新しい managed repository を作成します。`update` は、lock に記録済みの normalized intent を維持したまま、descendant である Composition source revision へ repository を reconcile します。`upgrade` は明示的な新しい consumer intent を受け取り、component-version の変更など compatibility boundary を越える変更で必須です。managed mutation が中断された場合は、任意の local state を推測または merge するのではなく、durable transaction marker から deterministic に roll-forward して recovery します。

Composition は意図的に fail-closed です。planning は read-only であり、mutation の前には完全な plan が作成されます。Composition-owned bytes に対する local changes は暗黙に上書きされず、未対応の ownership transition や component transition は推測せず拒否されます。

## Artifacts、capabilities、lifecycle

production catalog は、再利用可能な authority を次の3種類に分離します。

- `artifact.*` は `artifact.skill-core` や `artifact.webapp-core` など artifact-specific semantics を定義します。
- `capability.*` は runtime、CLI、MCP、MCP Apps、browser、headless service など、再利用可能な runtime/interface/service behavior を定義します。
- `lifecycle.*` は composition-state、contract-evolution、implementation-evidence、release-evidence、および release-bundle behavior を定義します。

`recipes/skill.json` は `artifact.skill-core` を選択し、application capability と product lifecycle component は opt-in です。`recipes/webapp.json` は `artifact.webapp-core` を選択し、contract evolution と implementation evidence を baseline とします。release lifecycle は `lifecycle.release-bundle` による明示的な opt-in であり、runtime と interface capability も独立して optional です。したがって static / CDN Web application は、browser-facing であるという理由だけで application runtime や release lifecycle を持つ必要はありません。

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

ここでいう **Composition authority 保守者** とは、`TakashiSasaki/templates` の `composition` authority 自体を変更・保守する人を指します。たとえば Composer、production catalog、schemas、architecture、provider publication contract などを変更する側です。consumer Skill または Web application repository の保守者を意味するものではありません。consumer repository を保守する場合は、まず [Using Composition](docs/consumer-guide.md) と [Composer reference](docs/reference/composer.md) を参照してください。

主要な詳細リファレンスは次のとおりです。

- [Composition documentation index](docs/index.md)
- [Composition model](docs/architecture/composition-model.md)
- [Production catalog architecture](docs/architecture/catalog.md)
- [Generated contract manifest](docs/architecture/generated-contract-manifest.md)
- [Composer architecture](docs/architecture/composer-mvp.md)
- [Production catalog guide](catalog/README.md)
- [Composition schema guide](schemas/README.md)

過去の migration provenance は、現在の operation および architecture documentation から意図的に分離されています。reader-facing summary は [Composition authority migration history](docs/migrations/composition-authority-migration.md) です。stage-specific implementation notes は portal pages ではなく、Composition authority の保守記録として保持されます。
