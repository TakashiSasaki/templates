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

| Command | Mode | `--target` | `--config` | Purpose |
| --- | --- | --- | --- | --- |
| `inspect` | none | required | not accepted | mutation せず target state を分類する |
| `plan` | `initial` or omitted | required | required | 最初の materialization を計画する |
| `apply` | `initial` or omitted | required | required | 最初の materialization を実行する |
| `plan` | `update` | required | forbidden | lock-v2 intent を保持して current descendant source へ reconcile する計画を作る |
| `apply` | `update` | required | forbidden | managed update を適用または recovery する |
| `plan` | `upgrade` | required | required | 明示的な intent / compatibility-boundary change を計画する |
| `apply` | `upgrade` | required | required for a new upgrade; forbidden during recovery | 明示的な upgrade を開始または recovery する |
| `validate` | none | required | not accepted | current consumer state を検証する |

Initial mode が default です。次の2つは同等です。

```sh
python scripts/compose.py plan --config composition.json --target /repo
python scripts/compose.py plan --mode initial --config composition.json --target /repo
```

dispatcher は command の前後どちらに `--mode` があっても受け付けますが、例とドキュメントでは command-first form を使用します。

## CLI discovery

public entrypoint は、consumer がどの internal adapter が command を処理するか知る必要がないよう、完全な lifecycle と mode/config rules を公開します。

```sh
python scripts/compose.py --help
```

top-level help には `inspect -> plan -> apply -> validate`、`initial` / `update` / `upgrade` mode、各 mode の `--config` 要件、interrupted-upgrade recovery behavior、代表的な command が表示されます。この help path は read-only で、Composition source state を load せず、consumer repository を inspect しません。

`composer_update_plan.py`、`composer_apply.py`、`composer_managed.py`、`composer_transaction.py` などの internal module は implementation layer であり、別の public entrypoint ではありません。consumer automation と documentation が `scripts/compose.py` を直接呼び出すのは、exact reviewed source checkout から操作するときだけにしてください。通常の installed-skill operation は同じ entrypoint に delegate します。

## Runner binding

install 済み runner の syntax は次のとおりです。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /repo \
  COMMAND [COMPOSER OPTIONS]
