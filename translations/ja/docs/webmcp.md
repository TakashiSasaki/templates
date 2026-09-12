# Website および Web application consumer 向け WebMCP

> **参考訳（非正本）:** この文書は英語正本の参考訳です。内容に差異がある場合は英語正本が優先されます。

これは Composition の任意選択 `capability.webmcp` に関する Site 所有の読者向けガイドです。component selection、contract、schema、validation、および implementation-evidence requirement に関しては **Composition が引き続き semantic authority** であり、このページがそれらの規則を再定義することはありません。

## WebMCP とは何か？

WebMCP は、ページが公開する意味のある product tool を AI 対応ブラウザが発見し、呼び出すことを可能にする browser-context interface です。現在の Composition v1 profile は、imperative な `document.modelContext` API を対象としています。WebMCP は backend の MCP server なしで存在でき、MCP、MCP Apps、runtime、および独立した Web-interface capability とは無関係です。

Website または Web application を選択しても、WebMCP が選択されるわけではありません。WebMCP を選択しても、MCP、MCP Apps、runtime、または独立した Web interface が選択されるわけではありません。

## 採用するべきか？

product に authenticated browser context で agent にとって有用な安定した domain operation があり、それらの operation が human-facing product path と同じ authorization、validation、confirmation、state-transition、および side-effect semantics を共有できる場合に、WebMCP を採用してください。

単に UI control を公開するためだけに採用してはなりません。Tool boundary は、ボタンをクリックするような低レベルな action ではなく、user / domain intent を表現するべきです。

Composition は 3 つの明確な intent を表現します。

| Intent | Composition selection | Meaning |
| --- | --- | --- |
| Default | include と exclude のどちらもしない | 未指定 / default intent |
| Adopt | `capability.webmcp` を include | 明示的な採用 |
| Explicitly exclude | `capability.webmcp` を exclude | 永続的で明示的な不採用 |

現在の recipe がデフォルトで WebMCP を選択しない場合であっても、明示的な不採用は omission (除外/省略) と等価ではありません。

## WebMCP vs MCP

MCP はブラウザページの外で使用できる protocol / interface capability です。WebMCP は browser-context capability です。product はどちらか一方、両方、またはどちらも公開しないことができます。一方の選択は他方を意味しません。

## WebMCP vs MCP Apps

MCP Apps は MCP の周りに application UI / resource semantics を追加します。対して WebMCP は browser context から tool を公開します。どちらの capability を選択しても、他方を意味しません。

## WebMCP vs 通常の Web UI

Human UI は引き続き first-class interface です。Human UI と WebMCP が同じ domain operation に到達する場合、それらは共有の application / domain code に収束するべきです。WebMCP callback が、human UI または API によって強制される規則を迂回する、特権的な代替の実装になってはなりません。

## Security の意味合い

WebMCP execution が product authorization、input validation、required confirmation、state-transition rules、または外部から観測可能な side-effect semantics を迂回してはなりません。authenticated browser session は context を提供しますが、すべての operation に対する十分な authorization ではありません。

prompt injection、tool metadata poisoning、untrusted tool output、sensitive input / output、stale registration、confused-deputy behavior、および Human UI と WebMCP path の divergence を、明示的な trust-boundary の懸念事項として扱ってください。upstream の annotation や hint は interoperability metadata であり、security authority ではありません。

Same-origin / narrow exposure がデフォルトです。Cross-origin exposure は明示的な Composition contract の選択であり、厳格な allowlist、関連する Permissions Policy の処理、そして positive および denied-origin の browser evidence を要求します。

## Imperative および Declarative WebMCP

現在の Composition v1 product profile は `document.modelContext` を通じた **Imperative WebMCP** です。**Declarative WebMCP** は現在の product contract の一部ではなく、引き続き experimental / informative な位置づけです。consumer から見える進化は、消費者が選択する二番目の upstream specification revision ではなく、immutable な Composition revision、component / schema version、migration、および lifecycle evidence を通じて処理されます。

## 選択の確認

Composition Playground は **Default / Adopt / Explicitly exclude** を提示します。Validity、conflict、生成される material / contract、dependency reason、および explainability は、固定された正確な Composition provider projection からもたらされます。Site のブラウザコードが dependency resolver を実装することはありません。

実装作業には、`capability.webmcp` によって提供される provider 所有の `WEBMCP.md`、tool-design、security、testing、machine-contract、および implementation-evidence material を使用してください。
