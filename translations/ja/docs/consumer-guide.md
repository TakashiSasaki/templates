# Composition の利用方法

> **参考訳（非正本）:** この文書は英語版 `docs/consumer-guide.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

このガイドは、Composition を使用して具体的な Agent Skill または Web application repository を作成・保守する consumer 向けです。通常の consumer はインストール済み Composition skill runner を使用し、その下では Composer が引き続き semantic authority です。

ここで **Composition authority 保守者** とは、`TakashiSasaki/templates` の `composition` authority 自体を変更・保守する人を指します。consumer repository の保守者とは区別します。

Composer の正確な options、plan fields、ownership definitions、diagnostic codes については [Composer reference](reference/composer.md) を参照してください。

## 操作を選ぶ

| 目的 | 操作 |
| --- | --- |
| まだ Composition-managed でない repository を作成する | `initial` |
| 記録済み intent を変えず、より新しい descendant Composition revision へ進める | `update` |
| recipe、component selection、parameters を変更する、または component-version compatibility boundary を越える | `upgrade` |
| 中断された `update` / `upgrade` を再開する | 対応する `apply --mode ...` を再実行する |

`inspect` と `validate` は mode-neutral です。mutation の前に `inspect`、成功した apply の後に `validate` を使用します。

## Composition skill をインストールして実行する

通常の consumer に必要な local prerequisite は CPython 3.11、3.12、3.13、または 3.14 です。**通常の Composition consumption に Git は不要です。** `TakashiSasaki/templates`、`composition`、`site`、`policy` のいずれも clone せずに利用できます。インストール済み runner は選択された immutable full-SHA Composition revision を HTTPS で取得し、source bootstrap には Python standard library を使用します。

cold execution では、選択された full-SHA source archive を取得するための GitHub network access が必要です。また一致する Python runtime cache が存在しない場合は、設定された Python package source への access が必要です。managed `update` / `upgrade` ではさらに GitHub compare API による old-to-new revision ancestry 検証が必要です。これらの network dependency は fail closed であり、mutable branch への fallback や ancestry の推測は行いません。

sandbox、container、CI worker など、既定 user cache が writable でない環境では runner を最初に呼ぶ前に writable cache root を指定してください。

```sh
export COMPOSITION_RUNTIME_CACHE=/path/to/writable/composition-runtime-cache
export COMPOSITION_VALIDATION_CACHE=/path/to/writable/composition-validation-cache
```

cache は product repository の外側に置きます。`COMPOSITION_RUNTIME_CACHE` に残るのは validation 済み Python runtime state であり、通常の Composition source snapshot は disposable で、そこには保存されません。

通常の consumer は immutable かつ stdlib-only の bootstrap script から公開済み Composition skill をインストールします。installer URL は branch/tag ではなく review 済み installer commit に固定されています。

```sh
python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/TakashiSasaki/templates/08c7c9ac647000b7e7232ad5eda4f0b3506a7675/scripts/install_composition_skill.py', timeout=30).read())" /path/to/agent-skills/composition
```

既存 destination にこの Composition skill がある場合は `--replace` を追加できます。`SKILL.md` によって `composition` skill と識別できない directory の replacement は拒否されます。

公開済み immutable identity は役割ごとに分かれています。installer `08c7c9ac647000b7e7232ad5eda4f0b3506a7675` は skill source `e8ee87483ea97e6cce8f27e6438d98a5a7c724a7` をインストールし、その runtime manifest は stable toolchain `16d3eb411729a79549dbaaf6dab1d05207f83415` を選択します。これらは `release/composition-installer.json` に記録され、Composition CI が repository history から検証します。

通常の command shape は次のとおりです。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  COMMAND [COMPOSER OPTIONS]
```

runner が Composer target を所有します。Composer の `--target` を重ねて渡さず、runner の `--repository` を使用してください。

### Doctor

local bootstrap prerequisite や runtime-cache behavior を診断するには read-only `doctor` を使用します。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  doctor
```

machine-readable 出力には `doctor --format json` を使用します。doctor は selected immutable revision、対応 CPython、persistent runtime-cache の write/atomic-rename capability を検査します。通常 consumer の Git は `not-required`、source acquisition は `ephemeral` と報告します。doctor は GitHub や package index に接続せず、source/runtime state を acquire しません。したがって `READY` は local bootstrap diagnosis であり、Composition validation の代替でも、後続 cold acquisition の network availability 保証でもありません。

例えば repository の状態確認は次です。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  inspect
```

