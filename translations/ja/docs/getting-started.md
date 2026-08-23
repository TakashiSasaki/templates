# はじめに

> **参考訳（非正本）:** この文書は `docs/getting-started.md` の日本語訳です。英語版が正本であり、内容に差異がある場合は英語版を優先します。

## 前提

対象はGitリポジトリです。Python 3.11以降とGitが必要です。単一の `agent-policy` skillを一度installし、その後は毎回新しい環境を作るのではなく、検証済みpersistent runtime cacheを再利用します。

## 推奨: 単一agent-policy skillを導入する

installer scriptのURL自体をimmutableなfull commit SHAで固定した公開済みinstallerを使用します。

```bash
python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/TakashiSasaki/templates/f9a3b7698a19bba1d2b7e9debd8a3de41a01b570/scripts/install_agent_policy_skill.py', timeout=30).read())" /path/to/agent-skills/agent-policy
```

既存の `agent-policy` skillを置換する場合だけ `--replace` を追加します。

3種類のfull-SHA identityを意図的に分離します。

- **installer script revision** `f9a3b7698a19bba1d2b7e9debd8a3de41a01b570`: remoteで実行するinstallerを識別します。
- **skill source revision** `b063d78ece8f5a8e9cab2e34093e6989a9a6c783`: installされる `skills/agent-policy/` subtreeを識別します。
- **stable runtime revision**: installed `runtime-manifest.json` 内のfull SHAで、skillがcanonical CLIを実行するときのruntimeを識別します。

`release/skill-installer.json` は最初の2つのidentityを記録します。このcommandは `policy`、tag、短縮SHAを実行しません。

レビュー済みcheckoutから直接installする方法は、repository development用の経路としても利用できます。

```bash
python skills/agent-policy/scripts/install.py \
  /path/to/agent-skills/agent-policy
```

このcommandは、レビュー中checkoutのskill treeをinstallします。そのcheckoutが `release/skill-installer.json` のskill-source revisionと一致しない限り、現在公開されているremote distributionとbyte-for-byteで同一とは限りません。公開distributionを再現することが目的なら、公開済みremote commandを使用します。

`runtime-manifest.json` はstable toolchain revisionをfull SHAで固定し、そのrevisionの `requirements-runtime.lock` をSHA-256で結び付けます。これらのfull SHAを `policy`、tag、短縮SHAなどmutableまたは曖昧なreferenceへ置き換えないでください。

通常のconsumer workflowでは、installed skill directoryから `scripts/bootstrap.py` と `scripts/run.py` を使用します。CLIおよびadoption reference中の直接 `agent-policy ...` exampleはcanonical toolchain CLIを説明するものであり、skillのinstallだけで `agent-policy` executableがglobalな `PATH` にinstallされるわけではありません。

## 1. Repositoryを調査してadoption planを確認する

unmanaged repositoryではbootstrapは既定でdry-runです。installed skill directoryから実行します。

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

`unmanaged-existing` では、`AGENTS.md`、`CLAUDE.md`、`GEMINI.md`、`.github/copilot-instructions.md` のうち対応instruction fileが1件だけ見つかった場合は自動選択します。複数見つかった場合は `--primary-instructions` でauthoritativeなprimaryを指定します。1件も見つからない場合は、まず対応instruction fileを作成してください。policyやskill assetだけをprimary instructionとして選択することはできません。

primaryの明示指定が必要な場合は、まずdry-runを確認します。

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

inspectionで対応instruction fileが1件だけ見つかり自動選択された場合は、`--primary-instructions` を省略します。

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
