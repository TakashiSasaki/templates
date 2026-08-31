# Composition モデル

> **参考訳（非正本）:** この文書は英語版 `docs/architecture/composition-model.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

## 決定

`composition` branch は、再利用可能な artifact semantics、application capabilities、lifecycle contracts、recipes、schemas、および deterministic Composer の canonical source authority です。

Composition は4つの component role を分離します。

1. **foundations** — artifact dependency により導入される共有必須 baseline semantics を表します。
2. **artifact semantics** — Website、Web application、Agent Skill のように何を作るかを表します。
3. **capabilities** — runtime、CLI、MCP、MCP Apps、browser exposure、headless service など、再利用可能で任意選択の behavior を表します。
4. **lifecycle contracts** — composition state、contract evolution、implementation evidence、release evidence、release-bundle の再利用可能な machinery を表します。

Web application と Agent Skill は引き続き異なる artifact です。重複する monolithic template を持つのではなく、1つの component catalog に対する recipe を通じて再利用可能な authority を共有します。

legacy `skill` / `webapp` source-authority migration は完了しています。managed-state update/upgrade は独立した Composer lifecycle concern です。

## Source-time composition と consumer-time independence

materialization model は次のとおりです。

```text
recipe + consumer intent + immutable source revision
                    |
                    | resolve
                    v
             component closure
                    |
                    | materialize
                    v
          consumer repository + lock