### Review 済み checkout からインストールする

Composition authority 保守者は、正確な review 済み Composition checkout から skill をインストールできます。

```sh
python skills/composition/scripts/install.py /path/to/agent-skills/composition
```

これは authority-maintenance 向けの高度な path で、通常 consumer installation route ではありません。この reviewed-checkout path では Git が expected prerequisite です。

### Immutable source snapshot と runtime reuse

インストール済み skill は mutable な `composition` branch/tag を実行せず、persistent templates checkout を作りません。

`runtime-manifest.json` は通常使用する full-SHA Composition source revision と、その revision の `requirements-runtime.lock` SHA-256 を記録します。各 Composer invocation で runner は次を行います。

1. immutable full SHA を選択する。
2. Python standard library で `https://codeload.github.com/TakashiSasaki/templates/tar.gz/<full-sha>` を取得する。
3. unsafe archive path、symbolic/hard link、duplicate/portable-colliding path、unsupported member type、archive limit 違反を拒否する。
4. revision を OS temporary directory に展開し、すべての regular file の SHA-256 inventory を作り、repository/revision/inventory metadata を Composer に渡す。
5. Composer authority file が acquired snapshot 内にあり inventory に含まれ、取得時 digest を維持していることを要求する。
6. stable revision では runtime-lock digest を検証する。
7. repository、revision、lock SHA-256、CPython major/minor、platform/machine から persistent runtime-cache identity を導出する。
8. marker、cached lock digest、Python/platform identity、`pip check`、source revision の runtime verifier がすべて通る runtime だけを再利用し、miss では exact lock から isolated runtime を構築して atomic install する。
9. その revision の `scripts/compose.py` を実行し、normal completion または handled failure 後に temporary source snapshot/context を削除する。

`--revision <full-sha>` で別の exact revision を選ぶこともできますが、現在の immutable snapshot execution contract をサポートする revision である必要があります。mutable name は拒否されます。

`.template-composition/transaction.json` が存在する managed recovery では transaction の exact source revision が stable pin より優先されます。競合する `--revision` は拒否され、malformed transaction metadata も fail closed します。

persistent source-cache hit は意図的に存在しません。通常の `inspect`、`plan`、`apply`、runner `validate` は invocation ごとに selected immutable source archive を再取得します。一方 `COMPOSITION_RUNTIME_CACHE` は、同一 validation 済み Python environment の再構築を避けるため persistent です。したがって warm runtime があっても normal Composer execution は完全 offline にはならず、GitHub source archive availability は必要です。`doctor` と `provenance` は network-free です。

materialized validation は自己完結しています。cold validation では exact review 済み validation requirement set 用の isolated validation runtime を platform cache に構築する場合があります。有効な warm validation cache は package acquisition なしで再利用されます。既定 namespace は `composition/validation-v1` で、必要なら `COMPOSITION_VALIDATION_CACHE` で writable root を選べます。

cache layout/reuse は performance detail であり、revision selection、recovery、Composer arguments、lock/transaction semantics、source identity、material ownership を変更しません。

### Consumer Git checkout なしの managed revision ancestry

managed `update` / `upgrade` は、新しい selected source revision が old lock revision と同一、またはその descendant であることを証明しなければなりません。snapshot-backed normal-consumer execution は2つの immutable full SHA を GitHub compare API に渡して検証します。`ahead` / `identical` は許可し、`behind` / `diverged` は拒否します。unknown commit、HTTP/network failure、rate limit、malformed response、unsupported status は fail closed です。

この network check が検証するのは revision ancestry であり、branch name を authority に変えるものではありません。lock と runner は full commit SHA のみを使用します。

### Source checkout から直接実行する

Composition authority 保守者は exact clean checkout から `scripts/compose.py` を直接実行できます。その Git-backed source context は reviewed checkout revision、tracked authority file、dirty state、managed ancestry を local Git history から検証します。通常 consumer は templates clone を必要としない installed skill path を使用してください。

