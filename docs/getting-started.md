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

## 1. リポジトリを調査し、導入計画を確認する

ブートストラップ処理は、既定ではdry-runです。

```bash
python bootstrap-agent-policy/scripts/bootstrap.py \
  --repository /path/to/product-repository
```

固定された `main` の完全なコミットSHAで `agent-policy adopt inspect` を実行し、対象を次のいずれかへ分類します。

- `unmanaged-empty`: 既存instructionがなく、`init`を使用できる
- `unmanaged-existing`: 既存instructionやpolicyがあり、`adopt prepare`を使用する
- `managed`: `.agent-policy.yml`が存在し、bootstrapは不要
- `inconsistent`: 部分導入、生成物だけの残存、危険なpathなどがあり、先に修復が必要

自動振り分けはdry-runの助言だけです。書込み時には経路を明示します。

## 2A. 空のリポジトリを初期化する

`unmanaged-empty` と判定され、計画に問題がなければ `init` を明示して適用します。

```bash
python bootstrap-agent-policy/scripts/bootstrap.py \
  --repository /path/to/product-repository \
  --route init \
  --apply
```

初期化後、ブートストラップスクリプトは同じ固定ツールチェーンによる `validate` と `check` の成功を要求します。

主に次のファイルが作成されます。

```text
.agent-policy.yml
.agent-policy.lock
policy/project.md
AGENTS.md
.agents/skills/validate-agent-policy/SKILL.md
```

`.agent-policy.yml` が人間が編集する設定の入口です。`.agent-policy.lock`、`AGENTS.md`、生成されたスキルはCLIが管理します。

## 2B. 既存instructionを保持して導入準備する

`unmanaged-existing` と判定された場合は、調査で発見された `AGENTS.md`、`CLAUDE.md`、`GEMINI.md`、または `.github/copilot-instructions.md` からprimary instructionを選択します。

まずdry-runを確認します。

```bash
python bootstrap-agent-policy/scripts/bootstrap.py \
  --repository /path/to/product-repository \
  --route adopt \
  --primary-instructions AGENTS.md
```

計画を確認した後、準備状態を適用します。

```bash
python bootstrap-agent-policy/scripts/bootstrap.py \
  --repository /path/to/product-repository \
  --route adopt \
  --primary-instructions AGENTS.md \
  --apply
```

既存primary instructionは置き換えられません。主に次の準備資産が作成され、`adopt preview`まで実行されます。

```text
.agent-policy.yml
.agent-policy.lock
.agent-policy/adoption.json
.agent-policy/preview/AGENTS.md
policy/project.md
.agents/skills/validate-agent-policy/SKILL.md
```

手書きinstructionの意味をproject policyへ反映し、previewとの意味的な差分をレビューしてください。CLIは自由記述を自動的に規約へ変換しません。

cutoverは別段階です。レビュー後に、同じ固定ツールチェーンの `agent-policy adopt finalize` をdry-runし、明示的に `--apply`して初めてprimary instructionを生成物へ切り替えます。genericなbootstrap `--apply`はfinalizeを実行しません。

## 3. 製品固有規約を記述する

`policy/project.md` に、その製品だけに適用する不変条件、互換性要件、検証方法を記述します。共通規約の正本を製品リポジトリへコピーして編集しないでください。

通常のmanaged stateでは次を実行します。

```bash
agent-policy --repository . validate
agent-policy --repository . render
agent-policy --repository . check
```

adoption準備中は、project policyを編集した後に次を実行してshadow previewを更新します。

```bash
agent-policy --repository . adopt preview
```

## 4. 変更をレビューしてコミットする

初期化、adoption preparation、preview、finalization、再生成はGit commitやpushを自動実行しません。生成された差分を確認し、製品コードと同じ通常のレビューフローでコミットしてください。

!!! note
    ブートストラップスキルは初回導入の信頼の種です。初期化後またはadoption finalization後の通常運用では、製品リポジトリ内の `.agent-policy.yml` と `.agent-policy.lock` がツールチェーンと生成状態を固定します。
