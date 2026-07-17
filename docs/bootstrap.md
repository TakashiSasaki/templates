# ブートストラップスキル

## 役割

`bootstrap-agent-policy` は、まだ `.agent-policy.yml` を持たないGitリポジトリへ `agent-policy` を導入するためのエージェントスキルです。

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

`SKILL.md` は起動条件、手順、安全制約を定義します。`bootstrap-manifest.yml` は実行を許可する `main` 上の完全なコミットSHAを固定し、`scripts/bootstrap.py` がそのCLIを一時環境で実行します。

## dry-runと適用

```bash
python scripts/bootstrap.py --repository /path/to/product
```

上記はdry-runです。実際に初期化する場合だけ `--apply` を付けます。

```bash
python scripts/bootstrap.py \
  --repository /path/to/product \
  --apply
```

適用後は、同じ固定ツールチェーンで `validate` と `check` が実行されます。

## 信頼境界

初期化前は、ブートストラップスキルのマニフェストに記録されたSHAを信頼します。初期化時に、そのSHAが製品リポジトリの `.agent-policy.yml` と `.agent-policy.lock` へ引き継がれます。

初期化後は次が通常運用の記録になります。

- `.agent-policy.yml`: 適用する規約、プロファイル、ツールチェーン、出力
- `.agent-policy.lock`: 実際に使用した入力・出力とハッシュ
- 生成されたエージェント指示と通常運用スキル
- リポジトリローカルのCI

## 更新時の注意

`bootstrap-manifest.yml` のSHA変更、`SKILL.md` の安全制約変更、`scripts/bootstrap.py` の変更は、通常の規約更新ではなく信頼基点の更新です。自動マージせず、差分を明示的にレビューしてください。
