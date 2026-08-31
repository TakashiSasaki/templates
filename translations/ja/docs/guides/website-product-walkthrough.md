# Website product walkthrough

> **参考訳（非正本）:** この文書は英語版 `docs/guides/website-product-walkthrough.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

これは Composition で content-oriented Website を作る canonical first-use walkthrough です。supported browser product が、利用者が発見し、移動し、読み、共有する document / content を主とする場合に使います。主目的が application state と recoverable UI state を通じた interactive task なら [Webapp product walkthrough](webapp-product-walkthrough.md) を使ってください。境界は [Website と Web application の選び方](website-webapp-selection.md) で説明します。

例として **Project Docs** という小さな documentation Website を作ります。home page と guide page を持ちますが、application surface、task state、maintained runtime、PWA behavior は持ちません。これらは Website identity の前提ではありません。

## Completion path at a glance

1. **Doctor** — この walkthrough が使用する immutable Website-capable revision に対して installed Composition runner を確認する。
2. **Inspect** — target が unmanaged であることを確認する。
3. **Plan** — repository を変更せず `website` recipe を解決する。
4. **Review** — artifact、transitive foundation、actions、conflicts を確認する。
5. **Apply** — review した Website scaffold を materialize する。
6. **Validate scaffold** — 最初の `VALID` は scaffold milestone にすぎないと扱う。
7. **Define Website contract** — routes、page structure、document metadata、discovery、viewport intent を Project Docs に合わせる。
8. **Define planning evidence** — product claim 前に stable requirement と proof kind を定義する。
9. **Checkpoint planning** — implementation 開始前に planning state を validate し、machine-projected planning checkpoint action を実行する。
10. **Implement content and presentation** — consumer-owned HTML/CSS/assets と宣言済み browser identity asset を実装する。
11. **Run product and browser proof** — content と browser-sensitive Website target を real browser-backed evidence で証明する。
12. **Populate and validate product evidence** — proof command と record を接続し、truthful な場合だけ `product` mode に切り替え、保存された planning baseline に対して validate する。
13. **Checkpoint product** — machine-projected product checkpoint action を実行し、閉じた lifecycle transition を再 validate する。
14. **Optional capabilities** — product が実際に support または必要とするときだけ PWA/runtime/service/interface/release-bundle behavior を追加する。
15. **Evaluate release readiness** — machine-projected `check-release-readiness` action を実行する。required browser proof が deferred なら結果は `not-ready` になる。

重要な境界は、**scaffold validity は product completion ではない**という点です。Website product evidence は contract file の存在ではなく、実装済み Website を証明しなければなりません。

## 0. この walkthrough で何を作るか

Project Docs は別 consumer repository に作ります。Composition を使うだけのために `TakashiSasaki/templates` を clone せず、provider repository 内に Website を実装しません。

```text
TakashiSasaki/templates
        |
        | Composition tooling と Website contracts を提供
        v
your separate project-docs repository
```

最小経路は次です。

```text
create repository
  ↓
install Composition + doctor against immutable Website revision
  ↓
composition.json (`website`)
  ↓
inspect → plan → review → apply → validate
  ↓
valid Website scaffold
  ↓
truthful Website contracts + planning evidence
  ↓
validate planning → planning checkpoint
  ↓
consumer-owned Website implementation
  ↓
product/browser proof + product evidence
  ↓
validate product → product checkpoint → validate
  ↓
check-release-readiness → ready | not-ready
```

## 1. Consumer repository を作る

```sh
mkdir /absolute/path/to/project-docs
cd /absolute/path/to/project-docs
git init
```

この directory が product repository です。Git は通常の product tooling であり、Composition runner 自体の prerequisite ではありません。

## 2. Prerequisite を確認して Composition を install する

通常利用では CPython 3.11、3.12、3.13、3.14 のいずれかが必要です。[Composition の利用方法](../consumer-guide.md#install-and-run-the-composition-skill) の immutable installer procedure に従い、Project Docs の外へ skill を install します。

現在公開されている skill の stable runtime manifest は `website` recipe より古いため、この walkthrough では CI-green immutable Website-capable Composition revision `379073f376ce1de80948abd2e92d5560b573e7e6` を明示的に選択します。この revision には Website recipe と step 14 で説明する optional component set が含まれます。installed runner は immutable full-SHA override を support しています。この walkthrough の **すべて** の runner invocation で同じ revision を使ってください。省略すると consumer lock ではなく、より古い stable runtime-manifest revision に戻ります。

その exact revision に対して read-only doctor を実行します。

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/project-docs \
  --revision 379073f376ce1de80948abd2e92d5560b573e7e6 \
  doctor
```

