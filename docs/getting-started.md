# はじめに

## 前提

対象はGitリポジトリです。Python 3.11以降とGitが必要です。`uvx` が利用可能な場合は一時環境でCLIを実行し、利用できない場合はブートストラップスクリプトが一時的なPython仮想環境を作成します。

## 推奨: ブートストラップスキルから導入する

`bootstrap-agent-policy` ブランチ全体が、一つの直接clone可能なエージェントスキルです。`SKILL.md` はブランチのルートにあります。

```bash
git clone \
  --branch bootstrap-agent-policy \
  --single-branch \
  https://github.com/TakashiSasaki/agent-policy.git \
  bootstrap-agent-policy
```

エージェントのユーザーレベルのスキルディレクトリへ配置する場合は、最後の引数を実際の配置先に変更してください。

## 1. 初期化計画を確認する

ブートストラップ処理は、既定ではdry-runです。

```bash
python bootstrap-agent-policy/scripts/bootstrap.py \
  --repository /path/to/product-repository
```

次を確認します。

- 対象のGitリポジトリルート
- 使用する `main` の完全なコミットSHA
- 作成予定ファイル
- 既存の手書きファイルとの衝突
- 既に `.agent-policy.yml` が存在しないこと

## 2. 初期化を適用する

計画に問題がなければ `--apply` を付けます。

```bash
python bootstrap-agent-policy/scripts/bootstrap.py \
  --repository /path/to/product-repository \
  --apply
```

初期化後、ブートストラップスクリプトは `validate` と `check` の成功を要求します。

## 3. 生成結果を確認する

初期実装では、主に次のファイルが作成されます。

```text
.agent-policy.yml
.agent-policy.lock
policy/project.md
AGENTS.md
.agents/skills/validate-agent-policy/SKILL.md
.github/workflows/check-agent-policy.yml
```

`.agent-policy.yml` が人間が編集する設定の入口です。`.agent-policy.lock`、`AGENTS.md`、生成されたスキルはCLIが管理します。

## 4. 製品固有規約を記述する

`policy/project.md` に、その製品だけに適用する不変条件、互換性要件、検証方法を記述します。共通規約の正本を製品リポジトリへコピーして編集しないでください。

変更後は次を実行します。

```bash
agent-policy --repository . validate
agent-policy --repository . render
agent-policy --repository . check
```

## 5. 変更をレビューしてコミットする

初期化や再生成はGit commitやpushを自動実行しません。生成された差分を確認し、製品コードと同じ通常のレビューフローでコミットしてください。

!!! note
    ブートストラップスキルは初回導入の信頼の種です。初期化後の通常運用では、製品リポジトリ内の `.agent-policy.yml` と `.agent-policy.lock` がツールチェーンと生成状態を固定します。
