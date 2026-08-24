# ブートストラップ操作

> **参考訳（非正本）:** この文書は `docs/bootstrap.md` の日本語訳です。英語版が正本であり、内容に差異がある場合は英語版を優先します。

## 役割

bootstrapは単一の `skills/agent-policy/` skillが提供するunmanaged repository向け操作です。空のリポジトリにはfresh adoption、既存の手書き指示があるリポジトリにはmigration adoptionを使用します。独立したbootstrap skillはありません。

skillはmutableな`policy`ブランチ先端を実行しません。`runtime-manifest.json` が `TakashiSasaki/templates` のレビュー済みfull commit SHAと、そのrevisionの `requirements-runtime.lock` のSHA-256を固定します。bootstrapとmanaged operationは同じpersistent runtime cacheを共有します。

## 公開済みskillをinstallする

remote installでは、installer script自体をfull SHAで固定したURLから実行します。

```bash
python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/TakashiSasaki/templates/b330f517ad2a348fafc7cb9f690b4df298ee24f4/scripts/install_agent_policy_skill.py', timeout=30).read())" /path/to/agent-skills/agent-policy
```

既存の `agent-policy` skillを置換する場合だけ `--replace` を追加します。

配布では3種類のrevisionを明確に分離します。

- **installer script revision** `b330f517ad2a348fafc7cb9f690b4df298ee24f4`: remoteで実行するbootstrap scriptを固定します。
- **skill source revision** `1656a0a18076dcb90d5ccadc0c6271fb557fe2a7`: installerが取得する `skills/agent-policy/` subtreeを固定します。
- **stable runtime revision**: `runtime-manifest.json` 内の独立したfull SHAで、install後にcanonical CLIを実行するruntimeを固定します。

`release/skill-installer.json` は最初の2つのidentityを公開します。commandもremote installerもmutableな `policy` branch、tag、短縮SHAを実行しません。

レビュー済みcheckoutから、そのcheckoutのskill treeを直接installする方法も利用できます。

```bash
python skills/agent-policy/scripts/install.py \
  /path/to/agent-skills/agent-policy
```

`--replace` は同じidentityの既存skillを置き換える場合だけ使用します。local installerはsymlink target、source/destinationの重複、`SKILL.md` が `agent-policy` を示さないdirectoryの置換を拒否します。

local-checkout経路はrepository developmentとreview用です。そのcheckoutが `release/skill-installer.json` のskill-source revisionと一致しない限り、現在公開されているremote distributionとbyte-for-byteで同一とは限りません。公開distributionを再現する必要がある場合は公開済みremote installerを使用します。

## Skillの内容

```text
skills/agent-policy/
  SKILL.md
  README.md
  runtime-manifest.json
  scripts/
    bootstrap.py
    install.py
    run.py
    runtime.py
    uninstall.py
```

`runtime.py` はimmutable toolchainの選択、persistent runtime cacheの構築・再利用、installed distribution setの検証を担当します。`bootstrap.py` は未導入repositoryを扱い、`run.py` は `.agent-policy.lock` に基づくmanaged operationを扱います。

通常のconsumer entry pointはinstalled `scripts/bootstrap.py` と `scripts/run.py` です。CLIおよびadoption reference中の直接 `agent-policy ...` commandはcanonical toolchain CLIを説明するものです。skillのinstallだけで `agent-policy` executableがglobalな `PATH` にinstallされるわけではありません。

## Repository inspectionとdry-run

installed skill directoryから実行します。

```bash
python scripts/bootstrap.py --repository /path/to/product
```

既定では変更しません。pinned runtimeで `agent-policy adopt inspect` を実行し、状態からstrategyを選びます。

| 状態 | Adoption strategy |
|---|---|
| `unmanaged-empty` | fresh adoption |
| `unmanaged-existing` | migration adoption |
| `managed` | bootstrapを停止して `scripts/run.py` を使用 |
| `inconsistent` | 変更せず、部分導入状態やunsafe pathを先に修復 |

利用者が `init` routeを選択する必要はありません。

## Fresh adoptionを適用する

`unmanaged-empty` ではdry-run確認後に `--apply` を追加します。

```bash
python scripts/bootstrap.py \
  --repository /path/to/product \
  --apply
```

pinned toolchainは `agent-policy init` をfresh-adoption用の内部primitiveとして使用できます。適用後は同じruntimeで `validate` と `check` を実行します。initializationは独立した利用者向け操作ではありません。

## 既存指示をmigration adoptionする

inspectionで対応instruction fileが1件だけ見つかった場合はbootstrapが自動選択します。複数見つかった場合はauthoritativeなprimary sourceを明示的に選択します。1件も見つからない場合は、まず対応する `AGENTS.md`、`CLAUDE.md`、`GEMINI.md`、または `.github/copilot-instructions.md` を作成してください。policyやskill assetだけをprimary instructionとして選択することはできません。

primaryの明示指定が必要な場合:

```bash
python scripts/bootstrap.py \
  --repository /path/to/product \
  --primary-instructions AGENTS.md
```

計画確認後、準備状態を作成する場合だけ `--apply` を追加します。

```bash
python scripts/bootstrap.py \
  --repository /path/to/product \
  --primary-instructions AGENTS.md \
  --apply
```

inspectionで対応instruction fileが1件だけ見つかり自動選択された場合は `--primary-instructions` を省略します。

migration preparation後に `adopt preview` を実行し、既存primary instructionは置き換えません。

finalizationはレビュー後の別の明示的managed operationです。

```bash
python scripts/run.py \
  --repository /path/to/product \
  adopt finalize --apply
```

`runtime-manifest.json` と `bootstrap.py` はfinalize routeを公開しません。したがってgeneric bootstrap `--apply` はmigrationをfinalizeできません。

## Persistent runtimeとmanaged operation

初回adoptionでは `runtime-manifest.json` のstable default full SHAを使用します。`.agent-policy.lock` が存在するmanaged repositoryでは `scripts/run.py` がrepository自身のfull-SHA pinを優先します。malformed、mutable、unsupportedなpinはdefaultへfallbackせずfail closedします。

runtime identityにはrepository、full revision、runtime-lock SHA-256、Python major/minor、platformを含めます。validなcache hitはnetworkなしで再利用できます。cacheはstaging areaで構築・検証し、`pip check` とexact installed-set verification成功後だけ正式位置へ切り替えます。

## 信頼境界

`release/skill-installer.json`、full-SHA remote installer、`SKILL.md`、`runtime-manifest.json`、`scripts/runtime.py`、`scripts/bootstrap.py`、`scripts/run.py`、installer/uninstaller、およびsingle-skill/installer-publication/release testsを一組のtrust boundaryとしてレビューします。

adoption後も同じskillがrepository-facing entry pointです。managed toolchain revisionのauthorityは `.agent-policy.lock` に移ります。
