# アーキテクチャ決定

> **参考訳（非正本）:** この文書は英語正本の日本語参考訳です。内容に差異がある場合は英語正本が優先されます。

## 現行の決定

* [ADR-0002: リポジトリ導入](0002-repository-adoption.md) - 既存のリポジトリ指示を破壊的に置き換えずに policy ツールチェーンを導入する方法を定義します。
* [ADR-0003: アプリケーション中立のポリシースコープ](0003-application-neutral-policy-scope.md) - 共有ポリシーを、製品アーキテクチャではなくアプリケーション種別に依存しないエージェント運用へ集中させます。
* [ADR-0005: 単一のポリシー権威](0005-single-policy-authority.md) - 単一の正本ポリシー権威を確立し、生成された指示をその権威の投影として扱います。
* [ADR-0006: コピー可能アーティファクトのポリシー導入](0006-copyable-artifact-policy-adoption.md) - コピー可能なテンプレートアーティファクトが、メンテナー専用リポジトリポリシーを取り込まずに共有ポリシーへオプトインする方法を定義します。
* [ADR-0007: 単一 agent-policy Skill と永続 runtime cache](0007-single-agent-policy-skill-runtime-cache.md) - adoption 前後で同じ immutable な repository-facing Skill を使い、検証済み full-SHA runtime を再利用します。
* [ADR-0008: Review authority と GitHub runtime boundary](0008-review-authority-and-github-runtime-boundary.md) - immutable exact-base review authority、trusted bootstrap/runtime provenance、procedure freezing、identity stability、review/merge separation を確立します。result-representation coupling は ADR-0009 により一部置き換えられます。
* [ADR-0009: Review-result representation boundary](0009-review-result-representation-boundary.md) - ADR-0008 の trust machinery を維持しつつ、provider serialization と GitHub request shape を semantic / procedural review authority の外側に置きます。

## 置き換え済みの決定

* [ADR-0004: 統合ブートストラップ Skill](0004-integrated-bootstrap-skill.md) - ADR-0007 によって置き換えられており、以前の bootstrap trust-boundary 設計を説明する歴史的根拠としてのみ保持されています。