`READY` は selected revision の local bootstrap prerequisite が利用可能という意味であり、Composition validation や後続 network/package availability の証明ではありません。続行前に doctor output の selected toolchain が `379073f376ce1de80948abd2e92d5560b573e7e6` であることを確認します。

## 3. `composition.json` を作る

Project Docs は content/document-oriented なので `website` を選択します。static output だから選ぶのではなく、product identity による選択です。この例では optional component は不要です。

```json
{
  "schema_version": 1,
  "recipe": "website",
  "components": {
    "include": [],
    "exclude": []
  },
  "parameters": {}
}
```

同じ machine-checked example を `examples/onboarding/project-docs/composition.json` に置きます。

`foundation.web` を直接 include してはいけません。foundation は artifact dependency として推移的に解決されます。Website が JavaScript を使う、generator で作られる、CDN に deploy されるという理由だけで `artifact.webapp-core`、`capability.runtime`、`capability.pwa` を追加しません。

## 4. Inspect → plan → review → apply

まず inspect します。

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/project-docs \
  --revision 379073f376ce1de80948abd2e92d5560b573e7e6 \
  inspect
```

fresh directory では `state: "unmanaged"` が期待値です。

absolute config path で plan します。

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/project-docs \
  --revision 379073f376ce1de80948abd2e92d5560b573e7e6 \
  plan --config /absolute/path/to/project-docs/composition.json
```

Initial planning is read-only です。apply 前に resolved closure が次を満たすことを確認します。

- `artifact.website-core`
- transitive `foundation.web`
- `lifecycle.lifecycle-checkpoints` を含む Website baseline lifecycle components
- **含まれない:** `artifact.webapp-core`、`capability.pwa`、`capability.runtime`

全 action を理解し、`conflicts` が空であることを確認してから同じ exact revision で apply します。

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/project-docs \
  --revision 379073f376ce1de80948abd2e92d5560b573e7e6 \
  apply --config /absolute/path/to/project-docs/composition.json
```

## 5. Scaffold を validate する

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/project-docs \
  --revision 379073f376ce1de80948abd2e92d5560b573e7e6 \
  validate
```

success は **Website scaffold** が valid であることだけを意味します。Project Docs の page が実装済み、browser evidence がある、release-ready である、という意味ではありません。

編集前に `.template-composition/lock.json` を読みます。materialization 後の `seed` は consumer-owned です。`managed`、`generated`、lock、transaction material は lock の authority boundary に従います。

## 6. Website contract boundary を理解する

Shared `foundation.web` は product-neutral browser contract を所有します。

- `contracts/browser-identity.json`
- `contracts/routes.json`
- `contracts/viewports.json`

`artifact.website-core` は Website-specific contract を所有します。

- `contracts/site-structure.json`
- `contracts/document-metadata.json`
- `contracts/site-discovery.json`

Project Docs に Webapp-private な `contracts/application-routes.json`、`contracts/surfaces.json`、`contracts/ui-states.json` は不要です。documentation site を説明するためだけに application surface や recoverable task state を発明しそうになったら、Webapp semantics を強制せず artifact boundary を見直してください。

## 7. Project Docs を具体化する

canonical route は2つです。

```text
home  -> /
guide -> /guide
```

consumer-owned seed contracts を整合的に更新します。

- `routes.json`: canonical route `guide`、必要な alias、accessibility focus target
- `site-structure.json`: page `guide`、route binding、parent `home`
- `document-metadata.json`: `siteName` を実際の product 名 `Project Docs` に変更し、両 page の visible/non-blank title/description と truthful indexability を設定する
- `site-discovery.json`: robots/sitemap path を分離し、indexable page と sitemap を正確に一致させ、product mode claim 前に concrete HTTPS `canonicalOrigin` を設定
- `viewports.json`: `minWidthPx: 0` の baseline を維持し、supported responsive behavior に対応する strictly increasing breakpoint のみ追加
- `browser-identity.json`: seed の `favicon.svg` 宣言は実装がその asset を実際に materialize する場合だけ維持する。そうでなければ consumer-owned seed contract を実際に提供する browser identity へ変更する

