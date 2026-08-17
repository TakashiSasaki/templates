# ブートストラップスキル

> **参考訳（非正本）:** この文書は `docs/bootstrap.md` の日本語訳です。英語版が正本であり、内容に差異がある場合は英語版を優先します。

## 役割

`skills/bootstrap-agent-policy/` は、まだ `.agent-policy.yml` を持たないGitリポジトリを調査し、agent-policy管理下へ導入するエージェントスキルです。空のリポジトリにはfresh adoption、既存の手書き指示があるリポジトリにはmigration adoptionを使用します。

スキルは `TakashiSasaki/templates` の `policy` ブランチ内で管理されますが、実行時にmutableなブランチ先端を信頼しません。`bootstrap-manifest.yml` がレビュー済みfull commit SHAと許可された内部CLI routeを固定します。

## レビュー済みcheckoutから導入する

```bash
python skills/bootstrap-agent-policy/scripts/install.py \
  /path/to/agent-skills/bootstrap-agent-policy
```

既存の同一スキルを置き換える場合だけ `--replace` を指定します。

## リポジトリ調査とdry-run

```bash
python scripts/bootstrap.py --repository /path/to/product
```

既定では変更しません。固定されたCLIの `agent-policy adopt inspect` を実行し、状態からadoption strategyを選択します。

| 状態 | Adoption strategy |
|---|---|
| `unmanaged-empty` | fresh adoption |
| `unmanaged-existing` | migration adoption |
| `managed` | bootstrapを停止して通常運用へ移行 |
| `inconsistent` | 変更せず、部分導入状態や危険なpathを修復 |

利用者が `init` と `adopt` のrouteを選ぶ必要はありません。

## Fresh adoptionを適用する

`unmanaged-empty` ではdry-runを確認後、検査済みの遷移を `--apply` で許可します。

```bash
python scripts/bootstrap.py \
  --repository /path/to/product \
  --apply
```

bootstrapは現在、固定された `agent-policy init` をfresh-adoption用の内部primitiveとして使用し、その後 `validate` と `check` を実行します。initializationは独立したbootstrap操作ではありません。

## 既存指示をmigration adoptionする

複数の対応instruction fileが見つかった場合だけprimary sourceを指定します。

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

適用時は `adopt prepare --apply` の後に `adopt preview` を実行し、既存primary instructionは置き換えません。`adopt finalize --apply` はレビュー後の別の明示的指示として実行します。bootstrap manifestはfinalize routeを公開しません。

## 信頼境界

導入前は `SKILL.md`、`bootstrap-manifest.yml`、`scripts/bootstrap.py`、installer/uninstaller、bootstrap testsを一組のtrust seedとしてレビューします。

fresh adoption完了後、またはmigration adoption finalization完了後は `.agent-policy.yml`、`.agent-policy.lock`、生成されたagent instructionsとskills、repository-local CIが通常運用の記録になります。bootstrap skillはmanaged repositoryのruntime dependencyではありません。
