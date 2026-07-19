---
description: mainとbootstrap-agent-policyのツリー構造、各ディレクトリの責務、および二つの独立した履歴の関係を説明します。
---

# リポジトリ構造

`TakashiSasaki/agent-policy` には、共通祖先を持たない二つの長期ブランチがあります。

- `main`: 規約、Python CLI、設定スキーマ、レンダラー、初期化・既存リポジトリ導入処理、通常運用スキル、テスト、GitHub Actions、公開ドキュメントを管理します。
- `bootstrap-agent-policy`: `agent-policy` が未導入のリポジトリを調査し、空なら初期化、既存指示があれば導入準備へ振り分ける、直接clone可能なエージェントスキルです。

二つのブランチはunrelated historiesです。`bootstrap-agent-policy` は `main` のファイルを内包せず、`bootstrap-manifest.yml` に固定された完全なコミットSHAと許可routeを通じて `main` のCLIを起動します。

掲載ツリーとファイルプレビューは、GitHub Pagesのビルド時に両ブランチのGitオブジェクトから生成されます。CIは公開用マニフェストに含まれる全ファイルパスと実際のGitツリーが完全に一致することを検査します。

ファイル名を選択すると、同じビルドで書き出された内容をダイアログで確認できます。UTF-8テキストでは行番号、行の折り返し、シンタックスハイライトを個別に切り替えられ、選択状態はブラウザ内に保存されます。PNG・JPEG・GIF・WebP画像もプレビューし、それ以外のバイナリまたは512 KiBを超えるファイルはGitHub上の表示へ案内します。

## `main` ブランチ

以下は、`main` でGitが追跡している完全なツリーです。ビルド生成物や未追跡の一時ファイルは含みません。

<!-- BEGIN VERIFIED TREE: main -->
<div class="repository-tree" data-repository-branch="main">
<p class="repository-tree__loading" role="status">ツリーを読み込んでいます…</p>
</div>
<!-- END VERIFIED TREE: main -->

### 主要ディレクトリの役割

| パス | 役割 |
|---|---|
| `policy/` | 共有規約の正本です。各規則はYAML front matter付きMarkdownとして管理します。 |
| `profiles/` | 適用する規約ファイルの集合と順序を宣言します。 |
| `schemas/` | 製品リポジトリの `.agent-policy.yml` とadoption stateを検証するJSON Schemaを格納します。 |
| `src/agent_policy/` | `init`、`adopt inspect/prepare/preview/finalize`、`validate`、`render`、`check` を実装するPython CLI本体です。 |
| `templates/` | `AGENTS.md`、製品固有規約、検査ワークフローなどの生成テンプレートです。 |
| `skills/` | 初期化後またはadoption後の製品リポジトリへ配布する通常運用スキルの正本です。 |
| `tests/` | 設定検証、初期化、adoption state、preview、transactional finalization、レンダリング、ロック整合性、パス安全性、リポジトリ保守判定、プレビュー資産分類・トークン化を検査します。 |
| `docs/` | GitHub Pagesで公開する導入方法、設計、PWA資産、ファイルプレビューUIを管理します。 |
| `overrides/` | MkDocsテーマを拡張し、PWA、Open Graph、Twitter CardなどのHTML要素を追加します。 |
| `.github/workflows/` | CLIのCI、GitHub Pagesのデプロイ、不要PR・マージ済みブランチの自動清掃を実行します。 |

## `bootstrap-agent-policy` ブランチ

このブランチは、ブランチ全体を一つのエージェントスキルとしてcloneできるよう、ルートに `SKILL.md` を配置しています。

<!-- BEGIN VERIFIED TREE: bootstrap-agent-policy -->
<div class="repository-tree" data-repository-branch="bootstrap-agent-policy">
<p class="repository-tree__loading" role="status">ツリーを読み込んでいます…</p>
</div>
<!-- END VERIFIED TREE: bootstrap-agent-policy -->

### 各ファイルの役割

| パス | 役割 |
|---|---|
| `SKILL.md` | スキルの起動条件、inspection、`init`／`adopt`振り分け、安全制約、finalizeの分離を定義します。 |
| `bootstrap-manifest.yml` | 実行を許可する `main` 上のCLIを完全なコミットSHAで固定し、inspection、initialization、adoption preparation/preview、validation、checkのrouteを列挙します。finalize routeは含みません。 |
| `scripts/bootstrap.py` | 固定されたCLIを一時環境で取得し、read-only inspection、明示的な`init`または`adopt prepare`、適用後の検証を実行します。 |
| `scripts/install.py` | ブートストラップスキルをユーザーのエージェント環境へ導入します。 |
| `scripts/uninstall.py` | 導入済みのブートストラップスキルを削除します。 |
| `tests/test_bootstrap.py` | マニフェスト、固定SHA、state parsing、route選択、refusal state、finalize非公開、適用後commandを検査します。 |
| `.github/workflows/validate-bootstrap.yml` | ブートストラップブランチとそのPRを対象に独立したCIを実行し、immutableかつnon-finalizingなtrust boundaryを検査します。 |

## 導入前後の制御移行

```text
導入前
  ユーザー環境の bootstrap-agent-policy
      ↓ bootstrap-manifest.yml の固定SHA
  main上の agent-policy adopt inspect
      ↓
  ├─ unmanaged-empty
  │    └─ 明示的な init --apply
  │
  └─ unmanaged-existing
       └─ 明示的な adopt prepare --apply
            ↓ previewと意味レビュー
          別の明示指示による adopt finalize --apply

導入完了後
  製品リポジトリの .agent-policy.yml
  .agent-policy.lock
  生成されたエージェント指示と通常運用スキル
  リポジトリローカルのCI
```

導入前の信頼基点はブートストラップスキルです。初期化完了後、またはadoption finalization完了後は、製品リポジトリに記録された設定、ロックファイル、生成物へ制御を引き渡します。adoption準備中は、手書きprimary instructionを保持したまま、adoption stateとshadow previewをレビューします。
