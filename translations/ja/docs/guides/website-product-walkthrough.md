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
12. **Populate and validate product evidence** — proof command、release gate、record、stable requirement を接続し、truthful な場合だけ `product` mode に切り替え、保存された planning baseline に対して validate する。
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

通常利用では CPython 3.11、3.12、3.13、3.14 のいずれかが必要です。[Composition の利用方法](../consumer-guide.md#composition-skill-install) の immutable installer procedure に従い、Project Docs の外へ skill を install します。

現在公開されている skill の stable runtime manifest は `website` recipe より古いため、この walkthrough では CI-green immutable Website-capable Composition revision `ca8b8bc9091c6c199224cd9b66c9a59229f1b6ac` を明示的に選択します。この revision には Website recipe と step 14 で説明する optional component set が含まれます。installed runner は immutable full-SHA override を support しています。この walkthrough の **すべて** の runner invocation で同じ revision を使ってください。省略すると consumer lock ではなく、より古い stable runtime-manifest revision に戻ります。

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/project-docs \
  --revision ca8b8bc9091c6c199224cd9b66c9a59229f1b6ac \
  doctor
```

`READY` は selected revision の local bootstrap prerequisite が利用可能という意味であり、Composition validation や後続 network/package availability の証明ではありません。続行前に doctor output の selected toolchain が `ca8b8bc9091c6c199224cd9b66c9a59229f1b6ac` であることを確認します。

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

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/project-docs \
  --revision ca8b8bc9091c6c199224cd9b66c9a59229f1b6ac \
  inspect
```

fresh directory では `state: "unmanaged"` が期待値です。

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/project-docs \
  --revision ca8b8bc9091c6c199224cd9b66c9a59229f1b6ac \
  plan --config /absolute/path/to/project-docs/composition.json
```

Initial planning は read-only です。apply 前に resolved closure が `artifact.website-core`、transitive `foundation.web`、`lifecycle.lifecycle-checkpoints` を含み、`artifact.webapp-core`、`capability.pwa`、`capability.runtime` を含まないことを確認します。全 action を理解し、`conflicts` が空であることを確認します。

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/project-docs \
  --revision ca8b8bc9091c6c199224cd9b66c9a59229f1b6ac \
  apply --config /absolute/path/to/project-docs/composition.json
```

## 5. Scaffold を validate する

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/project-docs \
  --revision ca8b8bc9091c6c199224cd9b66c9a59229f1b6ac \
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

step 7 の exact two-page Project Docs baseline では、step 9 の前に scaffold evidence file を次の planning payload に置換します。

```json
{
  "$schema": "../schemas/implementation-evidence.schema.json",
  "schemaVersion": 6,
  "mode": "planning",
  "commands": [],
  "releaseGates": [],
  "records": [],
  "requirements": [
    {
      "id": "WEBSITE-BROWSER",
      "description": "Project Docs browser-facing Website behavior requires browser-level positive proof.",
      "targets": [
        {"kind": "contract-item", "contractId": "browser_identity", "itemKind": "proof-family", "itemId": "browser-identity"},
        {"kind": "contract-item", "contractId": "document_metadata", "itemKind": "page-metadata", "itemId": "guide"},
        {"kind": "contract-item", "contractId": "document_metadata", "itemKind": "page-metadata", "itemId": "home"},
        {"kind": "contract-item", "contractId": "site_structure", "itemKind": "page", "itemId": "guide"},
        {"kind": "contract-item", "contractId": "site_structure", "itemKind": "page", "itemId": "home"},
        {"kind": "contract-item", "contractId": "viewports", "itemKind": "input-capability", "itemId": "keyboard"},
        {"kind": "contract-item", "contractId": "viewports", "itemKind": "viewport", "itemId": "base"}
      ],
      "recordIds": [],
      "requiredPositiveProofKinds": ["accessibility-test", "end-to-end-test"]
    },
    {
      "id": "WEBSITE-DISCOVERY",
      "description": "Project Docs discovery resources require inspection against the declared public Website contract.",
      "targets": [
        {"kind": "contract-item", "contractId": "site_discovery", "itemKind": "proof-family", "itemId": "canonical-origin"},
        {"kind": "contract-item", "contractId": "site_discovery", "itemKind": "proof-family", "itemId": "robots"},
        {"kind": "contract-item", "contractId": "site_discovery", "itemKind": "proof-family", "itemId": "sitemap"}
      ],
      "recordIds": [],
      "requiredPositiveProofKinds": ["inspection"]
    }
  ]
}
```

同じ payload は `examples/onboarding/project-docs/implementation-evidence.planning.json` にあり、implementation-evidence schema と Website validator の derived target inventory に対して regression check されています。page、feed、viewport、input capability を baseline より増やした場合はこの target list をそのまま再利用せず、current contracts から導出される全 target を planning requirements で cover してから validate します。

canonical origin、robots、sitemap、feed など discovery proof family も evidence が必要ですが、すべてが browser-sensitive とは限りません。observable requirement に合う proof strength を使います。

後で別 evidence-producing capability を追加しても、Website validator は Website/shared target だけを所有します。PWA/runtime/service/Web-interface evidence を Website evidence として複製しません。

## 9. Planning を validate し mandatory planning checkpoint を作る

`artifact.website-core` は `lifecycle.implementation-evidence` を要求し、それが `lifecycle.lifecycle-checkpoints` を推移的に要求します。したがって checkpoint lifecycle は Website baseline の一部であり、この walkthrough の conditional extra ではありません。

Website contracts と implementation evidence を truthful な `planning` mode にしたら、**product implementation を始める前に** validate します。

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/project-docs \
  --revision ca8b8bc9091c6c199224cd9b66c9a59229f1b6ac \
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
- happy path screenshot だけでなく negative route/path case を確認

source inspection、HTTP fetch success、unit test、contract declaration だけでは browser-backed proof になりません。それらを `end-to-end-test` と relabel しません。必要な browser proof を実行できない environment では deferred とし、release readiness は `NOT READY` のままにします。

## 12. Product evidence を記録して planning に対して validate する

implementation boundary と具体的な proof harness が存在してから `contracts/implementation-evidence.json` を `mode: "product"` にします。step 7 の exact two-page Project Docs baseline では、[published Project Docs product evidence example](../../../../examples/onboarding/project-docs/implementation-evidence.product.json) から machine-checked JSON を取得し、`contracts/implementation-evidence.json` にコピーしてから consumer repository の実際の proof harness command と implementation locator に合わせて調整します。この JSON は publication catalog の machine asset として公開されるため、通常 consumer が `TakashiSasaki/templates` を clone する必要はありません。provider source path は `examples/onboarding/project-docs/implementation-evidence.product.json` です。

published product example はすべての proof `status` を意図的に `deferred` のままにしています。これにより consumer がまだ browser/discovery proof を実行していないのに verified と偽ることなく structural product evidence を validate できます。したがって実 proof が完了するまで release-readiness は `not-ready` のままです。Project Docs で例を使う前に、参照される repository proof harness `tests/verify_project_docs_browser.py` と `tests/verify_project_docs_discovery.py` を作成するか、`commands` と harness locator を実際の proof program に置換します。

Product evidence は単なる record list ではなく cross-reference graph です。

1. `commands` は executable proof harness と execution capability を宣言する。negative evidence に使う command は `supportsNegativePath: true` を宣言する。
2. 各 `releaseGates[].commandIds` は gate が実際に実行する proof command を列挙する。
3. 各 record の positive/negative proof は `commandId` でその proof を生成した command を参照する。
4. 各 record の `releaseGateIds` は、その record が使う **すべて** の proof command を `commandIds` に含む selected gate を少なくとも1つ参照する。
5. planning の stable requirement は同じ `id`、`targets`、`requiredPositiveProofKinds` を維持し、planning 時に空だった `recordIds` を、その target を正確に cover する product record に置換する。
6. unused command または release gate を evidence document に残さない。product validation は unknown reference だけでなく unused graph node も拒否する。

Project Docs example では browser-sensitive record はすべて `project-docs-browser-proof` を参照し `project-docs-browser-gate` を選択します。discovery record は `project-docs-discovery-proof` を参照し `project-docs-discovery-gate` を選択します。browser gate の `commandIds` は browser proof command を含み、discovery gate の `commandIds` は discovery proof command を含みます。これにより evidence が参照する command が、その record が選択した release gate の実行対象であることを保証します。

各 required Website target について、current record は1つだけにし、すべての record をその target を所有する stable requirement から link します。必要な positive/negative browser-backed evidence を記録し、browser-level proof の authoritative command は execution capability `browser` を宣言します。各 linked record は有効な `releaseGateIds` を少なくとも1つ持ち、その gate が record の全 proof command を実行しなければなりません。unrelated capability record を Website target に複製しません。

実 proof command が成功した後だけ、proof の locator、command、description、expected result、actual observed result が実際に実行した proof を truthful に表す場合に `deferred` から `verified` へ変更します。`expectedResult` は unrelated target family 間で generic な同一文を再利用せず、record target ごとの claim-specific な内容にします。generic implementation-evidence validator は suspiciously broad な exact proof reuse を warning として報告します。release-readiness を green にする目的で example の deferred status を一括変換してはいけません。

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/project-docs \
  --revision ca8b8bc9091c6c199224cd9b66c9a59229f1b6ac \
  validate
```

Product-mode validation は step 9 の validated planning checkpoint を要求し、stable requirement と required proof kind が planning baseline と一致することを確認します。また missing release gate、unknown command/gate reference、selected release gate が実行しない proof command、unused command/gate を fail closed で拒否します。

## 13. Mandatory product checkpoint を作って再 validate する

product-mode validation 成功後、`lifecycle.next_actions` の product checkpoint entry に従い、`next_action_command.argv` をそのまま実行します。parent や command ordering を prose から再構成しません。

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/project-docs \
  --revision ca8b8bc9091c6c199224cd9b66c9a59229f1b6ac \
  validate
```

この final validation が planning-to-product lifecycle state の closure を確認します。

## 14. Optional PWA/runtime/service/Web-interface/release-bundle behavior は optional のまま

immutable revision `ca8b8bc9091c6c199224cd9b66c9a59229f1b6ac` の `website` recipe は次だけを optional selection として公開します。

- `capability.pwa`
- `capability.runtime`
- `capability.service`
- `capability.web-interface`
- `lifecycle.release-bundle`

Project Docs が後で installability/offline/update behavior を support するなら `capability.pwa` を追加します。PWA は cross-cutting capability なので Website のままです。maintained server runtime があれば `capability.runtime`、独立して support する non-browser API があれば `capability.service`、別に support する browser-facing operational/diagnostic interface があれば `capability.web-interface` を追加します。packaging lifecycle が必要な場合だけ `lifecycle.release-bundle` を選択します。どの選択も `artifact.website-core` を `artifact.webapp-core` に変えません。

selected component intent を変更するときは ordinary `update` ではなく `upgrade` を使います。upgrade 後も同じ immutable revision で plan/apply/validate し、追加 capability 自身の contract/evidence requirement を満たします。

## 15. Release-readiness evaluation を実行する

ordinary `validate` は contract/lifecycle validity を確認しますが、release-readiness decision の代わりではありません。product checkpoint と final validation 成功後、`lifecycle.next_actions` が `check-release-readiness` implementation-evidence action を投影することを確認します。

その complete `next_action_command.argv` をそのまま実行します。prose から command を再構成しません。structured output の `release_readiness` field を authority とします。

- `ready`: blocking condition なし
- `not-ready`: 少なくとも1つ blocking condition が残る
- provider/action execution failure: operational failure であり、successful `not-ready` decision ではない

required browser proof が deferred なら `not-ready` を生成または構成しなければならず、release-ready とみなしてはいけません。structured result を product の release evidence とともに記録します。

## 16. Completion criteria

Project Docs がこの walkthrough で complete なのは次がすべて true の場合です。

- recipe は `website` のままで、closure は `artifact.website-core` + transitive `foundation.web` を含み Webapp-private artifact contract を含まない
- すべての `scripts/run.py` invocation が immutable Website-capable revision `ca8b8bc9091c6c199224cd9b66c9a59229f1b6ac` を使用した
- routes/site structure/metadata/discovery/viewport/browser identity が実装済み Website を記述し、seed placeholder ではなく `siteName: "Project Docs"` になっている
- actual page/content/navigation と `favicon.svg` など宣言済み browser-identity asset が consumer-owned implementation に存在する
- implementation 前に validated planning checkpoint があり、product checkpoint が transition を閉じている
- required product check と real browser-backed positive/negative evidence が完了している
- implementation evidence は truthful な `product` mode で、すべての Website record が requirement-linked、すべての linked record が release gate を選択し、すべての proof command がその selected gate から実行される
- product checkpoint 後の Composition validation が成功する
- machine-projected `check-release-readiness` action を実際に実行し structured result を記録している
- required deferred proof が silently waived されず `release_readiness` を `not-ready` に保つ

rendering/deployment の曖昧さがある場合は [Website と Web application の選び方](website-webapp-selection.md) に戻ってください。static/dynamic は classifier ではありません。