```

中心となる invariant は次のとおりです。

> materialization が正常に完了した後、consumer repository は self-contained であり、Composition source checkout にアクセスせず steady composition state を validate できます。

source-side Composer operation が必要なのは、新しい state (`initial`, `update`, `upgrade`) を導出するとき、または中断された managed-state transaction を recovery するときだけです。

## Authority classes

Component ID は、次の component-role prefix のいずれか1つだけを持ちます。

- `foundation.*` — shared mandatory baseline semantics
- `artifact.*` — artifact-specific semantics
- `capability.*` — reusable optional capabilities
- `lifecycle.*` — reusable product-lifecycle machinery

prefix は descriptor の `component_role` と一致しなければなりません。foundation は artifact dependency により導入され、recipe から直接選択できません。non-artifact descriptor は、具体的な `artifact.*` authority を要求したり、それと conflict したりしてはなりません。artifact component は、それらの contract が artifact に本質的である場合、foundation、reusable capability、lifecycle component を require できます。

production catalog は closed です。catalog validation では、component と recipe inventory が source tree と一致していること、dependency が存在し acyclic であること、identity が unique であること、generic/artifact boundary が保持されること、および選択された conflict が reject されることを要求します。

## Component descriptor

component descriptor は次を宣言します。

- stable component `id`
- component `component_role`
- positive integer component `version`
- human-readable summary
- required component IDs
- conflicting component IDs
- ownership mode を持つ materialized destination
- bounded generated-material handler が使用する optional declarative registrations

`managed` と `seed` material は source path を宣言します。`generated` material には source path がありません。bytes は resolved component metadata から deterministic に導出されるためです。

descriptor には arbitrary executable install/update/post-install hook を含めません。

integer component version は明示的な compatibility boundary であり、SemVer ではありません。managed `update` は version change をまたげません。explicit `upgrade` は component-version change をまたぐことができます。component version が変わらないまま descriptor bytes が変化した場合、Composer は compatibility information が変わっていないかのように扱うのではなく、source transition を invariant violation として reject します。

## Recipe と consumer intent

recipe は consumer-facing な starting selection であり、implementation authority ではありません。次を宣言します。

- 1つの artifact component
- required reusable components
- default reusable components
- optional reusable components

required/default/optional set は pairwise disjoint です。

consumer configuration は unresolved intent を resolved lock とは別に記録します。

- recipe ID
- explicitly included capability/lifecycle IDs
- explicitly excluded capability/lifecycle IDs
- optional component-scoped parameters

include/exclude set は disjoint です。consumer は include/exclude によって recipe artifact を置き換えられません。resolver は recipe-required または transitive dependency の exclusion を reject し、resolved closure に存在しない component の parameter を reject します。

lock v2 に保存される normalized intent snapshot は、include/exclude ID を lexical に sort し、parameter 内の object key を recursive に sort する一方、array order は保持します。

## Deterministic resolution

validated configuration に対し、resolver は次から開始します。

```text
recipe artifact
+ recipe required components
+ recipe default components not explicitly excluded
+ explicit includes
```

その後、完全な transitive `requires` closure を計算し、exclusion/conflict を validate します。

Generated material は bounded allowlisted generator ID だけを使用します。現在の `contract-manifest-v1` generator は resolved closure から declarative contract registration を aggregate し、deterministic JSON を emit します。component descriptor が executable generator code を提供することはありません。

Composer は Composition state を導出するとき、mutable branch、wall-clock time、random value、network-discovered default、arbitrary hook、consumer code、package manager、product build/test/deploy command を参照しません。

## Lock schema version 2

canonical steady-state metadata path は次のとおりです。

```text
.template-composition/lock.json
```

Lock schema version 2 は次を記録します。

- canonical source repository identity
- exact nonzero lowercase 40-hex source commit revision
- normalized consumer `intent`
- resolution に使用した exact recipe bytes を bind する `recipe_sha256`
- 最後に明示的に渡された consumer configuration の exact bytes を bind する `configuration_sha256`
- positive integer version と descriptor SHA-256 digest を持つ lexically ordered resolved components
- owner、ownership mode、materialized SHA-256 digest を持つ lexically ordered materialized destinations

Lock v1 は意図的に unsupported です。この repository は pre-production のため、legacy migration path を保持せず contract を直接修正しました。

`configuration_sha256` は provenance であり、`intent` は update intent を再現するために必要な semantic authority です。そのため `update` には元の configuration file は不要です。`upgrade` は新しい explicit configuration を受け取り、normalized intent と configuration-byte provenance の両方を置き換えます。

lock には timestamp、random value、branch name、その他の意図的に nondeterministic な state は含まれません。

## File ownership

各 materialized destination には1つの component owner と1つの ownership mode があります。

### `managed`

Composition が bytes に対する authority を保持します。

Update/upgrade が managed file を replace または remove できるのは、現在の bytes が old lock digest と一致する場合だけです。local modification は conflict であり、暗黙に overwrite されることはありません。

### `generated`

bytes は target resolved composition から deterministic に再計算されます。

Generated file は managed file と同じ local-modification guard を使用します。現在の bytes が old lock digest と一致するときだけ regenerate または remove できます。

### `seed`

Composition がその destination の最初の materialization 時だけ bytes を供給し、その後 content ownership は consumer へ移ります。

old lock にすでに存在する seed について、update/upgrade は常に現在の consumer bytes を保持します。source-side seed change が上書きすることはありません。seed が引き続き selected である間、old seed provenance digest は new lock へ引き継がれます。

新たに selected された seed は、destination が absent かつ safe な場合にだけ create できます。その create が成功した後は consumer-owned です。

removed seed は決して delete されません。new lock から消え、通常の consumer-owned extra file として残ります。

## Destination と ownership invariants

materialized destination の component owner は最大1つです。Composition は複数 component で共有する file を patch、append、部分所有、merge しません。

portable destination comparison は次を reject します。

- `README.md` と `readme.md` のような ASCII case collision
- `contracts` と `contracts/mcp.json` のような file/directory prefix collision
- absolute または drive-prefixed path
- `.` / `..` segment
- repeated/trailing separator または backslash
- `-` で始まる segment
- ASCII case variant を含む任意の `.git` administration segment

既存 destination に対する component-owner change または ownership-mode change は自動的には推論されません。`update` は upgrade-required として報告します。explicit `upgrade` であっても、configuration が safe content-transfer policy を指定していないため automatic owner/ownership migration を拒否します。

component 間の aggregation は、separate declarative metadata と deterministic `generated` destination の designated owner によって実装されます。

## Policy coexistence boundary

Policy は独立した coding-agent operating authority であり、Composition capability ではありません。そのため Composition component と recipe は Policy adoption を表現せず、Composer は `agent-policy` を invoke したり、Policy profile、configuration、lock、runtime、release state を解釈したりしません。

Composition が enforce するのは mutation collision を避けるために必要な cross-authority ownership boundary だけです。次の path は foreign reserved destination です。

```text
.agent-policy.yml
.agent-policy.lock
.agent-policy/**
```

component descriptor、resolved lock inventory、managed transaction action、self-contained consumer validation は、portable case variant を含め、これらの path に対する claim を reject します。これは通常のすべての repository instruction path が Policy-owned であることを意味しません。Skill artifact の `AGENTS.md` は引き続き Composition `seed` です。initial materialization 後は consumer-owned となり、その後 Policy adoption が contents を置き換えても Composition update/upgrade がその bytes を overwrite することはありません。

逆方向の transition は意図的に推論しません。Skill initial composition 前に repository に別の Policy-generated `AGENTS.md` がすでに存在する場合、既存 destination conflict を保持し、explicit migration contract が存在するまで initial composition は fail closed します。

canonical cross-authority contract は Site-owned であり、[Policy–Composition coexistence contract](https://templates.moukaeritai.work/coexistence/) として公開されます。Composition の local model は自身が enforce する invariant だけを記録し、Policy semantics を複製したり、shared lock、transaction、umbrella management layer を導入したりしません。

## Public operation model

public lifecycle は次のとおりです。

```text
inspect -> plan -> apply -> validate
```

managed-state intent は operation mode によって明示されます。

```text
plan/apply --mode initial
plan/apply --mode update
plan/apply --mode upgrade
```

`--mode` の省略は initial Composer CLI との compatibility のため `initial` と同等です。

### Initial

Initial composition は explicit configuration を受け取り、existing lock が存在しないことを要求します。異なる unmanaged bytes を上書きすることはありません。同一の unmanaged material は adopt できます。lock は最後に書き込まれ、lock creation が unmanaged state から managed state への transition になります。

### Update

`update` は `lock.intent` を保持し、current descendant Composition source revision に対して reconcile します。新しい `--config` は reject します。

component version change は `COMPONENT_VERSION_UPGRADE_REQUIRED` として報告されます。同一 version の descriptor drift は source invariant violation として reject されます。

### Upgrade

`upgrade` は新しい operation のために explicit new configuration を要求します。recipe/include/exclude/parameters を変更でき、component-version boundary をまたぐことができます。

ownership protection は弱めません。managed/generated local change は引き続き conflict になり、seed contents は consumer-owned のままで、owner/ownership transition は引き続き unsupported automatic migration です。

update と upgrade はどちらも、old source revision が local source history に存在し、target source revision の ancestor または target と同一であることを要求します。downgrade または unrelated-history reconciliation は fail closed します。

## Read-only reconciliation

すべての update/upgrade は filesystem mutation より前に complete plan を構築します。

plan は component を次のように分類します。

```text
added / removed / changed / unchanged
```

file は次のように分類します。

```text
create / replace / remove / preserve / unchanged / conflict
```

managed/generated の replacement または removal は、現在の bytes が old lock digest と一致することを確認した後にだけ plan されます。new destination は empty かつ structurally safe でなければなりません。missing old locked material は implicit deletion ではなく invalid old state です。

plan には deterministic new-lock preview と explicit conflict list が含まれます。`plan` は read-only です。

同じ immutable source revision、selected intent、valid old managed state に対しては、plan ordering、generated bytes、lock preview は deterministic です。

## Managed-state transaction と recovery

Initial apply は old managed state が存在しないため "lock last" を使用できます。Update/upgrade では old lock がすでに repository を記述しているため、より強い protocol が必要です。

Composer は次を reserve します。

```text
.template-composition/transaction.json
.template-composition/staging/**
```

component はこれらの path を claim できません。`transaction.json` は実装済みの durable marker です。`staging/**` は将来の storage strategy の可能性のため reserve されたままです。

最初の managed-state file mutation より前に、apply は次を含む deterministic transaction marker を書き込みます。

- operation (`update` または `upgrade`)
- exact target source revision
- embedded old and new lock objects
- exact old/new lock-file identities
- digest precondition を持つ ordered create/replace/remove actions

mutation は deterministic roll-forward state machine に従います。

- create: destination は absent であるか、recovery 中なら recorded new digest とすでに一致していなければならない
- replace: destination は recorded old digest と一致するか、recorded new digest とすでに一致していなければならない
- remove: destination は recorded old digest と一致するか、すでに absent でなければならない
- third state、symlink、unsafe parent、non-regular-file state のいずれかでは overwrite せず停止する

new lock は material action の後にだけ install されます。new-state validation は transaction marker がまだ存在する間に実行されます。marker は最後に delete されます。

中断された場合、matching `apply --mode ...` を再実行すると、異なる operation を plan するのではなく existing marker を load します。recovery は transaction に記録された exact source revision を要求し、継続前に deterministic target bytes を reconstruct します。

Upgrade recovery は transaction-bound target intent を使用し、2つ目の `--config` を受け取りません。

これは rollback ではなく roll-forward です。この protocol は consumer-owned seed bytes を restore する必要がなく、予期しない local edit をどのように merge するかを推測しません。

## Consumer-time validation

`lifecycle.composition-state` は stdlib-only validator と lock schema を consumer repository に materialize します。

steady state では validator は lock-v2 shape、canonical source identity、deterministic ordering/portable path invariant、および current material を確認します。

- managed/generated file は存在し、lock digest と一致しなければならない
- active seed file は存在しなければならないが、recorded initial provenance digest と異なっていてよい
- lock inventory は foreign Policy-owned metadata destination を claim してはならない

`transaction.json` が存在する場合、steady-state validation は repository を interrupted managed state として拒否し、source-side recovery を要求します。

removed active composition の seed や Composition lock に列挙されていない independent Policy metadata を含む extra consumer-owned file は許可されます。

## Security と execution boundary

Composition は declarative のままです。consumer code または arbitrary component hook を execute しません。

Composer が行えるのは次です。

1. repository/composition state を inspect する
2. configuration と managed metadata を validate する
3. dependency/conflict を resolve する
4. read-only reconciliation plan を構築する
5. declared source bytes を materialize する
6. deterministic generated file を create する
7. digest-guarded filesystem mutation を実行する
8. lock/transaction metadata を書き込む
9. bounded composition-structure validation を実行する

Product build、test、deployment、application migration、runtime、package-install、coding-agent Policy command は Composer contract の外部にあります。

## Branch topology

canonical authority topology は次のとおりです。

```text
site          integrated reader-facing publication, assembly, Pages/PWA
policy        coding-agent policy authority
composition   artifact/capability/lifecycle authorities, recipes, schemas, Composer
```

Legacy `skill` / `webapp` authority migration と retirement は完了しています。これらの history は provenance であり、active Composition update source ではありません。

source unification によって reader-facing taxonomy が collapse するわけではありません。Site は、1つの immutable reviewed `composition` revision に帰属させながら、distinct Web application / Skill task-oriented view を引き続き公開できます。
