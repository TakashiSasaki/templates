# CLI

## 共通形式

```bash
agent-policy [--repository PATH] [--format text|json] COMMAND [OPTIONS]
```

`--repository` と `--format` はサブコマンドより前に指定します。`--repository` を省略すると、現在位置からGitリポジトリルートを探索します。

## `init`

未導入かつ既存規約を持たないリポジトリの初期化計画を作成します。既定ではファイルを書き換えません。既存instructionを保持しながら導入する場合は、後続の`adopt`機能を使用し、`init`で競合を回避しないでください。

```bash
agent-policy --repository /path/to/repository init
```

適用する場合は `--apply` を指定します。

```bash
agent-policy --repository /path/to/repository init \
  --toolchain-revision <FULL_COMMIT_SHA> \
  --profile core \
  --profile security-baseline \
  --verification-command "npm run verify:pr" \
  --apply
```

主なオプション:

| オプション | 説明 |
| --- | --- |
| `--config PATH` | 設定ファイルのパス。既定は `.agent-policy.yml` |
| `--apply` | 計画を実際に適用する |
| `--toolchain-revision SHA` | 設定とロックへ記録するツールチェーンの完全なコミットSHA |
| `--profile NAME` | 初期プロファイル。複数指定可能 |
| `--project-policy PATH` | 作成する単一のproject policy scaffold。既定は `policy/project.md` |
| `--verification-command COMMAND` | 生成指示へ記載する検証コマンド。既定は `./scripts/verify.sh` |
| `--no-verification` | `verification` セクションを初期設定へ含めない |
| `--agents-output-path PATH` | agent instructionの生成先。既定は `AGENTS.md` |
| `--disable-agents-output` | agent instruction生成を初期設定で無効にする。pathは将来の有効化に備えて保持される |
| `--skill NAME` | 初期状態で生成するskill。複数指定可能。省略時は `validate-agent-policy` |

プロファイルを省略した場合は `core` と `security-baseline` が選択されます。`init`はplaceholder rule IDの重複を避けるため、project policy scaffoldを一つだけ作成します。複数の既存project policyを保持する導入は`adopt prepare`の責務です。

既存挙動との互換性のため、verificationを指定しない場合は`./scripts/verify.sh`が設定されます。そのコマンドを持たないリポジトリでは、実際の検証コマンドを明示するか、`--no-verification`を指定します。

## `validate`

設定ファイルと参照対象の整合性を検査します。

```bash
agent-policy --repository . validate
agent-policy --repository . validate --config .agent-policy.yml
```

検査対象には、YAML／スキーマ、未知のキー、プロファイル、規約ファイル、規則ID、override、入力・出力パスの安全性が含まれます。

## `render`

共通規約と製品固有規約を合成し、生成物と `.agent-policy.lock` を更新します。

```bash
agent-policy --repository . render
```

生成物は直接編集せず、入力規約または `.agent-policy.yml` を変更して再生成します。

## `check`

設定、入力、ロックファイル、生成物が一致しているかを読み取り専用で確認します。

```bash
agent-policy --repository . check
```

CIではこのコマンドを使い、規約変更後の再生成漏れや生成物の手動改変を検出します。

## JSON出力

エージェントやCIから診断を処理する場合は、共通オプションの `--format json` を使います。

```bash
agent-policy --repository . --format json validate
```

終了コードは、エラー診断が一件以上あれば非ゼロになります。
