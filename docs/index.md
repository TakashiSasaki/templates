# agent-policy

`agent-policy` は、複数の製品リポジトリと複数のコーディング／汎用エージェントで共有する規約を、検証可能かつ再現可能な形で管理するためのポリシーツールチェーンです。開発上の正本は `TakashiSasaki/templates` の `policy` ブランチです。

## 目的

- 共通規約を中央で一度だけ管理する
- 製品固有規約を各リポジトリに保持する
- `.agent-policy.yml` を単一の意味的設定入口にする
- 共通規約と製品固有規約を決定的に合成する
- `AGENTS.md` と通常運用スキルを生成してコミットする
- `.agent-policy.lock` に入力・出力ハッシュとツールチェーンの完全なコミットSHAを記録する
- 設定、lock、生成物の不整合をCIで検出する
- 既存instructionを破壊せずに導入準備・preview・明示的cutoverを行う

## `policy`ブランチの構成

`policy`は、`templates`リポジトリの`main`、`site`、`webapp`とはunrelated historyです。このbranch内で次を管理します。

| パス | 役割 |
|---|---|
| `policy/`, `profiles/` | application-type-independentな共有規約と適用集合 |
| `src/agent_policy/` | Python CLIとadoption transaction |
| `schemas/`, `templates/` | consumer設定・stateのschemaと生成template |
| `skills/` | 通常運用skillと統合済み`bootstrap-agent-policy` trust seed |
| `tests/` | compiler、path safety、lock、adoption、bootstrap boundaryの検証 |
| `docs/` | 導入、設計、ADR、publication資産 |

ブートストラップスキルは `skills/bootstrap-agent-policy/` にあります。manifestは `TakashiSasaki/templates` のfull commit SHAを固定してCLIを実行し、mutableな`policy`先端を直接信頼しません。初期化後またはadoption finalization後は、製品リポジトリ内の `.agent-policy.yml`、`.agent-policy.lock`、生成された指示・skill、CIへ制御を引き渡します。

## 提供コマンド

```text
agent-policy init
agent-policy adopt inspect
agent-policy adopt prepare
agent-policy adopt preview
agent-policy adopt finalize
agent-policy validate
agent-policy render
agent-policy check
```

- `init`: 未導入で既存instruction競合のないリポジトリを初期化する
- `adopt`: 既存instructionを保持したまま調査、準備、preview、明示的cutoverを行う
- `validate`: 設定、参照、規則ID、path safetyなどを検査する
- `render`: 共通規約と製品固有規約を合成して生成物とlockを更新する
- `check`: 設定、入力、lock、生成物が一致しているかをread-onlyで確認する

## 次に読むページ

- [はじめに](getting-started.md)
- [Managed repository operation](managed-operation.md)
- [CLIリファレンス](cli.md)
- [ブートストラップスキル](bootstrap.md)
- [既存リポジトリの導入](adoption.md)
- [アーキテクチャ](architecture.md)
- [脅威モデル](threat-model.md)
