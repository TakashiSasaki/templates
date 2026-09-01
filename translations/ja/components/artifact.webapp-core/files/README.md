# Web application Composition レシピ

> **参考訳（非正本）:** この文書は英語版 `components/artifact.webapp-core/files/README.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

この repository は、`webapp` Composition レシピによって生成される framework-neutral な Web application contract scaffold です。

## Composition が初めてなら worked example から始める

この repository を使って初めて Web application を作る場合は、以下の contracts を最初から読み解くところから始めないでください。別 product repository から [Webapp product walkthrough](https://templates.moukaeritai.work/webapp/product-walkthrough/) を順に進めます。prerequisites と Composition install から始まり、`composition.json` を作成し、`inspect -> plan -> apply -> validate` を実行し、生成後にどの file を編集できるかを具体的に確認した後、product implementation と evidence まで進みます。

walkthrough の最初の milestone は **valid な Composition scaffold** であり、完成した Web application ではありません。product implementation と product verification は引き続き consumer の責任です。

## Webapp recipe が定義するもの

`foundation.web` は browser identity / favicon declaration、一般化された canonical route、responsive viewport / input expectation という必須の shared browser baseline を所有します。`artifact.webapp-core` は application-specific な semantics、すなわち surface、task/action UI state、および各 shared route に付加される application behavior を所有します。generic な contract evolution と implementation evidence は、再利用可能な `lifecycle.*` component を通じて Webapp baseline に含まれます。release execution、release evidence、release bundle の behavior は、consumer が `lifecycle.release-bundle` を明示的に選択した場合だけ追加されます。

この scaffold は、frontend framework、rendering model、package manager、backend、persistence layer、authentication provider、deployment platform、browser matrix、observability vendor を意図的に選択しません。

## Contracts

- `contracts/browser-identity.json` — `foundation.web` 由来。標準的な favicon relationship、primary icon asset、および optional な compatibility fallback。
- `contracts/surfaces.json` — browser-facing な surface boundary と audience。
- `contracts/routes.json` — `foundation.web` 由来。canonical navigation と generic な browser navigation / accessibility semantics。
- `contracts/application-routes.json` — Webapp 固有の route behavior。surface、authentication / access failure、history、state target を宣言します。
- `contracts/ui-states.json` — 再利用可能な visible state と recovery / focus behavior。
- `contracts/viewports.json` — `foundation.web` 由来。responsive lower bound と input capability。
- `contracts/implementation-evidence.json` — Webapp contract target と implementation / proof evidence を対応づける baseline contract。
- `contracts/manifest.json` — 解決済み component metadata から生成される閉じた registry。この Composition registry は Web App Manifest ではありません。
- release execution / evidence / bundle contract は `lifecycle.release-bundle` を選択した場合だけ materialize されます。

browser-identity seed は、単一の scalable asset で軽量かつ解像度非依存にしやすいため SVG favicon を推奨形として示します。ただし contract は、product や compatibility target が必要とする場合に別の image media type を許容します。PWA installability、application icon、offline behavior、update behavior は別の concern であり、favicon contract から暗黙には要求されません。

## Optional capability と release lifecycle

Webapp レシピでは、runtime、CLI、MCP、MCP Apps、standalone operational Web exposure、headless service capability を追加で選択できます。artifact が browser-facing であるという理由だけで、これらが必須になることはありません。static / CDN Web application は application runtime component がなくても妥当です。

Composition-managed release workflow が必要な repository では `lifecycle.release-bundle` を選択します。その dependency closure により release execution と revision-bound release evidence が追加され、baseline の implementation-evidence と contract-evolution component が再利用されます。

## Validation

`python .template-composition/validate.py .` を実行します。validator は managed な Composition validation registry に記録された exact dependency set から isolated validation runtime を自動的に構築・再利用するため、validation environment を手動でインストールする必要はありません。validation は Composition lock の resolved component set から選択されます。minimal Webapp や runtime-backed Webapp では release validator は実行されず、`lifecycle.release-bundle` を選択した release-ready Webapp では実行されます。
