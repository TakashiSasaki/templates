# Skill テンプレートのドキュメント

> **参考訳（非正本）:** この文書は英語正本の日本語参考訳です。内容に差異がある場合は英語正本が優先されます。

## Skill の中核モデル

* [アーキテクチャ](architecture.md) - 生成される Skill リポジトリ全体の構造と責務境界を定義します。
* [Skill プロファイル](skill-profiles.md) - 対応する能力プロファイルと、拡張機能の有効化を含む合成規則を定義します。
* [プロファイル契約マップ](profile-contract-map.md) - プロファイルと選択された MCP 拡張を、必要な契約面へ対応付けます。
* [ランタイム選択](runtime-selection.md) - テンプレートを特定ランタイム専用にせず、ランタイム選択を記録する方法を定義します。
* [MCP トランスポート](mcp-transports.md) - MCP インターフェースを公開する Skill の中核トランスポート選択と境界を定義します。
* [MCP Apps](mcp-apps.md) - 任意の `io.modelcontextprotocol/ui` 拡張に対する実装ガイダンスを定義します。

## トップレベル契約

* [SKILL.md](../SKILL.md) - 主要な Skill 契約と利用開始点を提供します。
* [INTERFACES.md](../INTERFACES.md) - 対応するインターフェース契約間の責務を振り分けます。
* [RUNTIME.md](../RUNTIME.md) - ランタイム要件、中核 MCP revision、選択した MCP 拡張識別子を記録します。
* [CLI インターフェース](../CLI_INTERFACE.md) - 存在する場合のパッケージ化されたコマンドラインインターフェースを定義します。
* [MCP インターフェース](../MCP_INTERFACE.md) - 存在する場合の中核 MCP 挙動を定義します。
* [MCP Apps インターフェース](../MCP_APPS.md) - `io.modelcontextprotocol/ui` が選択されている場合の Apps 拡張の挙動を定義します。
* [Web インターフェース](../WEB_INTERFACE.md) - 存在する場合の独立した人間向けブラウザインターフェースを定義します。
