# ブートストラップスキル

## 役割

`bootstrap-agent-policy` は、まだ `.agent-policy.yml` を持たないGitリポジトリを調査し、空のリポジトリなら初期化、既存の手書き指示があるリポジトリなら安全な導入準備へ振り分けるエージェントスキルです。

このブランチは `main` と共通祖先を持たないorphan branchで、ブランチのルートに `SKILL.md` があります。そのため、ブランチ全体をエージェントのスキルディレクトリへ直接cloneできます。

## ブランチを直接cloneする

```bash
git clone \
  --branch bootstrap-agent-policy \
  --single-branch \
  https://github.com/TakashiSasaki/agent-policy.git \
  bootstrap-agent-policy
```

ブランチ名はclone先ディレクトリ名を自動決定しません。最後の引数で、利用するエージェントのスキル格納先を明示してください。

## サブモジュールとして取り込む

```bash
git submodule add \
  -b bootstrap-agent-policy \
  https://github.com/TakashiSasaki/agent-policy.git \
  .agents/skills/bootstrap-agent-policy
```

サブモジュールは特定コミットを記録します。信頼の種であるため、ブランチ先端への無人追従は推奨しません。

## スキルの構成

```text
SKILL.md
README.md
bootstrap-manifest.yml
scripts/
  bootstrap.py
  install.py
  uninstall.py
tests/
  test_bootstrap.py
.github/workflows/
  validate-bootstrap.yml
```

`SKILL.md` は起動条件、振り分け手順、安全制約を定義します。`bootstrap-manifest.yml` は実行を許可する `main` 上の完全なコミットSHAとコマンド経路を固定し、`scripts/bootstrap.py` がそのCLIを一時環境で実行します。

## リポジトリ調査とdry-run

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

`unmanaged-empty` と判定された場合は、明示的に `init` 経路を選択して適用します。

```bash
python scripts/bootstrap.py \
  --repository /path/to/product \
  --route init \
  --apply
```

適用後は、同じ固定ツールチェーンで `validate` と `check` が実行されます。

## 既存指示の導入準備を行う

`unmanaged-existing` と判定された場合は、調査で発見されたinstruction fileから正本を一つ選びます。

```bash
python scripts/bootstrap.py \
  --repository /path/to/product \
  --route adopt \
  --primary-instructions AGENTS.md
```

上記は `adopt prepare` のdry-runです。計画を確認した後、準備状態を作成する場合だけ `--apply` を付けます。

```bash
python scripts/bootstrap.py \
  --repository /path/to/product \
  --route adopt \
  --primary-instructions AGENTS.md \
  --apply
```

適用時は `adopt prepare --apply` の後に `adopt preview` を実行します。既存のprimary instructionは置き換えず、`.agent-policy/preview/AGENTS.md` などのshadow outputを生成して比較可能な状態にします。

project policyとpreviewをレビューした後の `adopt finalize --apply` は、別の明示的な指示として実行します。bootstrap manifestと `scripts/bootstrap.py` はfinalize経路を公開せず、準備とcutoverを一回の無人操作へ統合しません。

## 明示的な経路選択

書込みを伴う `--apply` では、`--route init` または `--route adopt` が必須です。指定された経路がinspection結果と一致しない場合は拒否します。

たとえば既存指示が発見されたリポジトリへ `--route init --apply` を指定しても、競合を無視して初期化することはありません。`managed` と `inconsistent` もfail-closedで停止します。

## 信頼境界

導入前は、ブートストラップスキルのマニフェストに記録された完全なSHAと許可経路を信頼します。`main`、tag、短縮SHAなどのmutable referenceは使用しません。

初期化完了後、またはadoption finalization完了後は次が通常運用の記録になります。

- `.agent-policy.yml`: 適用する規約、プロファイル、ツールチェーン、出力
- `.agent-policy.lock`: 実際に使用した入力・出力とハッシュ
- 生成されたエージェント指示と通常運用スキル
- リポジトリローカルのCI

adoption準備中は、既存primary instructionが正本のまま保持され、adoption state、preview、lockがレビュー対象になります。

## 更新時の注意

`bootstrap-manifest.yml` のSHA・route変更、`SKILL.md` の安全制約変更、`scripts/bootstrap.py` の変更、bootstrap testの変更は、通常の規約更新ではなく信頼基点の更新です。自動マージせず、差分を明示的にレビューしてください。
