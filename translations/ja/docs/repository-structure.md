---
description: templatesのpolicyブランチにおける規約ツールチェーン、統合済みbootstrap skill、および各ディレクトリの責務を説明します。
---

# リポジトリ構造

> **参考訳（非正本）:** この文書は `docs/repository-structure.md` の日本語訳です。英語版が正本であり、内容に差異がある場合は英語版を優先します。

`TakashiSasaki/templates` の `policy` ブランチは、他の長期ブランチである `main`、`site`、`webapp` と共通祖先を持たないorphan historyです。`policy` には、規約ツールチェーンと初回導入用trust seedの両方を配置します。

bootstrap skillは `skills/bootstrap-agent-policy/` にあります。manifestがレビュー済みのfull commit SHAを固定するため、mutableな`policy`先端を実行しません。

## `policy` ブランチ

以下は、`policy` でGitが追跡している完全なツリーを表示するためのplaceholderです。documentation publication時に同じcommitからpreview manifestを生成します。

<!-- BEGIN VERIFIED TREE: policy -->
<div class="repository-tree" data-repository-branch="policy">
<p class="repository-tree__loading" role="status">ツリーを読み込んでいます…</p>
</div>
<!-- END VERIFIED TREE: policy -->

## 主要ディレクトリの役割

| パス | 役割 |
|---|---|
| `policy/` | 共有規約の正本。各規則はYAML front matter付きMarkdownとして管理する。 |
| `profiles/` | agent operationまたはrisk context向けの共有ポリシーモジュールを名前付きで選択する。profileは含める共有ルールを決め、最終的なルール順序は各ルールのmetadataが決める。 |
| `schemas/` | 製品リポジトリの `.agent-policy.yml` とadoption stateを検証するJSON Schema。toolchain repositoryは`TakashiSasaki/templates`。 |
| `src/agent_policy/` | 統合された `adopt inspect/prepare/preview/finalize`、`validate`、`render`、`check` を実装するPython CLI。hiddenな`init`はfresh adoption用の内部primitiveとして残る。 |
| `templates/` | `AGENTS.md`、製品固有規約、consumer workflowなどの生成template。 |
| `skills/` | 通常運用skillの正本と、`skills/bootstrap-agent-policy/`に統合された初回導入trust seed。 |
| `tests/` | 設定、adoption transaction、rendering、lock、path safety、repository identity、bootstrap trust boundaryを検査する。 |
| `docs/` | 導入方法、設計、ADR、PWA資産、repository preview UI。 |
| `scripts/` | repository preview生成・検証など、branchの保守とpublicationを支援するscript。 |
| `.github/workflows/` | `policy`向けCIとbuild-only documentation validation。Pages deployment authorityは持たない。 |

選択ガイドと現在の完全なprofileカタログについては、[Policyプロファイル](shared-policy/profiles.md)を参照してください。

## 統合済みbootstrap skill

```text
skills/bootstrap-agent-policy/
  SKILL.md
  README.md
  bootstrap-manifest.yml
  scripts/
    bootstrap.py
    install.py
    uninstall.py
```

| パス | 役割 |
|---|---|
| `SKILL.md` | 起動条件、inspection、repository stateから導出するfresh/migration adoption strategy、安全制約、migration finalizationの分離を定義する。 |
| `bootstrap-manifest.yml` | `TakashiSasaki/templates`のfull SHAと許可された内部route集合を固定する。finalize routeは含まない。 |
| `scripts/bootstrap.py` | 固定CLIを一時環境で取得し、repository stateをinspectionし、明示的に許可された場合に対応するadoption strategyを適用し、適用後検証を実行する。 |
| `scripts/install.py` | レビュー済みcheckoutからskill directoryへ安全にコピーする。 |
| `scripts/uninstall.py` | markerを確認して導入済みskillを削除する。 |
| `tests/test_bootstrap_skill.py` | manifest、pin、strategy route、安全制約、state parsing、post-apply commandを検査する。 |

## 導入前後の制御移行

```text
導入前
  user environmentの bootstrap-agent-policy skill
      ↓ bootstrap-manifest.yml の repository + full SHA
  templates上の pinned agent-policy CLI
      ↓ adopt inspect
  ├─ unmanaged-empty
  │    └─ adopt prepare --apply による fresh adoption
  │         └─ internal init primitive → managed
  │
  └─ unmanaged-existing
       └─ adopt prepare --apply による migration adoption
            ↓ previewと意味レビュー
          別の明示指示による adopt finalize --apply

導入完了後
  製品リポジトリの .agent-policy.yml
  .agent-policy.lock
  生成されたエージェント指示と通常運用skill
  repository-local CI
```

導入前のtrust seedはbootstrap packageです。fresh adoption完了後、またはmigration finalization完了後は、製品リポジトリに記録された設定、lock、生成物へ制御を引き渡します。