seeded `siteName: "Website"` は scaffold placeholder であり、Project Docs の product identity ではありません。この placeholder のまま product mode に移行してはいけません。

canonical path と alias は同じ URL namespace を共有します。同じ path を複数 route ID に割り当てたり、alias を別 canonical path と collision させてはいけません。

## 8. Product claim 前に planning evidence を定義する

`contracts/implementation-evidence.json` は scaffold/template material として始まります。Website requirement を実装済みと扱う前に truthful な `planning` evidence へ移し、stable requirement ID を維持します。

Website evidence target は current Website/shared contracts から導出されます。browser identity、Website page、page metadata、viewport、input capability は browser-sensitive target です。planning requirement は `end-to-end-test` や `accessibility-test` のような browser-level positive proof kind を宣言する必要があります。

canonical origin、robots、sitemap、feed など discovery proof family も evidence が必要ですが、すべてが browser-sensitive とは限りません。observable requirement に合う proof strength を使います。

後で別 evidence-producing capability を追加しても、Website validator は Website/shared target だけを所有します。PWA/runtime/service/Web-interface evidence を Website evidence として複製しません。

## 9. Planning を validate し mandatory planning checkpoint を作る

`artifact.website-core` は `lifecycle.implementation-evidence` を要求し、それが `lifecycle.lifecycle-checkpoints` を推移的に要求します。したがって checkpoint lifecycle は Website baseline の一部であり、この walkthrough の conditional extra ではありません。

Website contracts と implementation evidence を truthful な `planning` mode にしたら、**product implementation を始める前に** validate します。

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/project-docs \
  --revision 379073f376ce1de80948abd2e92d5560b573e7e6 \
  validate
```

planning validation が成功したら `lifecycle.next_actions` に planning checkpoint が投影されます。projected `next_action_command.argv` をそのまま実行し、checkpoint ID や supported Python executable など宣言された caller input だけを置換します。この guide から `checkpoint.py` syntax を再構成してはいけません。planning checkpoint の作成が成功するまで implementation を開始しません。これが product mode を照合する immutable validated baseline です。

## 10. Consumer-owned file に Website を実装する

seeded browser identity を維持する minimal static implementation なら例えば次です。

```text
index.html
guide/index.html
favicon.svg
assets/site.css
robots.txt
sitemap.xml
```

seed の `contracts/browser-identity.json` は `favicon.svg` を宣言します。Composition が consumer product asset 自体を materialize するわけではありません。宣言位置に truthful な `favicon.svg` を作成して Website から参照するか、product evidence で別 identity を claim する前に consumer-owned browser-identity contract を変更します。

SSR implementation でも同じ supported Website contract を実現できます。Composition は rendering strategy を規定しません。

実装は page title/description、navigation、canonical path、responsive behavior、keyboard use、robots/sitemap relation、宣言した browser identity を contract と一致させます。

## 11. Implemented Website を証明する

generated file、internal link、robots/sitemap consistency、browser-identity asset、build pipeline など通常の product check を実行します。さらに browser-sensitive Website target には **real browser-backed positive/negative proof** を実行します。

例:

- real browser で `/` と `/guide` を load し document identity と main focus target を確認
- 宣言した favicon/browser identity が実際に到達可能で使用されることを確認
- keyboard で primary navigation を操作
- representative viewport で forbidden horizontal scrolling がないことを確認
- happy path だけでなく unknown path など negative route case を確認

source inspection、HTTP fetch 成功、unit test、contract declaration だけでは browser-backed proof になりません。それらを `end-to-end-test` と再分類してはいけません。environment が required browser proof を実行できなければ proof を deferred にし、release readiness は `NOT READY` のままにします。

## 12. Product evidence を埋め planning baseline に対して validate する

implementation boundary と real proof command が存在してから `contracts/implementation-evidence.json` を `mode: "product"` にします。

各 required Website target について:

- target ごとに current record を1つ持つ
- browser-sensitive record を少なくとも1つの requirement から link する
- required な positive/negative browser-backed evidence を持つ
- browser-level proof は execution capability に `browser` を持つ authoritative command を参照する
- unrelated capability record は各 capability 自身の contract ID のまま保ち Website target にコピーしない

同じ exact revision に対して product verification と Composition validation を再実行します。

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/project-docs \
  --revision 379073f376ce1de80948abd2e92d5560b573e7e6 \
  validate
```

product-mode validation は step 9 の validated planning checkpoint を要求し、stable requirement と required proof kind が planning baseline と一致することを検証します。

