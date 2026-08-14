# Web アプリケーションアーキテクチャ

> **参考訳（非正本）:** この文書は英語正本の日本語参考訳です。内容に差異がある場合は英語正本が優先されます。

## 契約モデル

* [契約の完全性](contract-completeness.md) - 閉じた契約ファミリー一覧と、その拡張条件を定義します。
* [契約の進化](contract-evolution.md) - バージョン履歴、安定した移行所有権、廃止、ロールバック規則を定義します。
* [責務境界](responsibility-boundaries.md) - テンプレート、生成製品、運用の所有権を分離します。
* [検証ツールチェーン](validation-toolchain.md) - 検証環境、固定依存関係、対応する validator entry point を定義します。

## 実装とリリース証跡

* [実装証跡](implementation-evidence.md) - 実装対象を肯定・否定の証拠と release gate へ結び付けます。
* [リリース証跡](release-evidence.md) - コマンドと release gate の結果を1つの厳密な製品revisionへ結び付けます。
* [リリースバンドル](release-bundle.md) - 承認済みリリース証跡の後に生成される digest-closed な引き渡しバンドルを定義します。
