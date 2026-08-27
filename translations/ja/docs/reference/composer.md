# Composer リファレンス

> **参考訳（非正本）:** この文書は英語版 `docs/reference/composer.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

このリファレンスでは、`scripts/compose.py` の consumer-facing contract を説明します。タスク指向の手順については [Composition の利用方法](../consumer-guide.md) から始めてください。設計上の根拠については [Composer MVP](../architecture/composer-mvp.md) と [Composition model](../architecture/composition-model.md) を参照してください。

通常の consumer は、install 済みの `skills/composition/` runner を通じてこの contract を利用します。runner は immutable source の取得、isolated runtime の構築、target の注入を担当しますが、lifecycle mode、plan、lock/transaction semantics、ownership、diagnostics、Composer の exit behavior を再定義するものではありません。以下の direct source-checkout の例では `--target /repo` を明示します。runner 経由では同等の target を `--repository /repo` として1回だけ指定し、2つ目の `--target` は拒否されます。

## Public lifecycle

公開 lifecycle は次のとおりです。

```text
inspect -> plan -> apply -> validate
```

`inspect` と `validate` は mode-neutral です。`plan` と `apply` は `initial`、`update`、`upgrade` の3つの mode のいずれかを使用します。

## Command と option の対応表

| Command | Mode | `--target` | `--config` | `--format` | Purpose |
| --- | --- | --- | --- | --- | --- |
| `inspect` | none | required | not accepted | `json` (default) / `human` | mutation せず target state を分類する |
| `plan` | `initial` or omitted | required | required | `json` (default) / `human` | 最初の materialization を計画する |
| `apply` | `initial` or omitted | required | required | `json` (default) / `human` | 最初の materialization を実行する |
| `plan` | `update` | required | forbidden | `json` (default) / `human` | lock-v2 intent を保持して current descendant source へ reconcile する計画を作る |
| `apply` | `update` | required | forbidden | `json` (default) / `human` | managed update を適用または recovery する |
| `plan` | `upgrade` | required | required | `json` (default) / `human` | 明示的な intent / compatibility-boundary change を計画する |
| `apply` | `upgrade` | required | required for a new upgrade; forbidden during recovery | `json` (default) / `human` | 明示的な upgrade を開始または recovery する |
| `validate` | none | required | not accepted | `json` (default) / `human` | current consumer state を検証する |

Initial mode が default です。次の2つは同等です。

```sh
python scripts/compose.py plan --config composition.json --target /repo
python scripts/compose.py plan --mode initial --config composition.json --target /repo
```

dispatcher は command の前後どちらに `--mode` と `--format` があっても受け付けますが、例とドキュメントでは command-first form を使用します。

## Output format

`--format json` が public output contract の default です。`--format` を省略した場合は、明示的な `--format json` と同等です。machine-readable JSON の field shape、structured diagnostic code、lifecycle の exit behavior は同じです。

`--format human` は、人間が terminal で Composer を直接操作するときの opt-in presentation です。同じ structured lifecycle payload から、state、conflict/action summary、ownership guidance、remediation、next action を表示します。別の planner、apply path、validator、state transition を実行するものではありません。

human output は parsing/automation contract ではありません。automation は JSON output と structured `code` を使用してください。exit status semantics は format に依存しません。

```sh
python scripts/compose.py inspect --target /repo --format human
python scripts/compose.py plan --config composition.json --target /repo --format human
```

install 済み runner 経由では `--format` は Composer option として forward されます。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /repo \
  inspect --format human
```

## CLI discovery

```sh
python scripts/compose.py --help
```

top-level help は `inspect -> plan -> apply -> validate`、`initial` / `update` / `upgrade`、各 `--config` rule、interrupted-upgrade recovery、output format、代表 command を表示します。この help path は read-only です。

`composer_update_plan.py`、`composer_apply.py`、`composer_managed.py`、`composer_transaction.py` などは internal implementation layer です。`scripts/compose.py` を直接呼ぶのは exact reviewed source checkout から authority-maintenance operation を行う場合です。通常の consumer は installed runner を使います。

## Runner binding

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /repo \
  COMMAND [COMPOSER OPTIONS]