## 13. Mandatory product checkpoint を作って再 validate する

product-mode validation が成功したら `lifecycle.next_actions` の product checkpoint entry に従います。その `next_action_command.argv` をそのまま実行します。lifecycle machinery が latest planning checkpoint binding を解決するため、parent や command ordering を prose から再構成しません。

product checkpoint 成功後に Composition validation をもう一度実行します。

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/project-docs \
  --revision 379073f376ce1de80948abd2e92d5560b573e7e6 \
  validate
```

この final validation が closed planning-to-product lifecycle state を確認します。planning baseline または required product checkpoint なしで evidence を `product` に切り替えただけの product は、この walkthrough では complete ではありません。

## 14. PWA / runtime / service / Web-interface / release-bundle は optional のまま

immutable revision `379073f376ce1de80948abd2e92d5560b573e7e6` の `website` recipe が公開する optional selection は正確に次の5つです。

- `capability.pwa`
- `capability.runtime`
- `capability.service`
- `capability.web-interface`
- `lifecycle.release-bundle`

Project Docs が installability/offline/update behavior を後から support する場合は `capability.pwa` を include する upgrade を行います。PWA は cross-cutting capability なので、artifact は Website のままです。network-only offline read policy では cached-content proof は不要で、route policy が cached content を許可するときだけ cached-content/freshness proof family が active になります。

maintained server runtime を持つなら `capability.runtime` を追加します。独立して support される non-browser API を公開するなら `capability.service` を追加し、runtime dependency は推移的に解決されます。別個に support される browser-facing operational/diagnostic interface を公開するなら `capability.web-interface` を使います。repository が packaging lifecycle を必要とするときだけ `lifecycle.release-bundle` を選択します。どの選択も `artifact.website-core` を `artifact.webapp-core` に変えず、release-bundle lifecycle の選択だけで release readiness が成立することもありません。

intent を変える場合は ordinary `update` ではなく `upgrade` を使います。upgrade 後も同じ immutable revision を plan/apply/validate 全体で一貫して使い、追加 capability 自身の contract と evidence requirement を満たします。

## 15. Release-readiness evaluation を実行する

ordinary `validate` は contract/lifecycle validity を確立しますが、release-readiness decision の代わりにはなりません。product checkpoint と final validation が成功した後、`lifecycle.next_actions` を確認します。release readiness を評価可能な場合、`check-release-readiness` implementation-evidence action が投影されなければなりません。

その action の complete `next_action_command.argv` をそのまま実行します。prose から command を再構成してはいけません。managed action registry は operation を `check-release-readiness` として定義し、structured output は `.template-composition/implementation-evidence-release-readiness.schema.json` に従います。

structured `release_readiness` field を authority として扱います。

- `ready`: blocking condition がない
- `not-ready`: 少なくとも1つ blocking condition が残る
- provider/action execution failure: operational failure であり、成功した `not-ready` decision ではない

required deferred browser proof は `not-ready` result を生じさせるか、その blocking condition に寄与しなければなりません。silent に release-ready と扱ってはいけません。structured result を product の release evidence とともに記録します。

## 16. Completion criteria

この walkthrough の Project Docs が complete なのは次をすべて満たす場合です。

- recipe が `website` で、resolved closure が `artifact.website-core` + transitive `foundation.web` を含み、Webapp-private artifact contract を含まない
- すべての `scripts/run.py` invocation が immutable Website-capable revision `379073f376ce1de80948abd2e92d5560b573e7e6` を使用し、古い published stable toolchain へ silently fallback していない
- routes、site structure、metadata、discovery、viewport、browser-identity contracts が実装済み Website を表し、`siteName: "Project Docs"` が seeded placeholder に置き換わっている
- actual page/content/navigation と `favicon.svg` のような宣言済み browser-identity asset が consumer-owned implementation に存在する
- product implementation 前の validated planning checkpoint と、その transition を閉じる final product checkpoint が存在する
- required product checks と real browser-backed positive/negative evidence が通る
- implementation evidence が truthful な `product` mode で browser-sensitive record が requirement-linked
- product checkpoint 後の Composition validation が通る
- machine-projected `check-release-readiness` action を実際に実行し、structured result を記録している
- required deferred proof があれば silently waive せず `release_readiness` を `not-ready` に保つ

static/dynamic や deployment で迷った場合は [Website と Web application の選び方](website-webapp-selection.md) に戻ってください。
