# Web アプリケーションテンプレートのドキュメント

> **参考訳（非正本）:** この文書は英語正本の日本語参考訳です。内容に差異がある場合は英語正本が優先されます。

## 正本の下流運用

* [運用化](../template/docs/operationalization.md) - 生成されたリポジトリがテンプレート宣言から製品所有の実装とリリース証跡へ移行する方法を定義します。

## アーキテクチャと契約

* [メンテナー向けアーキテクチャ](architecture/) - テンプレートメンテナー向けの配布、準備状況、クリーンルーム適合、完成に関するドキュメントをまとめます。
* [利用者向けアーキテクチャ](../template/docs/architecture/) - 下流リポジトリへコピーされる契約モデル、証跡、リリース、責務、検証のドキュメントをまとめます。

## 正本の契約移行

* [Contract manifest v1 から v2](../template/docs/migrations/contract-manifest-v1-to-v2.md) - manifest を完全なファミリー履歴と移行所有権へ移行します。
* [Routes v1 から v2](../template/docs/migrations/routes-v1-to-v2.md) - routes 契約を version 1 から version 2 へ移行します。
* [UI states v1 から v2](../template/docs/migrations/ui-states-v1-to-v2.md) - UI states 契約を version 1 から version 2 へ移行します。

## 公開保守

* [公開カタログ](publication-catalog.md) - 履歴が独立した `site` 公開ブランチへ出力される Webapp 資料を説明します。
* [公開カタログデータ](publication-catalog.json) - 公開組み立てパイプラインが使用するソース一覧を提供します。

## コピー可能なドキュメント

* [利用者向けドキュメント](../template/docs/) - `template/` からコピーされるリポジトリに属するドキュメントを列挙します。