## Consumer configuration

initial composition と新しい upgrade には consumer configuration file が必要です。最小の Skill configuration は次です。

```json
{
  "schema_version": 1,
  "recipe": "skill",
  "components": {
    "include": [],
    "exclude": []
  },
  "parameters": {}
}
```

Web application では `"recipe": "webapp"` を使用します。optional `capability.*` / `lifecycle.*` は選択 recipe が公開するものだけを `components.include` に追加します。`recipes/` 以下が selectable component の source of truth です。

Web application の capability は process/listener topology ではなく、caller-visible contract に基づいて選択します。

| Product requirement | Composition selection |
| --- | --- |
| Browser application の surfaces、routes、visible states、responsive behavior | `webapp` baseline (`artifact.webapp-core`) |
| 独立して保守される browser-facing operational/diagnostic/demonstration interface | `capability.web-interface` |
| browser implementation detail にすぎない BFF/JSON endpoint | その理由だけでは `capability.service` を追加しない |
| browser と独立して caller が利用する HTTP/JSON 等の API | `capability.service` |
| browser interface と独立 API が同じ process/listener/proxy を共有 | 両方を選ぶ。shared topology は contract を統合しない |
| 保守対象 CLI | `capability.cli` |

現在の production revision では parameter-specific materialization behavior は定義されていません。component が明示的に対応 parameter contract を文書化していない限り `parameters` は空にします。parameter の変更も explicit `upgrade` boundary です。

## 新しい managed repository を作る

最初に target を inspect します。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  inspect
```

新規 target では `absent` または `unmanaged` が正常です。`managed-valid` は update/upgrade、`managed-interrupted` は recovery、`managed-invalid` は診断・修復が必要です。既存 Composition lock がある repository に initial composition は行いません。

apply の前に plan します。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  plan --config composition.json
```

relative `--config` は `--repository` ではなく invocation process の current working directory から解決されます。必要なら absolute path を使用します。

