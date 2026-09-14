# アーキテクチャ決定

> **参考訳（非正本）:** この文書は英語正本の日本語参考訳です。内容に差異がある場合は英語正本が優先されます。

## 現行の決定

ADR-0008 は信頼と来歴について現行であり、レビュー結果の表現については ADR-0009 により一部が置き換えられています。以下のリポジトリソースリンクは、読者向け公開を後続作業としたまま既存の決定を参照可能にします。[メンテナー公開ソース](../publication-catalog.md#deferred-maintainer-publications) を参照してください。

* [ADR-0002: リポジトリ導入](0002-repository-adoption.md) - 既存のリポジトリ指示を破壊的に置き換えずに policy ツールチェーンを導入する方法を定義します。
* [ADR-0003: アプリケーション中立のポリシースコープ](0003-application-neutral-policy-scope.md) - 共有ポリシーを、製品アーキテクチャではなくアプリケーション種別に依存しないエージェント運用へ集中させます。
* [ADR-0005: 単一のポリシー権威](0005-single-policy-authority.md) - 単一の正本ポリシー権威を確立し、生成された指示をその権威の投影として扱います。
* [ADR-0006: コピー可能アーティファクトのポリシー導入](0006-copyable-artifact-policy-adoption.md) - コピー可能なテンプレートアーティファクトが、メンテナー専用リポジトリポリシーを取り込まずに共有ポリシーへオプトインする方法を定義します。
* [ADR-0007: 単一 agent-policy Skill と永続 runtime cache](0007-single-agent-policy-skill-runtime-cache.md) - adoption 前後で同じ immutable な repository-facing Skill を使い、検証済み full-SHA runtime を再利用します。

* [ADR-0008: レビュー権威と GitHub ランタイムの境界（リポジトリソース、一部置き換え済み）](https://github.com/TakashiSasaki/templates/blob/policy/docs/adr/0008-review-authority-and-github-runtime-boundary.md) - 信頼されたレビューのブートストラップ、来歴、GitHub ランタイム境界を保持します。置き換えられた表現要件は ADR-0009 を参照してください。
* [ADR-0009: レビュー結果表現の境界（リポジトリソース）](https://github.com/TakashiSasaki/templates/blob/policy/docs/adr/0009-review-result-representation-boundary.md) - 識別子に結び付いた完了ハンドオフを保持しつつ、表現をレビュー権威の外に置きます。ADR-0008 を部分的に置き換えます。

## 置き換え済みの決定

* [ADR-0004: 統合ブートストラップ Skill](0004-integrated-bootstrap-skill.md) - ADR-0007 によって置き換えられており、以前の bootstrap trust-boundary 設計を説明する歴史的根拠としてのみ保持されています。
