# アーキテクチャ決定

> **参考訳（非正本）:** この文書は英語正本の日本語参考訳です。内容に差異がある場合は英語正本が優先されます。

## 決定

* [ADR-0002: リポジトリ導入](0002-repository-adoption.md) - 既存のリポジトリ指示を破壊的に置き換えずに policy ツールチェーンを導入する方法を定義します。
* [ADR-0003: アプリケーション中立のポリシースコープ](0003-application-neutral-policy-scope.md) - 共有ポリシーを、製品アーキテクチャではなくアプリケーション種別に依存しないエージェント運用へ集中させます。
* [ADR-0004: 統合ブートストラップ Skill](0004-integrated-bootstrap-skill.md) - 独立bootstrap skillの歴史的決定。ADR-0007によって置き換えられています。
* [ADR-0005: 単一のポリシー権威](0005-single-policy-authority.md) - 単一の正本ポリシー権威を確立し、生成された指示をその権威の投影として扱います。
* [ADR-0006: コピー可能アーティファクトのポリシー導入](0006-copyable-artifact-policy-adoption.md) - コピー可能なテンプレートアーティファクトが、メンテナー専用リポジトリポリシーを取り込まずに共有ポリシーへオプトインする方法を定義します。
* [ADR-0007: 単一agent-policy skillとpersistent runtime cache](0007-single-agent-policy-skill-runtime-cache.md) - adoption前後で同じimmutableなrepository-facing skillを使い、検証済みfull-SHA runtimeを再利用します。