initial planning は read-only です。`create`、意図した `adopt-identical`、および conflicts を確認します。conflict があれば apply しません。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  apply --config composition.json
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  validate
```

成功した initial apply は `.template-composition/lock.json` を最後に書き、使用した exact Composition source revision を記録します。

### Initial apply 後: scaffold を product にする

initial validation が証明するのは resolved Composition state と selected template contract の internal validity です。Webapp の `template` mode は application implementation、product test、deployment、release readiness の証明ではありません。

1. lock の ownership boundary を読み、`seed` と ordinary consumer file を編集し、`managed` / `generated` / lock / transaction material は手作業で編集しない。
2. seed assumption を実際の product contract に置き換える。
3. product を consumer-owned source file に実装する。
4. Webapp では `python scripts/scaffold_webapp_evidence.py` で現在の evidence-target worklist を確認する。
5. product coding 前に `contracts/implementation-evidence.json` を `template` から `planning` にし、stable requirement ID を記録する。real proof が整ったら records/commands/gates を接続して `product` に進める。
6. product 自身の verification と Composition `validate` の両方を行う。
7. coding-agent Policy も使用する場合は seed ownership transfer 後に明示的に adopt する。

## Composition repository で Policy を使う

Policy adoption は Composition とは独立しています。Composition は `.agent-policy.yml`、`.agent-policy.lock`、`.agent-policy/**` を作成せず、Policy adoption を capability として扱わず、`agent-policy` CLI を呼びません。

```text
Composition initial
  -> seed materialization
  -> consumer ownership
  -> optional explicit Policy adoption
  -> independent Policy + Composition managed state
```

`artifact.skill-core` の `AGENTS.md` は `seed` なので initial composition 後は consumer-owned です。後続 Policy adoption がその bytes を migrate/replace しても、Composition update/upgrade は active seed を保持します。

Policy-owned metadata は Composition lock の外側です。逆方向の ownership transition も推測されません。異なる `AGENTS.md` が既に存在すれば normal destination conflict として扱われます。

完全な cross-authority rule は Site-owned [Policy–Composition coexistence contract](https://templates.moukaeritai.work/coexistence/) を参照してください。

## Repository が managed か確認する

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  inspect
```

通常 state は `absent`、`unmanaged`、`managed-valid`、`managed-invalid`、`managed-interrupted` です。symbolic link など invalid target root は `invalid` になります。managed state の authority は `.template-composition/lock.json` と `inspect` です。

## Intent を変更せずに update する

同じ normalized intent を runner の selected descendant Composition revision へ進める場合は `update` を使います。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  inspect
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  plan --mode update
```

`update` は `--config` を受け付けません。intent を変更する場合は `upgrade` を使います。

managed file plan の主な class は `create`、`replace`、`remove`、`preserve`、`unchanged`、`conflict` です。`seed` は preserve され、consumer-owned のままです。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  apply --mode update
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  validate
```

component-version change は ordinary update ではなく `COMPONENT_VERSION_UPGRADE_REQUIRED` となるため、explicit `upgrade` を使います。

## Upgrade または intent の変更

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  plan --mode upgrade --config composition.json
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  apply --mode upgrade --config composition.json
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  validate
```

`upgrade` は explicit ですが general merge/ownership-migration engine ではありません。component owner や `managed` / `generated` / `seed` ownership mode の transition は source-side migration design が必要です。

## 中断された update / upgrade を recovery する

`managed-interrupted` では `.template-composition/transaction.json` を手作業で削除・編集しません。runner は source acquisition 前に transaction を読み、記録された exact source revision を自動選択して conflicting explicit revision を拒否します。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  apply --mode update
```

または:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  apply --mode upgrade
```

中断 upgrade recovery には `--config` を渡しません。成功後に `validate` します。recovery は deterministic roll-forward で、unexpected bytes は上書きしません。

## どの file を編集してよいか

| Ownership | Consumer rule |
| --- | --- |
| `managed` | Composition に管理を継続させるなら local edit しない |
| `generated` | local edit しない。deterministic に再生成される |
| `seed` | initial materialization 後は通常 content として編集可能 |

active lock にない file は、別 authority が定めない限り ordinary repository content です。Composer-owned lock/transaction metadata を conflict 回避のために手編集してはいけません。

## Planning が conflict を報告した場合

planning は fail-closed / read-only です。原因を直して `plan` を再実行します。

- `LOCAL_MODIFICATION` — locked `managed` / `generated` bytes と違う。Composition が管理を続けるなら復元する。
- `COMPONENT_VERSION_UPGRADE_REQUIRED` — explicit configuration と `upgrade` を使う。
- `FILE_OWNER_TRANSITION_UPGRADE_REQUIRED` / `OWNERSHIP_TRANSITION_UPGRADE_REQUIRED` — source-side migration design が必要。
- `SOURCE_REVISION_NOT_DESCENDANT` — old locked revision と同一または descendant の revision を使う。
- `OLD_SOURCE_REVISION_UNAVAILABLE` — GitHub が canonical repository history から old locked full SHA を解決できない。source identity/revision を確認し、canonical history が利用可能な状態で再試行する。
- `SOURCE_TRANSITION_UNAVAILABLE` — GitHub compare response が unavailable、rate-limited、malformed 等で ancestry を確立できない。check を bypass せず再試行する。
- `DESTINATION_CONFLICT` — ordinary repository path を意図的に reconcile する。
- `RECOVERY_REQUIRED` — 新しい plan より先に既存 transaction を完了する。

正確な diagnostic meaning は [Composer reference](reference/composer.md) を参照してください。

## なぜ apply の前に plan するのか

`plan` は selected exact Composition source と target repository を比較し、提案 mutation/conflict を書き込みなしで提示します。managed `apply` 自体も transaction marker を書く前に deterministic planning を行いますが、explicit plan の review が consumer safety checkpoint です。

## より深い設計情報

通常 consumer operation では architecture documents を読む必要はありません。設計理由や authority maintenance が必要な場合に参照します。

- [Composition model](architecture/composition-model.md) — authority、intent、lock、component、ownership model。
- [Composer MVP](architecture/composer-mvp.md) — resolver、reconciliation、transaction、digest precondition、crash recovery。
- [Composition state](../components/lifecycle.composition-state/files/docs/architecture/composition-state.md) — self-contained consumer validation contract。
