# Web application Composition レシピ

> **参考訳（非正本）:** この文書は英語版 `components/artifact.webapp-core/files/README.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

この repository は、`webapp` Composition レシピによって生成される framework-neutral な Web application contract scaffold です。

`artifact.webapp-core` は browser-specific な semantics を所有します。対象は surface、canonical route、visible UI state、responsive viewport / input capability、およびそれらの cross-contract validation です。generic な contract evolution、implementation evidence、release evidence、release bundle の behavior は、再利用可能な `lifecycle.*` component から提供されます。

この scaffold は、frontend framework、rendering model、package manager、backend、persistence layer、authentication provider、deployment platform、browser matrix、observability vendor を意図的に選択しません。

## Contracts

- `contracts/surfaces.json` — browser-facing な surface boundary と audience。
- `contracts/routes.json` — canonical navigation に加え、access failure の behavior と semantic な state / route target。
- `contracts/ui-states.json` — 再利用可能な visible state と recovery / focus behavior。
- `contracts/viewports.json` — responsive lower bound と input capability。
- `contracts/manifest.json` — 解決済み component metadata から生成される閉じた registry。
- Webapp は release lifecycle chain を必要とするため、lifecycle contract も materialize されます。

## Optional application capabilities

Webapp レシピでは、runtime、CLI、MCP、MCP Apps、standalone operational Web exposure、headless service capability を追加で選択できます。artifact が browser-facing であるという理由だけで、これらが必須になることはありません。static / CDN Web application は application runtime component がなくても妥当です。

## Validation

`.template-composition/requirements-validation.lock` をインストールしたうえで、Webapp validator と lifecycle validator を実行します。付属の GitHub Actions workflow が template mode の完全な validation sequence を実行します。
