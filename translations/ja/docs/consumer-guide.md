# Composition の利用方法

> **参考訳（非正本）:** この文書は英語版 `docs/consumer-guide.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

このガイドは、Composition を使用して具体的な Agent Skill または Web アプリケーション repository を作成・保守する consumer 向けです。通常の consumer は、インストール済みの Composition skill runner を使用します。その runner の下では Composer が引き続き semantic authority です。

このガイドでは、具体的な Skill または Web アプリケーション repository の保守者を consumer と呼びます。**Composition authority 保守者** とは、`TakashiSasaki/templates` の `composition` authority 自体を変更・保守する人だけを指します。

Composer の正確な options、plan fields、ownership definitions、および diagnostic codes については、[Composer reference](reference/composer.md) を参照してください。

## 操作を選ぶ

実行したいことから操作を選びます。

| 目的 | 操作 |
| --- | --- |
| まだ Composition によって managed されていない repository を作成する | `initial` |
| 記録済み intent を変更せずに、既存の managed repository をより新しい descendant Composition revision へ移行する | `update` |
| recipe、component selection、parameters を明示的に変更する、または component-version compatibility boundary を越える | `upgrade` |
| 中断された `update` または `upgrade` を再開する | 対応する `apply --mode ...` 操作を再実行する |

`inspect` と `validate` は mode-neutral です。mutating operation を選ぶ前に `inspect` を使い、apply が成功した後に `validate` を使います。

## Composition skill をインストールして実行する

対応している runner prerequisite は次のとおりです。

- `PATH` 上で Git が利用できること。
- CPython 3.11、3.12、3.13、または 3.14。

通常の consumer は、immutable かつ stdlib-only の bootstrap script を通じて公開済み Composition skill をインストールします。installer URL は branch や tag ではなく、review 済み installer commit に固定されています。

```sh
python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/TakashiSasaki/templates/2689bec83de815985a87cd287beba9ae414292b3/scripts/install_composition_skill.py', timeout=30).read())" /path/to/agent-skills/composition
```

その destination にこの Composition skill がすでに存在する場合は、`--replace` を追加します。既存 directory が `SKILL.md` によって `composition` skill と識別されない場合、replacement は拒否されます。

公開済み installer identity、installed skill source identity、および stable Composition toolchain identity は、それぞれ独立した immutable full SHA です。`2689bec83de815985a87cd287beba9ae414292b3` の installer は skill source `da2e169e1a650a2150936ca92d49596286e34a30` をインストールし、その skill の runtime manifest は stable Composition toolchain revision `1e982fb4c02e54c683a6d9215a9ca65e72fc0ffc` を選択します。これらの identity は `release/composition-installer.json` に記録され、Composition CI が repository history から検証します。installer URL の full SHA を mutable な `composition` branch や tag に置き換えないでください。

通常の command shape は次のとおりです。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  COMMAND [COMPOSER OPTIONS]
```

例:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  inspect
```

runner が Composer target を所有します。`--target` を重ねて渡さず、runner の `--repository` を使用してください。

### Review 済み checkout からインストールする

Composition authority 保守者は、正確な review 済み Composition checkout から skill をインストールすることもできます。

```sh
python skills/composition/scripts/install.py /path/to/agent-skills/composition
```

これは高度な source-maintenance path であり、通常の consumer installation route ではありません。checkout 自体も mutable branch identity ではなく、正確な review 済み revision でなければなりません。`--replace` は、既存 installation が Composition skill と識別済みの場合にだけ使用してください。

### Immutable source、runtime selection、cache reuse

インストール済み skill は mutable な `composition` branch や tag を実行しません。

`runtime-manifest.json` は、通常使用する full-SHA Composition source revision と、その revision の `requirements-runtime.lock` の SHA-256 を記録します。runner は invocation ごとに次を行います。

1. immutable な full SHA を選択する。
2. その exact revision に対する validation 済み cached checkout があれば再利用し、なければ ancestor history とともに `TakashiSasaki/templates` からその exact revision を取得する。
3. checkout が選択 SHA に detached されたままであり、canonical remote を指し、byte-clean で、LF-preserving checkout settings を使用し、history が traversable であることを検証する。
4. stable manifest revision が選択されている場合、stable runtime-lock digest を検証する。
5. repository、revision、lock SHA-256、CPython major/minor version、および platform/machine から runtime-cache identity を導出する。
6. marker、cached lock digest、Python/platform identity、`pip check`、および source revision の runtime verifier を検証した後にだけ runtime を再利用する。そうでなければ、dependency resolution を無効にして exact lock から新しい isolated runtime を構築し、atomic にインストールする。
7. その revision の `scripts/compose.py` を呼び出す。

高度な用途では `--revision <full-sha>` によって別の exact Composition revision を選択できます。mutable name は拒否されます。

`.template-composition/transaction.json` が存在する場合、managed recovery はより厳密です。transaction の exact source revision が stable manifest pin より優先されます。競合する `--revision` は recovery context を暗黙に変更せず拒否されます。malformed transaction metadata も fail closed します。

有効な source/runtime cache hit では network acquisition は不要です。既定では、runner は platform cache location の `composition/runner-v1` namespace を使用します。controlled environment または test では `COMPOSITION_RUNTIME_CACHE=/path/to/cache` で root を上書きできます。invalid cache entry は miss として扱われ、marker metadata だけを根拠に trust されることはありません。

cache layout と reuse は performance detail です。revision selection、recovery、Composer arguments、lock/transaction semantics、material ownership は変更しません。

### Source checkout から直接実行する

Composition authority 保守者は、正確かつ clean な Composition checkout から `scripts/compose.py` を直接実行することもできます。この path は runner と独立して確立された `requirements-runtime.lock` の consumer runtime contract を使用します。通常の consumer は immutable source selection と runtime setup を runner に任せるため、インストール済み skill を使用してください。

managed `update` および `upgrade` では、consumer lock に記録された old revision が、選択 source revision の Git ancestry から利用できなければなりません。runner の exact-SHA source cache は、この検査のために traversable ancestor history を保持し、検証します。

## Consumer configuration

initial composition と新しい upgrade には consumer configuration file が必要です。最小の Skill configuration は次のとおりです。

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

Web アプリケーションでは `"recipe": "webapp"` を使用します。選択した recipe が公開している場合にだけ、optional な `capability.*` または `lifecycle.*` component ID を `components.include` で追加してください。`recipes/` 以下の recipe file が selectable components の source of truth です。

現在の production revision では、components は parameter-specific materialization behavior を定義していません。選択 component が対応 parameter contract を明示的に文書化していない限り、`parameters` は空のままにしてください。parameter values も normalized consumer intent の一部なので、それを変更することは明示的な `upgrade` boundary です。

## 新しい managed repository を作成する

最初に target を inspect します。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  inspect
```

新しい target では `absent` または `unmanaged` が期待されます。`inspect` が managed state を報告した場合、validation が失敗したという理由だけで initial composition に戻らないでください。`managed-valid` では `update` または `upgrade` を使い、`managed-interrupted` は先に recovery し、`managed-invalid` は適切な managed operation を再試行する前に診断・修復します。initial composition は既存の Composition lock がある場合に拒否されます。

apply の前に plan します。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  plan --config composition.json
```

initial planning は read-only です。apply の前に、すべての action と conflict を確認してください。`create` は Composition が新しい destination を作成することを意味します。`adopt-identical` は destination がすでに desired bytes と完全一致しており、上書きせずに adopt できることを意味します。conflict が1つでもあれば apply は進みません。

同じ configuration を apply します。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  apply --config composition.json
```

