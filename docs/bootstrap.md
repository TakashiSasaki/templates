# ブートストラップスキル

## 役割

`skills/bootstrap-agent-policy/` は、まだ `.agent-policy.yml` を持たないGitリポジトリを調査し、空のリポジトリなら初期化、既存の手書き指示があるリポジトリなら安全な導入準備へ振り分けるエージェントスキルです。

スキルは `TakashiSasaki/templates` の `policy` ブランチ内で管理されますが、実行時にmutableなブランチ先端を信頼することはありません。`bootstrap-manifest.yml` が、レビュー済みの完全なコミットSHAと許可されたCLI routeを固定します。

## レビュー済みcheckoutから導入する

`policy` のレビュー済みcommitをcheckoutした状態で、installerを実行します。

```bash
python skills/bootstrap-agent-policy/scripts/install.py \
  /path/to/agent-skills/bootstrap-agent-policy
```

既存の同名スキルを置き換える場合だけ `--replace` を指定します。installerは、置換対象の `SKILL.md` がこのスキルを示していない場合は拒否します。

リポジトリ全体を常設したくない場合はsparse checkoutを使用できます。

```bash
git clone --filter=blob:none --no-checkout \
  --branch policy --single-branch \
  https://github.com/TakashiSasaki/templates.git \
  templates-policy

git -C templates-policy sparse-checkout init --cone
git -C templates-policy sparse-checkout set skills/bootstrap-agent-policy
git -C templates-policy checkout <reviewed-full-commit-sha>

python templates-policy/skills/bootstrap-agent-policy/scripts/install.py \
  /path/to/agent-skills/bootstrap-agent-policy
```

`<reviewed-full-commit-sha>`を`policy`、tag、短縮SHAなどへ置き換えないでください。

## スキルの構成

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

repository側の `tests/test_bootstrap_skill.py` がmanifest、固定SHA、state parsing、route選択、refusal state、finalize非公開、適用後commandを検査します。

## リポジトリ調査とdry-run

導入済みskill directoryから実行します。

```bash
python scripts/bootstrap.py --repository /path/to/product
```

既定ではファイルを変更しません。固定されたCLIの `agent-policy adopt inspect` を実行して、次の状態を報告します。

| 状態 | 推奨経路 |
|---|---|
| `unmanaged-empty` | `init` |
| `unmanaged-existing` | `adopt prepare` |
| `managed` | bootstrapを停止して通常運用へ移行 |
| `inconsistent` | 変更せず、部分導入状態や危険なpathを修復 |

続いて、推奨された `init` または `adopt prepare` をdry-runで実行し、作成予定ファイルや競合を表示します。自動振り分けはdry-runの助言に限定されます。

## 空のリポジトリを初期化する

```bash
python scripts/bootstrap.py \
  --repository /path/to/product \
  --route init \
  --apply
```

書込み時は明示的なroute選択が必須です。適用後は、同じ固定ツールチェーンで `validate` と `check` が実行されます。

## 既存指示の導入準備を行う

調査で発見されたinstruction fileから正本を一つ選びます。

```bash
python scripts/bootstrap.py \
  --repository /path/to/product \
  --route adopt \
  --primary-instructions AGENTS.md
```

計画を確認した後、準備状態を作成する場合だけ `--apply` を付けます。

```bash
python scripts/bootstrap.py \
  --repository /path/to/product \
  --route adopt \
  --primary-instructions AGENTS.md \
  --apply
```

適用時は `adopt prepare --apply` の後に `adopt preview` を実行します。既存のprimary instructionは置き換えません。

project policyとpreviewをレビューした後の `adopt finalize --apply` は別の明示的な指示として、manifestに記録された同じrepositoryとfull SHAのCLIを用いて実行します。bootstrap manifestと `scripts/bootstrap.py` はfinalize routeを公開しません。

## 信頼境界

導入前は次を一組のtrust seedとしてレビューします。

- `SKILL.md`の安全制約
- `bootstrap-manifest.yml`のrepository、full SHA、route集合
- `scripts/bootstrap.py`の取得・振り分け・適用処理
- installer/uninstaller
- bootstrap tests

初期化完了後、またはadoption finalization完了後は次が通常運用の記録になります。

- `.agent-policy.yml`
- `.agent-policy.lock`
- 生成されたエージェント指示と通常運用スキル
- リポジトリローカルのCI

bootstrap skillはmanaged repositoryのruntime dependencyではありません。
