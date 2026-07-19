# Managed repository operation

`agent-policy` の導入後は、製品リポジトリ内の生成済み `AGENTS.md` が一般的なコーディングエージェントの入口になります。このページは、初めてリポジトリを開いたエージェントと、policyを保守する人間の双方が同じ探索順序を使うための運用規約です。

## 初回探索順序

製品リポジトリで変更を始める前に、次の順序で確認します。

1. root `AGENTS.md` を読み、適用される共有規約、製品固有規約、必須検証コマンドを確認する。
2. `.agent-policy.yml` を読み、固定されたtoolchain repositoryと完全なcommit SHA、project policy入力、生成出力、generated skillを確認する。
3. `.agents/skills/manifest.json` などのrepository-local skill catalogが存在する場合は読み、変更面に該当するskillを確認する。
4. `AGENTS.md` の `Policy system` に列挙されたgenerated skillを読む。
5. 製品固有の意味を変更する場合だけ、`.agent-policy.yml` が参照するproject policyファイルを編集する。

生成`AGENTS.md`は直接編集しません。共有profile由来のrule sourceは、固定toolchainの `repository@revision:path` として表示されます。repository-local policyは、現在の製品リポジトリ内のpathとして表示されます。

## Policy変更の検証

`.agent-policy.yml`、project policy、生成instructions、generated skill、lock fileのいずれかに関係する変更では、`.agents/skills/validate-agent-policy/SKILL.md`を使用します。

利用可能な `agent-policy` コマンドがない場合でも、mutable branchや未固定releaseへ切り替えてはいけません。`.agent-policy.yml` の `toolchain.repository` と `toolchain.revision` を使用し、一時環境で固定revisionを実行します。

```bash
uvx --from "git+https://github.com/<repository>.git@<revision>" \
  agent-policy --repository . validate --config .agent-policy.yml
uvx --from "git+https://github.com/<repository>.git@<revision>" \
  agent-policy --repository . check --config .agent-policy.yml
```

`uvx` がない場合は一時virtual environmentへ同じfull-SHA Git referenceをinstallします。global環境へunversioned toolchainをinstallしません。

意味入力を変更して生成物がstaleになった場合は、明示的に同期する作業として固定toolchainの `render` を実行し、その後に `validate` と `check` を再実行します。

## Consumer CI

製品リポジトリには、製品固有のテストとは別にagent-policyの整合性gateを置きます。基準テンプレートはtoolchain repositoryの `templates/workflows/check-agent-policy.yml.j2` です。

workflowは `.agent-policy.yml` が固定する完全なcommit SHAを `uses:` に指定します。`main`、tag、短縮SHAなどのmutableまたは曖昧な参照を使用しません。

agent output、project policy、generated skillのpathは設定可能であるため、CIの `pull_request.paths` で固定pathだけに限定すると変更を見落とします。標準workflowは全pull requestで `agent-policy check` を実行します。製品側の必須検証コマンドは別のjobまたは既存CIで実行します。

## Adoption backup

既存リポジトリをfinalizeした場合、元のprimary instructionsは `.agent-policy/adoption.json` の `backup_path` に保存されます。これはcutoverの証跡と復旧用backupであり、現行instructionsではありません。

rootの生成`AGENTS.md`と現在のproject policyを正本として扱います。再帰的にすべての `AGENTS.md` を探索するツールは、adoption backupを現行規約として合成しないようにしてください。
