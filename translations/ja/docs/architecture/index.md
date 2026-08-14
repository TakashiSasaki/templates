# Web アプリケーションアーキテクチャ

> **参考訳（非正本）:** この文書は英語正本の日本語参考訳です。内容に差異がある場合は英語正本が優先されます。

## 正本の下流契約モデル

* [契約の完全性](../../template/docs/architecture/contract-completeness.md) - 閉じた契約ファミリー一覧と、その拡張条件を定義します。
* [契約の進化](../../template/docs/architecture/contract-evolution.md) - バージョン履歴、安定した移行所有権、廃止、ロールバック規則を定義します。
* [責務境界](../../template/docs/architecture/responsibility-boundaries.md) - テンプレート、生成製品、運用の所有権を分離します。
* [検証ツールチェーン](../../template/docs/architecture/validation-toolchain.md) - 検証環境、固定依存関係、対応する validator entry point を定義します。

## 正本の下流実装とリリース証跡

* [実装証跡](../../template/docs/architecture/implementation-evidence.md) - surface、route、UI state、viewport、入力能力、migration を肯定・否定の実装証拠へ結び付けます。
* [リリース証跡](../../template/docs/architecture/release-evidence.md) - コマンドと release gate の結果を1つの厳密な製品revisionへ結び付けます。
* [リリースバンドル](../../template/docs/architecture/release-bundle.md) - 承認済みリリース証跡の後に生成される digest-closed な引き渡しバンドルを定義します。

## テンプレート保守と配布

* [完成ロードマップ](completion-roadmap.md) - Webapp テンプレート基盤を完成させるための横断的な完成条件を記録します。
* [配布境界](distribution-boundary.md) - `template/` を唯一の正本の下流ソースツリーとして定義し、ソースメンテナーのアーティファクトから分離します。
* [配布分類](distribution-classification.json) - トップレベルの配布責務とメンテナー責務の機械可読分類を提供します。
* [配布準備状況監査](distribution-readiness-audit.md) - 正本のコピー可能配布境界が完全で内部整合している証拠を記録します。
* [最終準備状況監査](final-readiness-audit.md) - 保守対象テンプレートの最終的な横断準備状況レビューを記録します。
* [生成リポジトリ適合](generated-repository-conformance.md) - テンプレートモードから生成製品モードへのメンテナークリーンルーム遷移を定義し検証します。

## コピー可能なアーキテクチャ

* [利用者向けアーキテクチャ](../../template/docs/architecture/) - コピーされたリポジトリに含まれるアーキテクチャ文書を列挙します。
