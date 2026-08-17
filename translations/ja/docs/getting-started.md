# はじめに

> **参考訳（非正本）:** この文書は `docs/getting-started.md` の日本語訳です。英語版が正本であり、内容に差異がある場合は英語版を優先します。

## 前提

対象はGitリポジトリです。Python 3.11以降とGitが必要です。`uvx` が利用可能な場合は一時環境でCLIを実行し、利用できない場合はブートストラップスクリプトが一時的なPython仮想環境を作成します。

## 推奨: 統合済みブートストラップスキルから導入する

ブートストラップスキルは `TakashiSasaki/templates` の `policy` ブランチ内、`skills/bootstrap-agent-policy/` にあります。レビュー済みfull commit SHAをcheckoutし、installerでエージェントのskill directoryへ配置します。

```bash
python skills/bootstrap-agent-policy/scripts/install.py \
  /path/to/agent-skills/bootstrap-agent-policy
```

スキル自身の `bootstrap-manifest.yml` は実行するtoolchain revisionをfull SHAで固定しています。mutable referenceへ置き換えないでください。

## 1. リポジトリを調査し、導入計画を確認する

```bash
python scripts/bootstrap.py \
  --repository /path/to/product-repository
```

bootstrapは既定でdry-runです。固定toolchainの `agent-policy adopt inspect` で対象を分類します。

- `unmanaged-empty`: fresh adoption
- `unmanaged-existing`: migration adoption
- `managed`: bootstrap不要
- `inconsistent`: 部分導入状態などを先に修復

adoption strategyはinspection結果から決まり、利用者が `init` と `adopt` のrouteを選択する必要はありません。

## 2A. Fresh adoptionを適用する

`unmanaged-empty` ではdry-runを確認後、次のように適用します。

```bash
python scripts/bootstrap.py \
  --repository /path/to/product-repository \
  --apply
```

bootstrapは現在 `agent-policy init` を内部primitiveとして使用し、その後同じ固定toolchainによる `validate` と `check` の成功を要求します。initializationは独立した利用者向け操作ではありません。

主に次のファイルが作成されます。

```text
.agent-policy.yml
.agent-policy.lock
policy/project.md
AGENTS.md
.agents/skills/validate-agent-policy/SKILL.md
```

## 2B. 既存instructionをmigration adoptionする

複数の対応instruction fileが発見された場合はprimary instructionを指定します。

```bash
python scripts/bootstrap.py \
  --repository /path/to/product-repository \
  --primary-instructions AGENTS.md
```

計画確認後に適用します。

```bash
python scripts/bootstrap.py \
  --repository /path/to/product-repository \
  --primary-instructions AGENTS.md \
  --apply
```

既存primary instructionは置き換えられません。`.agent-policy/adoption.json` とshadow preview等を作成し、`adopt preview`まで実行します。手書きinstructionの意味をproject policyへ反映し、previewとの差分をレビューしてください。

cutoverは別段階です。レビュー後に、manifestに固定された同じrepositoryとfull SHAのCLIで `agent-policy adopt finalize` をdry-runし、明示的な `--apply` でprimary instructionを生成物へ切り替えます。generic bootstrap `--apply`はmigration finalizationを実行しません。

## 3. 製品固有規約を記述する

`policy/project.md` に、その製品だけに適用する不変条件、互換性要件、検証方法を記述します。

通常のmanaged stateでは次を実行します。

```bash
agent-policy --repository . validate
agent-policy --repository . render
agent-policy --repository . check
```

migration adoption準備中はproject policy編集後に次を実行します。

```bash
agent-policy --repository . adopt preview
```

## 4. 変更をレビューしてコミットする

fresh adoption、migration preparation、preview、finalization、再生成はGit commitやpushを自動実行しません。生成された差分を通常のレビューフローで確認してください。

!!! note
    ブートストラップスキルは初回導入のtrust seedです。fresh adoption後またはmigration finalization後の通常運用では、製品リポジトリ内の `.agent-policy.yml` と `.agent-policy.lock` がツールチェーンと生成状態を固定します。