```

runner が選択するのは、`TakashiSasaki/templates` 内の lowercase 40-character full source revision だけです。stable default は `skills/composition/runtime-manifest.json` から取得され、明示的な `--revision <full-sha>` でその default を override できます。`.template-composition/transaction.json` が存在する場合、その exact source revision が recovery の authority となり、stable default を override します。conflicting explicit revision は拒否されます。

revision を選択すると、runner は独立して検証される2層の persistent cache を reuse または build します。source cache は exact revision を key とし、その SHA で detached のまま、canonical remote を指し、LF-preserving checkout settings の下で byte-clean であり、traversable ancestor history を保持している必要があります。runtime cache は repository、revision、runtime-lock SHA-256、CPython major/minor、platform/machine を key とします。cache hit は marker/digest/identity checks、`pip check`、選択した source revision の runtime verifier を通過した場合だけ受け入れられます。miss の場合、runner は exact source を fetch するか、dependency resolution を無効にして exact `requirements-runtime.lock` environment を build し、新しい cache entry を atomic に install します。valid cache hit では network acquisition は不要です。controlled environment では `COMPOSITION_RUNTIME_CACHE` で platform-default cache root を override できます。runner 自身が `--target /repo` を追加し、forward された `--target` option は拒否します。cache layout と reuse は performance detail であり、Composer semantics を再定義しません。

## Source checkout requirements

Composer は Composition source checkout から実行されます。composition が consume する source authority は、1つの exact clean revision の下にある regular Git-tracked file でなければなりません。

managed `update` と `upgrade` では、次の条件が必要です。

- consumer lock に記録された old revision が local Composition Git history で利用可能であること。
- target source revision が old revision と同一か、その descendant であること。
- recovery では `.template-composition/transaction.json` に記録された exact target revision を使用すること。

canonical source identity は `TakashiSasaki/templates` の Composition authority です。installed runner は、選択された revision の ancestor history を持つ detached exact-SHA checkout を取得または reuse し、reuse 前にその history を検証します。このため、これらの check は wrapper によって弱められるのではなく、引き続き Composer-owned です。

## `inspect`

Syntax:

```sh
python scripts/compose.py inspect --target /repo
```

取り得る `state` value は次のとおりです。

| State | Meaning |
| --- | --- |
| `absent` | target path が存在しない |
| `unmanaged` | target は存在するが Composition lock がない |
| `managed-valid` | lock と materialized state が valid |
| `managed-invalid` | Composition metadata は存在するが consumer validation が失敗する |
| `managed-interrupted` | `.template-composition/transaction.json` が存在し recovery が必要 |
| `invalid` | symbolic link など、target root 自体が invalid |

`inspect` は transaction marker の存在だけで interrupted managed state と分類するのに十分と扱います。recovery 前に transaction の内容を trust したり、それに基づいて branch したりしません。runner は Composer を起動する前に exact recovery source revision を選択するために必要な最小限の transaction metadata だけを別途検証します。recovery-state validation の authority は引き続き Composer です。

## Consumer configuration

Configuration schema version 1 には4つの required field があります。

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

`recipe` は production recipe を選択します。`components.include` と `components.exclude` には exposed `capability.*` または `lifecycle.*` component を指定できます。include/exclude set は disjoint でなければならず、required component は exclude できません。また、selected dependency closure に excluded component を含めることはできません。

`parameters` は、選択された `artifact.*`、`capability.*`、`lifecycle.*` component ID を key とする object です。schema は component-local object value を許可します。現在の production revision では materialization は parameter value を consume せず、production component は parameter-specific material behavior を宣言していません。それでも parameter object は lock-v2 intent に normalize されるため、変更には明示的な `upgrade` が必要です。

## Lock schema v2

`.template-composition/lock.json` は Composer-owned resolved state です。次の情報を記録します。

- exact source repository と revision。
- normalized intent: recipe、sorted include/exclude choices、normalized parameters。
- exact recipe digest。
- 最後に supplied された configuration bytes の digest。
- resolved component IDs、component versions、descriptor digests。
- すべての active material destination、owner component、ownership mode、materialized digest。

consumer は state と ownership を理解するため lock を読むことはできますが、手動で編集すべきではありません。

## Initial planning

Syntax:

```sh
python scripts/compose.py plan --config composition.json --target /repo
```

initial plan payload は `schema_version: 2`、`operation: "initial"` です。重要な field には `source`、`intent`、`resolved_components`、`actions`、`conflicts`、`lock_preview` があります。

Initial action value は次のとおりです。

| Action | Meaning |
| --- | --- |
| `create` | destination が absent で、安全に作成できる |
| `adopt-identical` | existing regular file が desired bytes と完全に同一である |

Initial conflict は別に報告されます。異なる existing bytes、portable case collision、file/directory collision、symbolic link、unsafe path、existing Composer-managed metadata、invalid component/configuration resolution がある場合、apply は実行されません。

Initial composition は異なる existing bytes を決して overwrite しません。

## Managed update planning

Syntax:

```sh
python scripts/compose.py plan --mode update --target /repo
```

managed update plan は `schema_version: 1`、`operation: "update"` です。lock-v2 normalized intent から configuration を reconstruct します。新しい `--config` は `UPDATE_CONFIG_NOT_ALLOWED` として拒否されます。

payload には次の情報が含まれます。

- `from_revision` / `to_revision`。
- unchanged normalized `intent`。
- recipe digest transition information。
- component の `added`、`removed`、`changed`、`unchanged` group。
- file action bucket。
- structured top-level `conflicts`。
- `lock_preview`。

Managed file action bucket は次のとおりです。

| Bucket | Meaning |
| --- | --- |
| `create` | new active material を absent safe destination に作成できる |
| `replace` | clean な `managed` または `generated` material の bytes が変わり、replace できる |
| `remove` | clean な `managed` または `generated` material が active composition から外れ、delete できる |
| `preserve` | `seed` は consumer-owned のまま変更されず、removed seed も ordinary extra file として残る |
| `unchanged` | active `managed` / `generated` material がすでに desired digest と一致している |
| `conflict` | transition が unsafe または unsupported で、apply は mutation してはならない |

component version change は update では conflict となり、`COMPONENT_VERSION_UPGRADE_REQUIRED` を報告します。

## Explicit upgrade planning

Syntax:

```sh
python scripts/compose.py plan --mode upgrade --config composition.json --target /repo
```

Upgrade は explicit new intent を受け付けます。plan には `intent.from` と `intent.to`、configuration digest transition、recipe transition、component transition、同じ managed file action bucket、conflicts、新しい lock preview が含まれます。

component version change は upgrade 中は explicit `component-version` compatibility boundary として受け入れられます。component-version を変更せず descriptor bytes が変化した場合は引き続き invalid で、`COMPONENT_DESCRIPTOR_CHANGED_WITHOUT_VERSION` を報告します。

file-owner と ownership-mode change は自動 migration されません。Update はこれらを `*_UPGRADE_REQUIRED` として識別する場合がありますが、public message は current upgrade でもその migration を推測しないことを明示します。Explicit upgrade は migration を推測せず、対応する `*_NOT_SUPPORTED` conflict を報告します。

## Apply behavior

`apply` は mutation 前に deterministic planning をもう一度実行します。conflict のある plan は managed transaction を作成せず return します。

Initial apply は absent destination だけを作成し、byte-identical existing file だけを adopt し、lock を最後に書き込んだ後、consumer validation を実行します。

Managed update/upgrade は最初の managed-state mutation の前に `.template-composition/transaction.json` を書き込みます。transaction action になるのは `create`、`replace`、`remove` だけです。`preserve` と `unchanged` は file を mutate しません。

`replace` と `remove` では、current bytes が old lock digest と引き続き一致している必要があります。retry はすでに適用済みの new state を受け入れます。third state があれば overwrite せず precondition error を報告します。

new lock は file action の後に install され、transaction marker がまだ存在する状態で consumer state を validate し、marker は最後に remove されます。

## Ownership modes

| Ownership | Authority after initial materialization | Update/upgrade behavior |
| --- | --- | --- |
| `managed` | Composition source material が引き続き authoritative | current bytes が old lock digest と等しい場合だけ replace/remove できる |
| `generated` | deterministic Composition generator が引き続き authoritative | recompute され、current bytes が old lock digest と等しい場合だけ replace/remove できる |
| `seed` | ownership が consumer に transfer される | first materialization 後は update/upgrade によって overwrite または delete されない |

active のまま残る seed file は、consumer bytes が異なっていても next lock に original provenance digest を保持します。removed seed は new lock から消えますが、repository には ordinary consumer-owned content として残ります。

## Recovery

managed transaction は durable roll-forward state です。marker が存在する間、`inspect` は `managed-interrupted` を報告します。

Recovery requirements は次のとおりです。

1. `transaction.source.revision` に記録された exact Composition source revision を使用する。
2. `transaction.operation` に記録された matching apply mode を再実行する。
3. marker を手動で edit または delete しない。
4. interrupted upgrade では、target intent と new lock がすでに記録されているため `--config` を省略する。

Examples:

```sh
python scripts/compose.py apply --mode update --target /repo
python scripts/compose.py apply --mode upgrade --target /repo
```

install 済み runner 経由の同等 command では source checkout management と `--target` を省略します。runner は transaction の exact source revision を読み、`--repository` から target を supply します。

別 operation の transaction に対しては `RECOVERY_OPERATION_MISMATCH`、異なる source checkout に対しては `RECOVERY_SOURCE_MISMATCH` が報告されます。

## Consumer-facing managed lifecycle diagnostics

以下の code は通常の consumer operation で特に重要です。public `scripts/compose.py` entrypoint は structured diagnostic `code` を保持し、既知の managed-lifecycle `message` field には presentation 時に remediation を追加します。underlying planner/transaction code と fail-closed decision は変更されません。automation は `message` prose を match するのではなく、`code` と structured field を key にしてください。

| Code | Meaning | Consumer action |
| --- | --- | --- |
| `INITIAL_MODE_REQUIRES_UNMANAGED_TARGET` | initial mode で existing Composition lock が見つかった | intent を保持するなら `update`、intent/boundary を変更するなら `upgrade` を使用する |
| `MANAGED_LOCK_REQUIRED` | managed state がない状態で update/upgrade が要求された | `inspect` を実行し、target が unmanaged かつ lock がない場合だけ initial mode を使用する |
| `UPDATE_CONFIG_NOT_ALLOWED` | update に `--config` が supplied された | `--config` を外す。意図的な recipe/component/parameter/boundary change には upgrade を使用する |
| `UPGRADE_CONFIG_REQUIRED` | new upgrade planning/apply に explicit target intent がない | `--config` を supply する。interrupted upgrade recovery の場合だけ省略する |
| `RECOVERY_CONFIG_NOT_ALLOWED` | upgrade recovery 中に `--config` が supplied された | `--config` を外し、exact recorded source revision で `apply --mode upgrade` を再実行する |
| `RECOVERY_REQUIRED` | unfinished managed transaction が存在する | 別の plan の前に recorded operation を exact source revision で recovery する。marker を delete しない |
| `RECOVERY_OPERATION_MISMATCH` | requested recovery mode が transaction operation と異なる | transaction に記録された operation で `apply` を再実行する |
| `RECOVERY_SOURCE_MISMATCH` | source checkout が transaction に記録された exact revision ではない | recorded revision を checkout し matching apply を retry する。upgrade recovery では `--config` を省略する |
| `OLD_SOURCE_REVISION_UNAVAILABLE` | old lock revision が local Composition history にない | retry 前にその revision を local で利用可能にする。ancestry validation を bypass しない |
| `SOURCE_REVISION_NOT_DESCENDANT` | target Composition revision が old revision と同一でも descendant でもない | locked revision または descendant/equal source revision を使用する |
| `COMPONENT_VERSION_UPGRADE_REQUIRED` | update が component version change に遭遇した | desired intent と `--config` を指定して explicit upgrade を plan する |
| `COMPONENT_DESCRIPTOR_CHANGED_WITHOUT_VERSION` | version change なしで descriptor bytes が変化した | source-side invariant が壊れている。consumer 側で bypass しない |
| `LOCAL_MODIFICATION` | managed/generated current bytes が old lock と異なる | locked bytes を restore するか source/ownership を redesign する。Composer は unexpected local state を merge、overwrite、delete しない |
| `OLD_STATE_INVALID` | locked material が missing、non-regular、または unsafe path の下にある | retry 前に target state を repair する。Composer は unexpected state を overwrite して repair しない |
| `DESTINATION_CONFLICT` | newly selected destination が existing repository structure と conflict する | ordinary repository path を意図的に reconcile してから `plan` を再実行する |
| `FILE_OWNER_TRANSITION_UPGRADE_REQUIRED` | update が1つの destination で component-owner change を検出した | update では自動的に越えられず、current upgrade も migration を推測しない。source-side migration を設計する |
| `OWNERSHIP_TRANSITION_UPGRADE_REQUIRED` | update が ownership-mode change を検出した | update では自動的に越えられず、current upgrade も migration を推測しない。source-side migration を設計する |
| `FILE_OWNER_TRANSITION_NOT_SUPPORTED` | explicit upgrade でも owner migration が必要 | explicit source-side migration design を用意する。lock metadata を edit したり unchanged のまま retry したりしない |
| `OWNERSHIP_TRANSITION_NOT_SUPPORTED` | explicit upgrade でも ownership migration が必要 | explicit source-side migration design を用意する。lock metadata を edit したり unchanged のまま retry したりしない |
| `PRECONDITION_CHANGED` | transaction/plan precondition 確立後に bytes または metadata が変化した | unexpected change を inspect する。transaction marker がある場合は保持し、force overwrite しない |

その他の code は、invalid source authority、malformed schema/configuration、unsafe path、unsupported generated handler、I/O failure などを表す場合があります。これらは通常の lifecycle choice ではなく source/contract failure です。

## Exit status

explicit help output を除き、CLI は normal result と Composer error を standard output に JSON として emit します。

- `0` — requested operation、validation、または explicit help が成功した。
- `2` — invalid state、conflict、argument-level Composer error、または managed-operation failure。
- `3` — initial apply が file を materialize した後、immediate post-apply consumer validation が失敗した。Composer は repository が successfully managed と報告されないよう、書き込んだばかりの lock の remove を試みる。

Argparse usage error は Python `argparse` behavior に従います。runner-local acquisition または selection failure も `2` を返しますが、Composer が invoked される前に runner error として standard error へ出力されます。

## Consumer validator

すべての artifact は `lifecycle.composition-state` を含み、`.template-composition/` 以下に stdlib-only validator を materialize します。source-side の `compose.py validate` command は、その source authority version の validator を invoke します。

Consumer validation は lock shape/semantics と materialized repository state を検証します。`managed` と `generated` bytes は lock digest と一致しなければなりません。active `seed` file は存在し続ける必要がありますが、provenance digest と異なっていても構いません。

consumer validator は source component graph を再解決したり source descriptor bytes を検証したりしません。これらの check は source-side Composer の責務です。
