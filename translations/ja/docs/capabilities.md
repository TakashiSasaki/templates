# 再利用可能な capability

> **参考訳（非正本）:** このページは英語正本の参考訳です。内容に差異がある場合は英語正本が優先されます。

これは、再利用可能な capability のための Site 所有の読者向けインデックスです。canonical な capability の意味論とソース文書は `composition` provider が所有します。このページは、安定した `/capabilities/` の読者向け入口を提供し、公開先をグループ化するだけです。

artifact identity は別の判断です。browser product は caller-visible な product model に基づいて `website` または `webapp` を選び、runtime、PWA、standalone interface などの optional capability は、それぞれの挙動が実際に必要な場合だけ選択します。browser artifact をまだ決めていない場合は [Website と Web application の選び方](/web/) から始めます。

component role と dependency closure の Composition レベルの説明は [Composition concepts](/composition/concepts/) を参照してください。

## 実装ランタイム

product をどのように実装し実行するかを定義します。言語 / runtime、dependency workflow、command、environment、distribution、deployment の選択が含まれます。runtime の選択は browser product が Website か Web application かを決めません。

- [Implementation runtime decision record](/capabilities/runtime/)
- [Choosing an implementation runtime](/capabilities/runtime/selection/)

## インターフェース

ユーザー、エージェント、ブラウザ、その他のシステムが product とどのようにやり取りするかを定義します。interface contract は artifact identity や上記の implementation-runtime の選択とは分離して caller-visible behavior を記述します。

- [Packaged CLI interface](/capabilities/cli/)
- [MCP interface](/capabilities/mcp/)
- [MCP transports](/capabilities/mcp/transports/)
- [MCP Apps interface](/capabilities/mcp-apps/)
- [MCP Apps guidance](/capabilities/mcp-apps/guidance/)
- [Standalone browser interface](/capabilities/browser/)
- [Headless service interface](/capabilities/service/)

## Browser product

Website と Web application は sibling artifact identity です。どちらも shared `foundation.web` browser baseline を推移的に受け取り、consumer がその foundation を optional capability として直接選択することはありません。shared baseline は browser identity、generalized routes、viewport expectations を所有します。

- [Website と Web application の選び方](/web/) — static/dynamic rendering、hosting、runtime ではなく product identity から browser artifact を選択します。
- [Website](/website/) — content/document-oriented browser product。
- [Web application](/webapp/) — task/state/action-oriented browser product。
- [Progressive Web App capability](/capabilities/pwa/) — installability、offline/freshness、platform application identity、update behavior が supported product contract に含まれる場合に Website / Web application のどちらにも追加できる optional capability。

別の [Policy PWA usage guide](/policy/pwa/) は、Policy documentation site 自体の install と利用方法を説明する文書です。再利用可能な PWA capability の authority ではありません。

ブラウザや OS によって実現機構は異なり得ます。現在のブラウザの install prompt や platform 固有の表示を Site の authority とみなさず、product invariant と evidence boundary については Composition の正本に従ってください。

上記の公開 path は Site の publication destination です。build artifact 内での provenance は、`build-provenance.json` に記録された正確な Composition revision に解決されます。
