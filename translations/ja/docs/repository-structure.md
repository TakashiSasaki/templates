---
description: templatesのpolicyブランチにおける規約ツールチェーン、単一agent-policy skill、persistent runtime cache、および各ディレクトリの責務を説明します。
---

# リポジトリ構造

> **参考訳（非正本）:** この文書は `docs/repository-structure.md` の日本語訳です。英語版が正本であり、内容に差異がある場合は英語版を優先します。

`TakashiSasaki/templates` の `policy` ブランチは、他の長期ブランチである `main`、`site`、`webapp` と共通祖先を持たないorphan historyです。`policy` には規約ツールチェーンと、repository-facingな単一 `agent-policy` skillを配置します。

skillは `skills/agent-policy/` にあります。runtime manifestがレビュー済みfull commit SHAと、そのrevisionのruntime dependency lockのSHA-256を固定するため、mutableな `policy` 先端を実行しません。

## `policy` ブランチ

以下は `policy` でGitが追跡している完全なtreeを表示するplaceholderです。documentation publication時に同じcommitからpreview manifestを生成します。

<!-- BEGIN VERIFIED TREE: policy -->
<div class="repository-tree" data-repository-branch="policy">
<p class="repository-tree__loading" role="status">ツリーを読み込んでいます…</p>
</div>
<!-- END VERIFIED TREE: policy -->

## 主要ディレクトリの役割

| パス | 役割 |
|---|---|
| `policy/` | 共有規約の正本。各規則はYAML front matter付きMarkdownとして管理する。 |
| `profiles/` | agent operationまたはrisk context向けの共有policy moduleを名前付きで選択する。profileは含める共有ruleを決め、最終順序はrule metadataが決める。 |
| `schemas/` | 製品repositoryの `.agent-policy.yml`、adoption state、stable release metadataを検証するJSON Schema。 |
| `src/agent_policy/` | 統合された `adopt inspect/prepare/preview/finalize`、`validate`、`render`、`check` を実装するcanonical Python CLI。hiddenな `init` はfresh adoption用の内部primitive。 |
| `templates/` | `AGENTS.md`、製品固有policy、consumer workflowなどのgeneration template。 |
| `skills/agent-policy/` | unmanaged bootstrap、managed command dispatch、immutable pin selection、persistent runtime cache管理を担う単一installable skill。 |
| `tests/` | configuration、adoption transaction、rendering、lock、path safety、release identity、runtime distribution、cache behavior、single-skill trust boundaryを検査する。 |
| `docs/` | adoption guidance、architecture、ADR、PWA asset、repository preview UI。 |
| `scripts/` | branch maintenance、release verification、runtime-distribution verification、publication helper。 |
| `.github/workflows/` | `policy`向けCIとbuild-only documentation validation。Pages deployment authorityは持たない。 |

選択ガイドと現在の完全なprofile catalogについては、[Policyプロファイル](shared-policy/profiles.md)を参照してください。

## 単一agent-policy skill

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

| パス | 役割 |
|---|---|
| `SKILL.md` | unmanaged repositoryをbootstrapする条件、managed commandを実行する条件、cache/pin semantics、migration finalizationの安全制約を定義する。 |
| `runtime-manifest.json` | `TakashiSasaki/templates` のstable full SHA、その `requirements-runtime.lock` のSHA-256、stable project identity、closed bootstrap route setを固定する。finalize routeは含まない。 |
| `scripts/runtime.py` | stableまたはrepository-pinned full SHAを解決し、persistent runtime cacheを構築・再利用し、Python/pip inputをsanitizeし、exact installed distribution setを検証する。 |
| `scripts/bootstrap.py` | unmanaged repositoryをinspectionし、許可された場合にstate-derived fresh/migration strategyを適用する。migration bootstrapはpreview後に停止する。 |
| `scripts/run.py` | `.agent-policy.lock` から選択したcached runtimeでmanaged commandを実行する。 |
| `scripts/install.py` | identity/path safetyを確認後、レビュー済みcheckoutからskillをatomicにinstall/replaceする。 |
| `scripts/uninstall.py` | identity markerを確認してinstalled skillを削除する。 |
| `tests/test_agent_policy_skill.py` | pin precedence、cache identity、offline cache hit、environment isolation、bootstrap safety、managed dispatch、install/uninstall guardを検査する。 |

## Runtimeと導入前後の制御

```text
導入前
  installed agent-policy skill
      ↓ runtime-manifest.json の stable full SHA + runtime-lock digest
  validated persistent runtime cache
      ↓ adopt inspect
  ├─ unmanaged-empty
  │    └─ fresh adoption --apply
  │         └─ internal init primitive → managed
  │
  └─ unmanaged-existing
       └─ migration prepare --apply
            ↓ previewとsemantic review
          別の明示指示による adopt finalize --apply

導入後
  同じinstalled agent-policy skill
      ↓ 製品repositoryの .agent-policy.lock にある full SHA
  validated persistent runtime cache
      ↓ normal managed commands
  .agent-policy.yml + generated outputs + repository-local CI
```

adoption前は `runtime-manifest.json` がレビュー済みstable default toolchainを提供します。`.agent-policy.lock` が存在した後は同じskillがrepository自身のfull-SHA pinを優先します。malformedまたはmutableなmanaged pinはsilent fallbackせずfail closedします。

runtime cache identityにはrepository、full revision、runtime-lock SHA-256、Python major/minor、platformを含めます。validなcacheはnetworkなしで再利用でき、cache missはstaging directoryで構築され、dependencyとinstalled-set validation成功後だけ正式位置へ移動します。
