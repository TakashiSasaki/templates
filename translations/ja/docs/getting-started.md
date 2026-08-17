# はじめに

> **参考訳（非正本）:** この文書は `docs/getting-started.md` の日本語訳です。英語版が正本であり、内容に差異がある場合は英語版を優先します。

## 前提

対象はGitリポジトリです。Python 3.11以降とGitが必要です。単一の `agent-policy` skillを一度installし、その後は毎回新しい環境を作るのではなく、検証済みpersistent runtime cacheを再利用します。

## 推奨: 単一agent-policy skillを導入する

skillは `TakashiSasaki/templates` の `policy` ブランチ内、`skills/agent-policy/` にあります。レビュー済みcheckoutからエージェントのskill directoryへinstallします。

```bash
python skills/agent-policy/scripts/install.py \
  /path/to/agent-skills/agent-policy
```

`runtime-manifest.json` はstable toolchain revisionをfull SHAで固定し、そのrevisionの `requirements-runtime.lock` をSHA-256で結び付けます。full SHAを `policy`、tag、短縮SHAなどmutableまたは曖昧なreferenceへ置き換えないでください。

## 1. Repositoryを調査してadoption planを確認する

unmanaged repositoryではbootstrapは既定でdry-runです。

```bash
python scripts/bootstrap.py \
  --repository /path/to/product-repository
```

pinned cached runtimeの `agent-policy adopt inspect` により次のいずれかへ分類します。

- `unmanaged-empty`: fresh adoption
- `unmanaged-existing`: migration adoption
- `managed`: 既にmanaged stateなので `scripts/run.py` を使用
- `inconsistent`: 部分導入、orphaned generated artifact、unsafe pathなどを先に修復

adoption strategyはinspection結果から決まり、利用者が `init` と `adopt` のrouteを選ぶ必要はありません。

## 2A. Fresh adoptionを適用する

`unmanaged-empty` ではdry-run確認後に適用します。

```bash
python scripts/bootstrap.py \
  --repository /path/to/product-repository \
  --apply
```

pinned toolchainは `agent-policy init` を内部primitiveとして使用できます。その後、同じruntimeで `validate` と `check` の成功を要求します。initializationは独立した利用者向け操作ではありません。

主に次のファイルが作成されます。

```text
.agent-policy.yml
.agent-policy.lock
policy/project.md
AGENTS.md
.agents/skills/validate-agent-policy/SKILL.md
```

`.agent-policy.yml` は人間が編集するconfiguration entry pointです。`.agent-policy.lock`、`AGENTS.md`、generated skillsはCLIが管理します。

## 2B. 既存instructionをpreserveしたままmigration adoptionする

複数の対応instruction fileが見つかった場合はprimary instructionを指定します。

```bash
python scripts/bootstrap.py \
  --repository /path/to/product-repository \
  --primary-instructions AGENTS.md
```

計画確認後に準備状態を適用します。

```bash
python scripts/bootstrap.py \
  --repository /path/to/product-repository \
  --primary-instructions AGENTS.md \
  --apply
```

既存primary instructionは置き換えません。prepared adoption stateを作成し、`adopt preview` まで実行します。手書きinstructionのsemanticsをproject policyへ反映し、previewとの差分をレビューしてください。

cutoverは別段階です。同じinstalled skillとrepository-pinned toolchainを使います。

```bash
python scripts/run.py \
  --repository /path/to/product-repository \
  adopt finalize
```

このdry-runを確認後、明示的に `--apply` を追加します。generic bootstrap `--apply` はmigration finalizationを実行できません。

## 3. Managed repositoryを運用する

`.agent-policy.lock` が存在した後は `scripts/run.py` を使用します。runnerはskill defaultよりrepository自身のfull SHAを優先します。

```bash
python scripts/run.py --repository . validate
python scripts/run.py --repository . render
python scripts/run.py --repository . check
```

migration preparation中のpreview更新は次のとおりです。

```bash
python scripts/run.py --repository . adopt preview
```

`.agent-policy.lock` のtoolchain pinがmalformedまたはmutableならfail closedします。stable defaultへのsilent fallbackは行いません。

## 4. Runtime cacheの動作

runtime cache identityにはfull toolchain SHA、runtime-lock SHA-256、Python major/minor、platformを含めます。validなcache entryはnetworkなしで再利用できます。

stable defaultでは `runtime-manifest.json` にlock digestがあるため、network access前にcache identityを判定できます。managed repositoryが別のfull SHAを選択した場合でも、同じrevision/Python/platformの検証済みcacheがあればoffline reuseできます。なければそのrevisionのruntime lockを一度取得し、digestを計算して新しいstaged runtimeを構築します。

## 5. Policyを記述し、レビューしてcommitする

`policy/project.md` には、その製品だけに適用するinvariant、compatibility requirement、verification methodを記述します。canonical shared policyを製品repositoryへコピーして編集しないでください。

fresh adoption、migration preparation、preview、finalization、regenerationはGit commitやpushを自動実行しません。生成差分を通常のレビューフローで確認してください。

!!! note
    adoption前後で同じ `agent-policy` skillを使用します。adoption前はレビュー済みruntime manifestがdefault trust seedであり、adoption後は `.agent-policy.lock` がmanaged repositoryのtoolchain revisionについてauthoritativeになります。
