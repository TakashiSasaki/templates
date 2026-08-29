# アプリケーション capability

> **参考訳（非正本）:** このページは英語正本の参考訳です。内容に差異がある場合は英語正本が優先されます。

これは、再利用可能なアプリケーション capability のための Site 所有の読者向けインデックスです。canonical な capability の意味論とソース文書は `composition` provider が所有します。このページは、安定した `/capabilities/` の読者向け入口を提供し、公開先をグループ化するだけです。

これらの component が composition にどのように参加するかについて Composition レベルの説明を読むには、[Composition documentation index](/composition/docs/#reusable-application-capabilities) を参照してください。

## 実装ランタイム

アプリケーションをどのように実装し実行するかを定義します。言語 / runtime、dependency workflow、command、environment、distribution、deployment の選択が含まれます。

- [Implementation runtime decision record](/capabilities/runtime/)
- [Choosing an implementation runtime](/capabilities/runtime/selection/)

## インターフェース

ユーザー、エージェント、ブラウザ、その他のシステムがアプリケーションとどのようにやり取りするかを定義します。interface contract は、上記の implementation-runtime の選択とは分離して caller-visible behavior を記述します。

- [Packaged CLI interface](/capabilities/cli/)
- [MCP interface](/capabilities/mcp/)
- [MCP transports](/capabilities/mcp/transports/)
- [MCP Apps interface](/capabilities/mcp-apps/)
- [MCP Apps guidance](/capabilities/mcp-apps/guidance/)
- [Standalone browser interface](/capabilities/browser/)
- [Headless service interface](/capabilities/service/)

## Web アプリケーションのブラウザ体験

Web アプリケーションにはブラウザ上の identity があり、必要に応じて PWA behavior を選択できます。Site はどちらの contract family も再定義せず、Composition が所有する正本への読者向け導線だけを提供します。

- [Browser identity and favicon](/webapp/docs/architecture/contracts/) — Webapp contract family の reference には通常のブラウザ favicon が含まれ、installed application icon とは別の identity concern として扱われます。
- [Progressive Web App capability](/capabilities/pwa/) — PWA decision record は、installability、application icon、offline / network-loss presentation、data freshness、update、cross-platform compatibility に関する正本をまとめています。

ブラウザや OS によって実現機構は異なり得ます。現在のブラウザの install prompt や platform 固有の表示を Site の authority とみなさず、product invariant と evidence boundary については Composition の正本に従ってください。

上記の公開 path は Site の publication destination です。build artifact 内での provenance は、`build-provenance.json` に記録された正確な Composition revision に解決されます。
