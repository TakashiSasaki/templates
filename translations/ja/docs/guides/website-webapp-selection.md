# Website と Web application の選び方

> **参考訳（非正本）:** この文書は英語版 `docs/guides/website-webapp-selection.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

browser-facing product で `website` と `webapp` のどちらの Composition recipe を使うか判断するときに、このガイドを使用します。

判断基準は **product identity と caller-visible behavior** です。static / dynamic、client-rendered / server-rendered、CDN / application server、使用 framework といった実装技術から artifact を分類しないでください。

## 短い判断基準

主な product model が、利用者が **発見し、移動し、読み、共有する document / content** であるなら **Website** を選びます。

主な product model が、application state、action、transition、recoverable UI state を通じて行う **interactive task** であるなら **Web application** を選びます。

両方を含む場合は、その browser product の identity を定義する挙動から主 artifact を分類します。deployment topology に合わせて artifact identity を変えるのではなく、追加で外部提供する挙動には capability を選択します。

## 判断表

| Product intent | 選択 | 理由 |
| --- | --- | --- |
| documentation、reference、blog、news、marketing、institutional information、content catalog | `website` | page/document structure、metadata、discovery、canonical identity、navigation が product baseline |
| static file として生成する corporate / documentation site | `website` | static generation は deployment/rendering choice であり application identity ではない |
| server-rendered news / publishing site | `website` | server rendering で document-oriented content が application になるわけではない |
| browser inventory manager、task tracker、dashboard、editor、workflow UI、stateful tool | `webapp` | application surface、action、route behavior、visible state、recovery behavior が product を定義する |
| CDN だけから配信する single-page application | `webapp` | static hosting で task/application-state semantics が Website semantics になるわけではない |
| backend を持たない local-storage-only browser tool | `webapp` | Web application identity に runtime/server は必須ではない |
| install して offline で読める documentation site | `website` + `capability.pwa` | PWA は optional cross-cutting capability であり installability は artifact identity を変えない |
| installable な stateful browser application | `webapp` + `capability.pwa` | PWA behavior を追加しても product は Web application のまま |
| maintained server runtime で render する Website | `website` + `capability.runtime` | runtime/deployment は Website identity と直交する |
| maintained runtime を持つ Web application | `webapp` + `capability.runtime` | runtime/deployment は Web application identity と直交する |

## 両 recipe が共有するもの

両 browser artifact は `foundation.web` を推移的に要求します。consumer が foundation を直接選択することはありません。

shared foundation は、browser identity、generalized route identity/canonical path/alias/deep-link/accessibility、viewport と input-capability expectation を所有します。これらの共通 contract は、product が Website か Web application かを決定しません。

## Website identity

`website` recipe は `artifact.website-core` を選択します。

- `site_structure` — page identity、page hierarchy、home page、primary navigation、shared route への binding
- `document_metadata` — page title、description、indexability、canonical-path policy、social-preview intent
- `site_discovery` — canonical origin、robots policy、sitemap coverage、discovery feed

Website は JavaScript、runtime、別 system の authentication、client-side navigation を使うという理由だけで Webapp-private な `application_routes`、`surfaces`、`ui_states` を受け取りません。

## Web application identity

`webapp` recipe は `artifact.webapp-core` を選択し、同じ shared Web foundation の上に application surface、application-route binding、authentication/access-failure/history behavior、visible UI state と recovery/announcement/focus semantics を追加します。

application behavior 自体が supported browser product contract の一部なら、これらの contract を使います。

## PWA は artifact を決めない

`capability.pwa` は artifact-neutral です。Web App Manifest、home-screen install、service worker、offline behavior、application icon、update lifecycle の有無だけから `webapp` と判断してはいけません。

content-oriented documentation Website も PWA にできます。stateful browser application も PWA にできます。artifact は **browser product が何であるか** に答え、PWA は **追加で何をできるか** に答えます。

## Runtime と deployment も artifact を決めない

次はすべて有効な組合せです。

```text
static Website
server-rendered Website
PWA Website
runtime-backed Website
CDN-hosted Web application
local-only Web application
PWA Web application
runtime-backed Web application
```

`capability.runtime`、`capability.web-interface`、service interface、release lifecycle component は、それぞれ自身の caller-visible / lifecycle contract が適用される場合だけ選択します。

## Mixed product

一方が主で他方が incidental なら主 artifact を選びます。Website と application が独立して support され、異なる lifecycle/contract need を持つなら、別 product artifact/repository または明示的な composition boundary として model します。shared origin、framework、process、deployment、navigation chrome だけでは1 artifact とする根拠になりません。

## 簡単な例

**`website`:** project documentation、大学の部局 site、企業 site、blog、news publication、API reference site、static knowledge base、server-rendered article archive。

**`webapp`:** inventory manager、issue tracker、form workflow、administrative dashboard、visual editor、scheduling tool、authenticated task application、browser IDE。

PWA を追加しても artifact identity は変わりません。

## apply 前に選択を確認する

machine authority は recipe descriptor です。`apply` の前に `plan` を使い、resolved closure を確認します。

最小 Website には `artifact.website-core` と transitive な `foundation.web` が含まれ、`artifact.webapp-core` は含まれません。最小 Web application では逆です。`capability.pwa` や `capability.runtime` を追加しても artifact identity は切り替わりません。

正確な recipe/component availability は [production catalog guide](../../catalog/README.md) を、component-role mental model は [Composition concepts](composition-concepts.md) を参照してください。
