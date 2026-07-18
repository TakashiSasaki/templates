---
description: mainとbootstrap-agent-policyのツリー構造、各ディレクトリの責務、および二つの独立した履歴の関係を説明します。
---

# リポジトリ構造

`TakashiSasaki/agent-policy` には、共通祖先を持たない二つの長期ブランチがあります。

- `main`: 規約、Python CLI、設定スキーマ、レンダラー、通常運用スキル、テスト、GitHub Actions、公開ドキュメントを管理します。
- `bootstrap-agent-policy`: `agent-policy` が未導入のリポジトリへ最初の導入を行う、直接clone可能なエージェントスキルです。

二つのブランチはunrelated historiesです。`bootstrap-agent-policy` は `main` のファイルを内包せず、`bootstrap-manifest.yml` に固定された完全なコミットSHAを通じて `main` のCLIを起動します。

掲載しているツリーはGitの追跡対象から機械生成できます。GitHub Pagesのビルド時に、各コードブロックと実際のGitツリーが完全に一致することを検査します。ツリーを手作業で修正せず、構成変更後は `python scripts/verify-repository-structure.py --update` を実行してください。

## `main` ブランチ

以下は、`main` でGitが追跡しているファイルの完全なツリー構造です。ビルド生成物や未追跡の一時ファイルは含みません。

<!-- BEGIN VERIFIED TREE: main -->
```text
.
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── pages.yml
├── docs/
│   ├── adr/
│   │   └── 0001-unrelated-bootstrap-history.md
│   ├── assets/
│   │   ├── icons/
│   │   │   ├── apple-touch-icon.png
│   │   │   ├── favicon-16.png
│   │   │   ├── favicon-32.png
│   │   │   ├── icon-192.png
│   │   │   ├── icon-512.png
│   │   │   └── icon-maskable-512.png
│   │   └── javascripts/
│   │       └── pwa.js
│   ├── architecture.md
│   ├── bootstrap-model.md
│   ├── bootstrap.md
│   ├── cli.md
│   ├── configuration.md
│   ├── getting-started.md
│   ├── index.md
│   ├── manifest.webmanifest
│   ├── offline.html
│   ├── policy-authoring.md
│   ├── pwa.md
│   ├── repository-structure.md
│   ├── service-worker.js
│   └── threat-model.md
├── overrides/
│   └── main.html
├── policy/
│   ├── core/
│   │   ├── change-scope.md
│   │   ├── compatibility.md
│   │   ├── regression-safety.md
│   │   ├── testing.md
│   │   └── truthful-reporting.md
│   └── security/
│       ├── input-validation.md
│       └── secrets.md
├── profiles/
│   ├── core.yml
│   └── security-baseline.yml
├── schemas/
│   └── agent-policy.schema.json
├── scripts/
│   ├── generate-doc-assets.py
│   └── verify-repository-structure.py
├── skills/
│   └── validate-agent-policy/
│       └── SKILL.md
├── src/
│   └── agent_policy/
│       ├── commands/
│       │   ├── __init__.py
│       │   ├── check.py
│       │   ├── init.py
│       │   ├── render.py
│       │   └── validate.py
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── diagnostics.py
│       ├── lockfile.py
│       ├── paths.py
│       ├── policy_loader.py
│       ├── renderer.py
│       └── yamlutil.py
├── templates/
│   ├── workflows/
│   │   └── check-agent-policy.yml.j2
│   ├── AGENTS.md.j2
│   └── project-policy.md.j2
├── tests/
│   ├── test_config.py
│   ├── test_init_render_check.py
│   └── test_paths.py
├── .gitignore
├── action.yml
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── mkdocs.yml
├── pyproject.toml
├── README.md
├── requirements-docs.txt
└── SECURITY.md
```
<!-- END VERIFIED TREE: main -->

### 主要ディレクトリの役割

| パス | 役割 |
|---|---|
| `policy/` | 共有規約の正本です。各規則はYAML front matter付きMarkdownとして管理します。 |
| `profiles/` | 適用する規約ファイルの集合と順序を宣言します。 |
| `schemas/` | 製品リポジトリの `.agent-policy.yml` を検証するJSON Schemaを格納します。 |
| `src/agent_policy/` | `init`、`validate`、`render`、`check` を実装するPython CLI本体です。 |
| `templates/` | `AGENTS.md`、製品固有規約、検査ワークフローなどの生成テンプレートです。 |
| `skills/` | 初期化後の製品リポジトリへ配布する通常運用スキルの正本です。 |
| `tests/` | 設定検証、初期化、レンダリング、ロック整合性、パス安全性を検査します。 |
| `docs/` | GitHub Pagesで公開する利用方法、設計、PWA資産を管理します。 |
| `overrides/` | MkDocsテーマを拡張し、PWA、Open Graph、Twitter CardなどのHTML要素を追加します。 |
| `.github/workflows/` | CLIのCIとGitHub Pagesのビルド・デプロイを実行します。 |

## `bootstrap-agent-policy` ブランチ

このブランチは、ブランチ全体を一つのエージェントスキルとしてcloneできるよう、ルートに `SKILL.md` を配置しています。

<!-- BEGIN VERIFIED TREE: bootstrap-agent-policy -->
```text
.
├── .github/
│   └── workflows/
│       └── validate-bootstrap.yml
├── scripts/
│   ├── bootstrap.py
│   ├── install.py
│   └── uninstall.py
├── tests/
│   └── test_bootstrap.py
├── .gitignore
├── bootstrap-manifest.yml
├── LICENSE
├── README.md
└── SKILL.md
```
<!-- END VERIFIED TREE: bootstrap-agent-policy -->

### 各ファイルの役割

| パス | 役割 |
|---|---|
| `SKILL.md` | スキルの起動条件、初期化手順、安全制約、検証手順を定義します。 |
| `bootstrap-manifest.yml` | 実行を許可する `main` 上のCLIを完全なコミットSHAで固定します。 |
| `scripts/bootstrap.py` | 固定されたCLIを一時環境で取得し、`init`、`validate`、`check` を実行します。 |
| `scripts/install.py` | ブートストラップスキルをユーザーのエージェント環境へ導入します。 |
| `scripts/uninstall.py` | 導入済みのブートストラップスキルを削除します。 |
| `tests/test_bootstrap.py` | マニフェスト、固定SHA、dry-run、初期化処理の基本動作を検査します。 |
| `.github/workflows/validate-bootstrap.yml` | ブートストラップブランチだけを対象に独立したCIを実行します。 |

## 初期化前後の制御移行

```text
初期化前
  ユーザー環境の bootstrap-agent-policy
      ↓ bootstrap-manifest.yml の固定SHA
  main上の agent-policy init
      ↓
初期化後
  製品リポジトリの .agent-policy.yml
  .agent-policy.lock
  生成されたエージェント指示と通常運用スキル
  リポジトリローカルのCI
```

初期化前の信頼基点はブートストラップスキルです。初期化完了後は、製品リポジトリに記録された設定、ロックファイル、生成物へ制御を引き渡します。
