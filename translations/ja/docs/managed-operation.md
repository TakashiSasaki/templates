# Managed repository operation

> **参考訳（非正本）:** この文書は `docs/managed-operation.md` の日本語訳です。英語版が正本であり、内容に差異がある場合は英語版を優先します。

`agent-policy` の導入後は、製品リポジトリ内の生成済み `AGENTS.md` が一般的なコーディングエージェントのinstruction entry pointになります。一方、policy toolchain commandの実行入口は導入済みの単一 `agent-policy` skillのままであり、persistent runtime cacheを通じてrepositoryの `.agent-policy.lock` full-SHA pinに従います。

## 初回探索順序

製品リポジトリで変更を始める前に、次の順序で確認します。

1. root `AGENTS.md` を読み、適用される共有規約、製品固有規約、必須検証コマンドを確認する。
2. `.agent-policy.yml` を読み、semantic configuration、project policy入力、生成出力、generated skillを確認する。
3. `.agent-policy.lock` を読み、immutable toolchain repository/revisionとgenerated-state hashを確認する。
4. `.agents/skills/manifest.json` などのrepository-local skill catalogが存在する場合は読み、変更面に該当するskillを確認する。
5. `AGENTS.md` の `Policy system` に列挙されたgenerated skillを読む。
6. 製品固有の意味を変更する場合だけ、`.agent-policy.yml` が参照するproject policyファイルを編集する。

生成`AGENTS.md`は直接編集しません。共有profile由来のrule sourceは、固定toolchainの `repository@revision:path` として表示されます。repository-local policyは、現在の製品リポジトリ内のpathとして表示されます。

## Policy変更の検証

`.agent-policy.yml`、project policy、生成instructions、generated skill、lock fileのいずれかに関係する変更では、`.agents/skills/validate-agent-policy/SKILL.md`を使用します。

直接toolchainを実行する場合は、導入済みの単一skillを使用します。

```bash
python /path/to/agent-skills/agent-policy/scripts/run.py \
  --repository . \
  validate --config .agent-policy.yml
python /path/to/agent-skills/agent-policy/scripts/run.py \
  --repository . \
  check --config .agent-policy.yml
```

`scripts/run.py` は `.agent-policy.lock` を読み、`TakashiSasaki/templates` とfull lowercase commit SHAを要求し、そのrevision用の検証済みpersistent runtimeを選択します。malformedまたはmutableなlockは、skillのstable defaultへfallbackせずfail closedします。

validなruntime cache entryはnetworkなしで再利用できます。repositoryが別のfull SHAをpinし、compatibleなcacheが存在しない場合、skillはそのrevisionのruntime lockを取得してcache identityを導出し、staging directoryでruntimeを構築・検証した後だけactiveにします。

mutableな `policy` ブランチ、unpinned release、provenance不明のglobal toolchainを直接実行してこの経路を迂回しないでください。

意味入力を変更して生成物がstaleになった場合は、同じrepository-pinned runtimeで `render` を明示的に実行し、その後 `validate` と `check` を再実行します。

## Consumer CI

製品リポジトリには、製品固有のテストとは別にagent-policyの整合性gateを置きます。基準テンプレートはtoolchain repositoryの `templates/workflows/check-agent-policy.yml.j2` です。

workflowは `.agent-policy.yml` が固定する完全なcommit SHAを `uses:` に指定します。`main`、tag、短縮SHAなどのmutableまたは曖昧な参照を使用しません。

agent output、project policy、generated skillのpathは設定可能であるため、CIの `pull_request.paths` で固定pathだけに限定すると変更を見落とします。標準workflowは全pull requestで `agent-policy check` を実行します。製品側の必須検証コマンドは別のjobまたは既存CIで実行します。

## Adoption backup

既存リポジトリをfinalizeした場合、元のprimary instructionsは `.agent-policy/adoption.json` の `backup_path` に保存されます。これはcutoverの証跡と復旧用backupであり、現行instructionsではありません。

rootの生成`AGENTS.md`と現在のproject policyを正本として扱います。再帰的にすべての `AGENTS.md` を探索するツールは、adoption backupを現行規約として合成しないようにしてください。
