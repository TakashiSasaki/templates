# Composition スキーマ

> **参考訳（非正本）:** この文書は英語版 `schemas/README.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

JSON Schema Draft 2020-12 contract は、composition source、resolved state、immutable installer publication の model を定義します。

- `component.schema.json` — foundation / artifact / capability / lifecycle descriptor、material、dependency / conflict、任意の `contract_registrations`、および範囲を限定した generated-material handler ID。
- `recipe.schema.json` — consumer-facing artifact recipe。recipe は1つの artifact を選び、capability / lifecycle choice を公開できます。foundation component は consumer が直接選択するのではなく推移的に解決されます。
- `composition-config.schema.json` — 未解決の consumer intent。
- `composition-playground-projection.schema.json` — Composition 所有の Playground v1 projection。recipe のケース表、正規 outcome、provenance の reason bit と依存関係、contract、material、空の target に対する initial plan の要約を含みます。
- `composition-lock.schema.json` — normalized consumer intent を含む、immutable source に束縛された resolved managed state。
- `composition-transaction.schema.json` — deterministic な interrupted update / upgrade recovery metadata と mutation precondition。
- `catalog.schema.json` — 閉じた production component / recipe inventory。
- `composition-skill-installer-release.schema.json` — immutable remote-installer revision、installed skill-source revision、Composition toolchain revision を分離して表す stable release metadata。

Playground projection は、正規の Composition resolution / planning API だけから生成します。`generated/composition-playground-v1.json.gz` はその JSON の決定的 gzip transport であり、`playground/composition-playground-v1.json.gz` で公開します。

Provenance の identity は3種類に分かれます。`projection_id` と `schema_version` は契約と payload family を識別します。gzip 内の `source.revision` はケース、provenance、contract、material、ownership、空 target の plan を生成した正確な semantic source revision です。publication/provider revision は Site が選択して `/build-provenance.json` に記録する供給元の commit であり、semantic source の publication-only descendant でも構いません。

両 SHA の一致は必須ではありません。Publication CI は `build_projection(source_revision=...)` による再生成時に ancestry と semantic path の同一性を検証します。ブラウザは Git ancestry を再実装したり、両 SHA の相違だけで正当な descendant を拒否したりしません。transport 自身の provider commit SHA を payload に埋め込まないため、最終 commit identity の自己参照は発生しません。

contract registration は、component-owned contract document / schema、stable migration slug、現在の document schema version、完全な version history、purpose を1件指定します。registration metadata は source-time の composition input であり、consumer に独立した authority としてコピーされるものではありません。`lifecycle.contract-evolution` は、解決済み registration set から consumer の `contracts/manifest.json` を deterministic に render します。

JSON Schema が検証するのは document shape です。repository test と `scripts/compose.py` は、それに加えて safe path、component role / ID の一致、foundation の direct-selection 制約、selection の disjointness、dependency closure、portable destination ownership、registration の uniqueness / ownership、deterministic generation、source tracking、resolved-owner reference、materialized validation、transaction action consistency などの cross-document semantics を強制します。installer-publication verification はさらに、参照された immutable Git history と `toolchain -> skill source -> installer -> publication` の ancestry chain を検査します。これらの性質は JSON Schema だけでは保証できません。

Destination schema は、Composer 内部 metadata の予約だけでなく provider ownership も強制します。Composition material、lock inventory、transaction action は `.agent-policy.yml`、`.agent-policy.lock`、`.agent-policy/**` を claim できません。これらは外部の Policy-owned path です。これは path ownership の制約に限られ、Composition が Policy schema、lock、profile、runtime state を parse することはありません。

Composer は initial の `inspect`、`plan`、`apply`、`validate` に加え、明示的な managed-state `update` / `upgrade` mode をサポートします。両 managed mode とも `plan` 時は read-only で、crash-recoverable な `apply` mutation には `.template-composition/transaction.json` を使います。transaction は old/new lock state と、順序付きの create / replace / remove action を正確に束縛します。recovery は各 action について記録済み old digest または既に適用済みの new state のみを受理し、その後 new managed state を validate してから transaction marker を削除します。

`update` は lock v2 から intent を再構成し、新しい `--config` を拒否します。component-version の変更には upgrade が必要です。`upgrade` は新しい transaction を開始する際に明示的な新 configuration を要求し、recipe / include / exclude / parameter / component version を変更できます。ただし file owner や ownership mode の migration は推測せず、component-version を変更せずに descriptor bytes が変化した場合も拒否します。

新しい seed material は、まだ consumer-owned file が存在しないため `create` action です。initial materialization が成功すると seed ownership は consumer に移ります。共通して残る seed bytes は保持され、その original provenance digest も引き継がれます。削除された seed file は通常の consumer-owned extra として残されます。