続いて validate します。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  validate
```

initial apply が成功すると `.template-composition/lock.json` が最後に書き込まれます。lock は runner が使用した exact Composition source revision を記録します。

## Composition repository で Policy を使う

coding-agent Policy は optional であり、Composition とは独立して adopt します。Composition は `.agent-policy.yml`、`.agent-policy.lock`、または `.agent-policy/**` を作成せず、Policy adoption を `capability.*` として公開せず、`agent-policy` CLI を呼び出しません。

両 authority を使用する repository では、通常の順序は次のとおりです。

```text
Composition initial
  -> seed materialization
  -> consumer ownership
  -> optional explicit Policy adoption
  -> independent Policy + Composition managed state
```

この順序が特に重要なのは Skill recipe です。`artifact.skill-core` は `AGENTS.md` を `seed` として materialize するため、initial composition の後、その内容は consumer-owned になります。その後の明示的な Policy adoption は、その instruction bytes を migrate または replace できます。以後の Composition `update` / `upgrade` は、Composition の元の `AGENTS.md` bytes に戻すのではなく、active seed を保持します。

Policy-owned metadata は Composition ownership の外側です。既存の `.agent-policy.yml`、`.agent-policy.lock`、および `.agent-policy/**` は、通常の Composition material と衝突しない限り変更されません。Composition schemas と consumer validation も、これらの path を claim しようとする component、lock inventory、または transaction を拒否します。

逆方向の ownership transition は推測されません。Policy-managed repository に異なる `AGENTS.md` がすでに存在する状態で Skill initial composition を試みると、planning は通常の destination conflict を報告し、apply は file を上書きせず Composition lock も作成しません。

完全な cross-authority rules については、Site-owned の [Policy–Composition coexistence contract](https://templates.moukaeritai.work/coexistence/) を参照してください。

## Repository が managed か確認する

次を使用します。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  inspect
```

通常の state は次のとおりです。

- `absent` — target path が存在しない。
- `unmanaged` — Composition lock が存在しない。
- `managed-valid` — lock と現在の materialized state が validation を通る。
- `managed-invalid` — Composition metadata は存在するが、managed state が validation を通らない。
- `managed-interrupted` — managed transaction marker が存在し、recovery が必要。

symbolic link など invalid な target root には `invalid` state が使用されます。repository に template output のように見える files があるかどうかだけで managed state を判断しないでください。`.template-composition/lock.json` と `inspect` が authoritative indicators です。

## Intent を変更せずに update する

同じ normalized intent、つまり同じ recipe、明示的な include/exclude choices、および parameters を維持したまま、runner が選択した descendant Composition revision へ進める場合は `update` を使用します。

inspect と plan を行います。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  inspect
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  plan --mode update
```

`update` は意図的に `--config` を受け付けません。lock schema v2 は normalized consumer intent を保存しているため、通常の update で replacement configuration を受け付けると、intent change と routine source advancement を区別できなくなります。intent を変更する場合は `upgrade` を使用してください。

managed file plan を確認します。主な class は次のとおりです。

- `create` — 新たに選択された destination を安全に作成できる。
- `replace` — clean な既存 `managed` または `generated` destination に新しい bytes を書き込む。
- `remove` — clean な既存 `managed` または `generated` destination が選択対象から外れたため削除する。
- `preserve` — `seed` file は consumer-owned のままで、上書きも削除もしない。
- `unchanged` — desired bytes がすでに locked bytes と同じ。
- `conflict` — conflict が解決されるまで apply は repository を mutate してはならない。

plan に問題がなければ次を実行します。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  apply --mode update
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  validate
```

component-version の変更は通常の update ではありません。update plan は `COMPONENT_VERSION_UPGRADE_REQUIRED` を報告します。その boundary は `upgrade` で明示的に越えてください。

## Upgrade または intent の変更

recipe、明示的な component include/exclude choices、parameters、または upgrade boundary として報告された component versions など、選択された compatibility surface を意図的に変更する場合は `upgrade` を使用します。

desired new configuration を明示的に plan します。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  plan --mode upgrade --config composition.json
```

続いて、同じ target intent を apply して validate します。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  apply --mode upgrade --config composition.json
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  validate
```

`upgrade` は explicit ですが、一般的な merge engine や ownership-migration engine ではありません。component owner が変わる destination や、`managed`、`generated`、`seed` の間で ownership mode が変わる destination は引き続き拒否されます。これらの transition には Composer が推測するのではなく、明示的な source-side migration design が必要です。

## 中断された update または upgrade を recovery する

`inspect` が `managed-interrupted` を返した場合、`.template-composition/transaction.json` を手作業で削除・編集しないでください。

インストール済み runner は source acquisition の前に transaction を読みます。transaction に記録された exact source revision を自動的に選択し、競合する explicit revision を拒否します。

対応する operation を再実行します。

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

中断された upgrade の recovery では `--config` を渡してはいけません。target intent と new lock はすでに transaction に bind されています。

recovery が成功した後:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  validate
```

recovery は deterministic roll-forward です。file が記録済み old state と、すでに apply 済みの new state のどちらにも一致しなくなっている場合、Composer は unexpected bytes を上書きせず停止します。

## どの file を編集してよいか

materialized file の ownership を判断するには `.template-composition/lock.json` の `ownership` field を使用します。

| Ownership | Consumer の編集規則 |
| --- | --- |
| `managed` | update/upgrade にその file を管理させるなら local edit しないでください。Composition が引き続き authoritative です。 |
| `generated` | local edit しないでください。bytes は Composition authorities から deterministic に再生成されます。 |
| `seed` | 最初の materialization 後は通常の repository content として編集できます。Composition は後続の consumer edits を上書きしません。 |

active lock に記載されていない files は、別の repository-local contract が定めない限り通常の repository content です。Policy-owned metadata は明示的な例であり、`.agent-policy.yml`、`.agent-policy.lock`、および `.agent-policy/**` は Composition lock の外側にあり、Composer operation の repair target ではありません。

conflict を回避するために `.template-composition/lock.json` や `.template-composition/transaction.json` など Composer-owned metadata を手作業で編集しないでください。

## Planning が conflict を報告した場合

planning は意図的に fail-closed かつ read-only です。原因を修正し、`apply` の前に `plan` を再実行してください。

一般的な case は次のとおりです。

- `LOCAL_MODIFICATION` — `managed` または `generated` file が old lock と一致しなくなっています。Composition に管理を継続させるなら locked bytes を復元してください。local change を維持する必要がある場合は停止し、ownership/source authority を再設計してください。
- `COMPONENT_VERSION_UPGRADE_REQUIRED` — desired intent を表す explicit configuration とともに `upgrade` を使用してください。
- `FILE_OWNER_TRANSITION_UPGRADE_REQUIRED` / `OWNERSHIP_TRANSITION_UPGRADE_REQUIRED` — 現在の upgrade はその migration を推測しません。明示的な source-side migration design が必要です。
- `SOURCE_REVISION_NOT_DESCENDANT` — locked source revision またはその descendant である Composition revision を使用してください。
- `OLD_SOURCE_REVISION_UNAVAILABLE` — 選択した exact revision は old locked revision を ancestor history に含める必要があります。
- `DESTINATION_CONFLICT` — conflicting ordinary repository path を削除または意図的に reconcile してください。Composer による overwrite を前提にしないでください。
- `RECOVERY_REQUIRED` — 新しい plan を開始せず、既存 transaction を完了してください。

正確な diagnostic meaning については [Composer reference](reference/composer.md) を参照してください。

## なぜ apply の前に plan するのか

`plan` は選択された exact Composition source を解決し、target repository と比較して、提案される mutation と conflict を target に書き込まずにすべて提示します。managed `apply` 自体も transaction marker を書く前に deterministic planning を実行しますが、先に explicit plan を review することが consumer safety checkpoint です。

## より深い設計情報

通常の consumer operation では architecture documents を読む必要はありません。設計理由を確認する場合、または Composition authority 自体を保守する場合に参照してください。

- [Composition model](architecture/composition-model.md) — authority、intent、lock、component、および ownership model。
- [Composer MVP](architecture/composer-mvp.md) — deterministic resolver、reconciliation、transaction、digest precondition、および crash-recovery contract。
- [Composition state](../components/lifecycle.composition-state/files/docs/architecture/composition-state.md) — 自己完結した consumer validation contract。