```

runner が選択するのは `TakashiSasaki/templates` 内の lowercase 40-character full source revision だけです。stable default は `skills/composition/runtime-manifest.json`、advanced override は `--revision <full-sha>` です。`.template-composition/transaction.json` が存在すると、その exact source revision が recovery authority となり stable default より優先されます。conflicting explicit revision は拒否されます。

通常 consumer execution は templates checkout も Git on `PATH` も必要としません。revision 選択後、runner は canonical GitHub codeload endpoint からその exact full-SHA tar archive を download し、OS temporary directory に展開します。unsafe archive structure を拒否し、すべての regular file の SHA-256 inventory を作成します。snapshot source context は Composer の source identity と authority read を revision/inventory に bind します。authority file は acquired snapshot 内に存在し、inventory に含まれ、consume 時にも acquisition digest と一致していなければなりません。invocation 終了時には source snapshot と context metadata を削除します。

通常 runner で persistent cache されるのは isolated Python runtime だけです。cache identity は repository、revision、runtime-lock SHA-256、CPython major/minor、platform/machine を含みます。marker/digest/identity check、`pip check`、selected source revision の runtime verifier を通った matching entry のみ reuse します。miss では dependency resolution を無効にして exact `requirements-runtime.lock` environment を build し atomic install します。`COMPOSITION_RUNTIME_CACHE` で platform-default root を override できます。warm runtime があっても source archive は invocation ごとに再取得するため、normal Composer execution は完全 offline にはなりません。

runner 自身が `--target /repo` を追加し、forward された `--target` は拒否します。source acquisition と runtime-cache layout は implementation detail であり、Composer lifecycle、ownership、lock、transaction、diagnostic semantics を変えません。

## Source context と ancestry

Composer source authority は2種類の fail-closed source context のどちらかで表現されます。

- **snapshot context — normal consumer:** selected immutable full-SHA GitHub archive から source file を取得し、authority read を acquisition SHA-256 inventory で検証します。local Git checkout/history は不要です。
- **Git context — Composition authority 保守者:** reviewed checkout から `scripts/compose.py` を直接実行する場合、1つの exact clean Git revision が必要です。source authority は regular tracked file でなければならず、tracked modification は拒否されます。これは authority-maintenance path であり normal consumer prerequisite ではありません。

managed `update` / `upgrade` では old lock revision が selected target source revision と同一、またはその ancestor でなければなりません。検証 mechanism は source context により異なります。

- snapshot-backed normal execution は canonical GitHub Compare API に2つの immutable full SHA を渡します。`ahead` / `identical` は許可し、`behind` / `diverged` は拒否します。
- direct Git-context execution は local Git history から同じ relation を検証します。

ancestry verification は fail closed です。old revision が unavailable、GitHub compare response が unavailable/invalid、rate limit、network failure、malformed result などでは managed transition を許可しません。recovery ではさらに `.template-composition/transaction.json` に記録された exact target revision が必要です。

canonical source identity は両 context とも `TakashiSasaki/templates` です。abstraction は immutable revision/authority evidence の確立方法を変えるだけで、full-SHA source identity を弱めません。

## `inspect`

```sh
python scripts/compose.py inspect --target /repo
```

| State | Meaning |
| --- | --- |
| `absent` | target path が存在しない |
| `unmanaged` | target は存在するが Composition lock がない |
| `managed-valid` | lock と materialized state が valid |
| `managed-invalid` | Composition metadata は存在するが consumer validation が失敗する |
| `managed-interrupted` | `.template-composition/transaction.json` が存在し recovery が必要 |
| `invalid` | symbolic link など target root 自体が invalid |

`inspect` は transaction marker の存在だけで interrupted state と分類します。runner は Composer 起動前に exact recovery revision を選択するために必要な最小限の transaction metadata だけを検証し、recovery-state validation の authority は Composer に残します。

## Consumer configuration

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

`recipe` は production recipe を選択します。`components.include` / `exclude` は exposed `capability.*` / `lifecycle.*` を指定できます。set は disjoint、required component は exclude 不可、dependency closure に excluded component を含められません。

`parameters` は selected component ID を key とする object です。現在の production revision では parameter-specific materialization behavior はありませんが、parameter object は lock-v2 intent に normalize されるため変更には explicit `upgrade` が必要です。

## Lock schema v2

`.template-composition/lock.json` は Composer-owned resolved state です。exact source repository/revision、normalized intent、recipe/configuration digest、resolved component/version/descriptor digest、active material destination/owner/ownership/materialized digest を記録します。consumer は読むことはできますが hand-edit しません。

## Initial planning

```sh
python scripts/compose.py plan --config composition.json --target /repo
```

initial plan は `schema_version: 2`、`operation: "initial"` で、`source`、`intent`、`resolved_components`、`actions`、`conflicts`、`lock_preview` を含みます。

| Action | Meaning |
| --- | --- |
| `create` | destination が absent で作成可能 |
| `adopt-identical` | existing regular file が desired bytes と完全一致 |

異なる bytes、portable case collision、file/directory collision、symbolic link、unsafe path、existing Composer-managed metadata、invalid component/configuration resolution は conflict です。initial composition は異なる existing bytes を overwrite しません。

## Managed update planning

```sh
python scripts/compose.py plan --mode update --target /repo
```

managed update は lock-v2 normalized intent から configuration を reconstruct し、新しい `--config` は `UPDATE_CONFIG_NOT_ALLOWED` として拒否します。payload は `from_revision` / `to_revision`、intent、recipe transition、component groups、file action buckets、conflicts、`lock_preview` を含みます。

| Bucket | Meaning |
| --- | --- |
| `create` | new active material を absent safe destination に作成 |
| `replace` | clean `managed` / `generated` material を新 bytes に置換 |
| `remove` | clean `managed` / `generated` material を削除 |
| `preserve` | `seed` を consumer-owned のまま保持。removed seed も ordinary extra file として残す |
| `unchanged` | desired digest と一致 |
| `conflict` | unsafe/unsupported transition のため apply 禁止 |

component version change は update では `COMPONENT_VERSION_UPGRADE_REQUIRED` conflict です。

## Explicit upgrade planning

```sh
python scripts/compose.py plan --mode upgrade --config composition.json --target /repo
```

upgrade は explicit new intent を受け付け、component version change を explicit `component-version` compatibility boundary として扱います。version を変えず descriptor bytes が変わった場合は `COMPONENT_DESCRIPTOR_CHANGED_WITHOUT_VERSION` です。

file-owner / ownership-mode change は自動 migration されません。update の `*_UPGRADE_REQUIRED` を受けて explicit upgrade しても、current upgrade は migration を推測せず `*_NOT_SUPPORTED` を返します。source-side migration design が必要です。

## Apply behavior

`apply` は mutation 前に deterministic planning を再実行します。conflict があれば transaction を作らず終了します。

initial apply は absent destination だけを create、byte-identical file だけを adopt し、lock を最後に書いて consumer validation を行います。

managed update/upgrade は最初の mutation 前に `.template-composition/transaction.json` を書きます。transaction action は `create`、`replace`、`remove` だけです。replace/remove は current bytes が old lock digest と一致する必要があります。retry は already-applied new state を許可しますが third state は overwrite せず precondition error です。new lock install 後、transaction marker がある状態で consumer state を validate し、marker は最後に remove します。

## Ownership modes

| Ownership | Authority after initial materialization | Update/upgrade behavior |
| --- | --- | --- |
| `managed` | Composition source material | current bytes が old lock digest と一致する場合だけ replace/remove |
| `generated` | deterministic Composition generator | recompute し、current bytes が old lock digest と一致する場合だけ replace/remove |
| `seed` | consumer に transfer | initial materialization 後は update/upgrade が overwrite/delete しない |

active seed は consumer bytes が変わっても original provenance digest を next lock に保持します。removed seed は new lock から消え、ordinary consumer-owned content として repository に残ります。

## Recovery

managed transaction は durable roll-forward state です。marker がある間 `inspect` は `managed-interrupted` を報告します。

1. `transaction.source.revision` の exact revision を使用する。
2. `transaction.operation` の matching apply mode を再実行する。
3. marker を手動 edit/delete しない。
4. interrupted upgrade では `--config` を省略する。

```sh
python scripts/compose.py apply --mode update --target /repo
python scripts/compose.py apply --mode upgrade --target /repo
```

installed runner では source management と `--target` を省略します。runner は transaction の exact revision を読み、その immutable snapshot を取得して `--repository` target を supply します。

別 operation なら `RECOVERY_OPERATION_MISMATCH`、transaction と異なる source revision を選択すると `RECOVERY_SOURCE_MISMATCH` です。

## Consumer-facing managed lifecycle diagnostics

public entrypoint は structured diagnostic `code` を保持します。automation は human prose ではなく `code` と structured field を使用してください。

| Code | Meaning | Consumer action |
| --- | --- | --- |
| `INITIAL_MODE_REQUIRES_UNMANAGED_TARGET` | existing Composition lock がある | intent 維持なら `update`、変更なら `upgrade` |
| `MANAGED_LOCK_REQUIRED` | managed state なしで update/upgrade | `inspect` し、unmanaged の場合だけ initial |
| `UPDATE_CONFIG_NOT_ALLOWED` | update に `--config` | `--config` を外し、intent change は upgrade |
| `UPGRADE_CONFIG_REQUIRED` | new upgrade に target intent がない | `--config` を指定。recovery のみ省略 |
| `RECOVERY_CONFIG_NOT_ALLOWED` | upgrade recovery に `--config` | `--config` を外して matching recovery |
| `RECOVERY_REQUIRED` | unfinished transaction | new plan 前に exact revision で recovery。marker を削除しない |
| `RECOVERY_OPERATION_MISMATCH` | recovery mode が transaction と違う | recorded operation で `apply` |
| `RECOVERY_SOURCE_MISMATCH` | selected source が transaction exact revision ではない | runner では conflicting `--revision` を外して recovery。direct checkout では recorded revision を使う |
| `OLD_SOURCE_REVISION_UNAVAILABLE` | active source context で old lock revision を確立できない | normal runner は locked full SHA が canonical GitHub history に属することを確認し GitHub availability 後 retry。direct checkout は local history に revision を用意 |
| `SOURCE_REVISION_NOT_DESCENDANT` | target revision が old と同一/descendant でない | locked revision または descendant/equal を使用 |
| `SOURCE_TRANSITION_UNAVAILABLE` | snapshot ancestry の GitHub compare evidence が unavailable/invalid | canonical GitHub compare evidence が利用可能になってから retry。bypass しない |
| `COMPONENT_VERSION_UPGRADE_REQUIRED` | update で component version change | explicit upgrade |
| `COMPONENT_DESCRIPTOR_CHANGED_WITHOUT_VERSION` | version change なしの descriptor drift | source-side invariant を修正 |
| `LOCAL_MODIFICATION` | managed/generated bytes が old lock と違う | locked bytes を restore または ownership/source redesign。Composer は merge/overwrite/delete しない |
| `OLD_STATE_INVALID` | locked material missing/non-regular/unsafe | target state を修復して retry |
| `DESTINATION_CONFLICT` | new destination と existing structure が conflict | ordinary path を意図的に reconcile 後 `plan` |
| `FILE_OWNER_TRANSITION_UPGRADE_REQUIRED` | update が owner change を検出 | source-side migration design |
| `OWNERSHIP_TRANSITION_UPGRADE_REQUIRED` | update が ownership-mode change を検出 | source-side migration design |
| `FILE_OWNER_TRANSITION_NOT_SUPPORTED` | explicit upgrade でも owner migration が必要 | source-side migration design。lock hand-edit 不可 |
| `OWNERSHIP_TRANSITION_NOT_SUPPORTED` | explicit upgrade でも ownership migration が必要 | source-side migration design。lock hand-edit 不可 |
| `PRECONDITION_CHANGED` | transaction/plan 後に bytes/metadata が変化 | unexpected change を inspect。marker を保持し force overwrite しない |

その他、invalid source authority、malformed schema/configuration、unsafe path、unsupported generated handler、I/O failure などは source/contract failure です。

## Exit status

- `0` — requested operation、validation、explicit help が成功。
- `2` — invalid state、conflict、argument-level Composer error、managed-operation failure。
- `3` — initial apply 後の immediate consumer validation failure。Composer は just-written lock の remove を試みます。

JSON/human format は exit code を変えません。runner-local acquisition/selection failure も `2` ですが Composer 起動前に stderr に runner error として出ます。

## Consumer validator

すべての artifact は `lifecycle.composition-state` を含み、`.template-composition/` 以下に stdlib-only state validator、managed validation registry、selected-component validation runner を materialize します。

source-side `compose.py validate` は source-authority Composition-state validator の後、consumer の canonical `.template-composition/validate.py` を invoke します。state validation 成功後にのみ `resolved_components` を読み、selected component の registered validator だけを dispatch します。

Consumer validation は lock shape/semantics、materialized repository state、selected-component validation を検査します。`managed` / `generated` bytes は lock digest と一致、active `seed` file は存在必須ですが provenance digest と異なって構いません。product-mode release evidence/bundle は exact-candidate check で ordinary validation では deferred です。

Consumer validation は source component graph を再解決したり source descriptor bytes を検証したりしません。これらは source-side Composer の責務です。
