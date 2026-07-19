# agent-policy

`agent-policy` は、複数の製品リポジトリと複数のコーディング／汎用エージェントで共有する規約を、検証可能かつ再現可能な形で管理するためのポリシーツールチェーンです。

## 目的

- 共通規約を中央で一度だけ管理する
- 製品固有規約を各リポジトリに保持する
- `.agent-policy.yml` を単一の意味的設定入口にする
- 共通規約と製品固有規約を決定的に合成する
- `AGENTS.md` と通常運用スキルを生成してコミットする
- `.agent-policy.lock` に入力・出力ハッシュとツールチェーンの完全なコミットSHAを記録する
- 設定、ロックファイル、生成物の不整合をCIで検出する

## 構成

このリポジトリには、共通祖先を持たない二つの長期ブランチがあります。

| ブランチ | 役割 |
| --- | --- |
| `main` | 規約ソース、Python CLI、スキーマ、レンダラー、通常運用スキル、テスト、GitHub Actions連携 |
| `bootstrap-agent-policy` | 未導入リポジトリを初期化する、直接clone可能なエージェントスキル |

ブートストラップスキルは、`main` 上の完全な40桁コミットSHAを固定して `agent-policy init` を呼び出します。初期化後は、製品リポジトリ内の `.agent-policy.yml`、`.agent-policy.lock`、生成された指示・スキル、CIへ制御を引き渡します。

## 提供コマンド

```text
agent-policy init
agent-policy validate
agent-policy render
agent-policy check
```

- `init`: 未導入リポジトリの初期化計画を表示し、`--apply` 指定時に適用します。
- `validate`: 設定、参照、規則ID、パス安全性などを検査します。
- `render`: 共通規約と製品固有規約を合成して生成物とロックファイルを更新します。
- `check`: 設定、入力、ロックファイル、生成物が一致しているかを読み取り専用で確認します。

## 次に読むページ

- [はじめに](getting-started.md)
- [Managed repository operation](managed-operation.md)
- [CLIリファレンス](cli.md)
- [ブートストラップスキル](bootstrap.md)
- [アーキテクチャ](architecture.md)
- [脅威モデル](threat-model.md)
