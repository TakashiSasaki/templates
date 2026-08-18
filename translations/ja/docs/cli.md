# CLI

> **参考訳（非正本）:** この文書は `docs/cli.md` の日本語訳です。英語版が正本であり、内容に差異がある場合は英語版を優先します。

## 共通形式

```bash
agent-policy [--repository PATH] [--format text|json] COMMAND [OPTIONS]
```

`--repository` と `--format` はサブコマンドより前に指定します。`--repository` を省略すると、現在位置からGitリポジトリルートを探索します。

これらのexampleはcanonical toolchain CLIを直接説明します。`agent-policy` skillをinstallした通常のconsumer workflowでは、unmanaged repositoryに対してinstalled skill directoryから `python scripts/bootstrap.py ...` を、managed operationには `python scripts/run.py ...` を使用します。skillのinstallだけで `agent-policy` executableがglobalな `PATH` にinstallされるわけではありません。

## オンボーディングモデル

初回導入には常に `adopt` を使用します。`adopt inspect` が未管理リポジトリを分類し、`adopt prepare` がその状態から安全な内部strategyを選択します。

- `unmanaged-empty`: initialization primitiveを内部利用するfresh adoption
- `unmanaged-existing`: 手書きinstructionを保持するmigration adoption
- `managed`: 既にmanagedなのでbootstrapを拒否
- `inconsistent`: 不整合を修復するまでmutationを拒否

従来の `init` parserは、固定bootstrap trust seedと内部実装テストのためのhidden primitiveとしてだけ残します。独立した利用者向けonboarding workflowではありません。新しい呼出しは `adopt prepare` を使用してください。

## `adopt inspect`

既存のagent instruction、`.agents/policies`、`.agents/skills`を読み取り専用で調査し、リポジトリを次のいずれかへ分類します。

- `unmanaged-empty`
- `unmanaged-existing`
- `managed`
- `inconsistent`

```bash
agent-policy --repository . adopt inspect
agent-policy --repository . --format json adopt inspect
```

各sourceについてpath、SHA-256、生成マーカーの有無を診断として返します。ファイル内容はreportへ複製しません。repository内のsymlinkをsourceとして発見した場合、reportとadoption stateには発見されたlexical pathを記録し、SHA-256と生成マーカーはrepository内へ安全に解決した実体から計算します。既知のsource tree配下では、既存の通常ファイルを指すsymlinkだけをsourceとして許可します。directory、dangling target、その他の非通常ファイルを指すsymlinkは`inconsistent`として拒否し、repository外を指すsymlinkも拒否します。absolute symlinkはsource自身だけでなく、`.agents`や`.github`などlexical source pathのancestor componentに含まれる場合も`inconsistent`として拒否します。設定、lock、adoption state、生成マーカーだけが残る部分導入状態は`inconsistent`として扱います。

## `adopt prepare`

未管理リポジトリをagent-policy管理へ導入する準備を行います。既定ではdry-runであり、inspectionされたrepository stateから挙動を選択します。

`unmanaged-empty` ではfresh adoptionを行います。既存initialization実装を内部で使用し、`--apply`指定時には通常のmanaged filesを直接作成します。adoption-state transactionやprimary instructionsは必要ありません。

```bash
agent-policy --repository . adopt prepare \
  --profile core \
  --profile security-baseline

agent-policy --repository . adopt prepare \
  --profile core \
  --profile security-baseline \
  --apply
```

fresh adoptionでは従来のinitialization defaultsを維持します。project policy scaffoldは`policy/project.md`、生成instructionは`AGENTS.md`、生成skillは`validate-agent-policy`、verification commandは`--no-verification`を指定しない限り`./scripts/verify.sh`です。

`unmanaged-existing` では既存instructionを正本として保持したままstaged migration stateを作成します。

```bash
agent-policy --repository . adopt prepare \
  --primary-instructions AGENTS.md \
  --profile core \
  --profile security-baseline \
  --project-policy .agents/policies/repository.md \
  --verification-command "npm run verify:pr"
```

適用する場合は`--apply`を明示します。

```bash
agent-policy --repository . adopt prepare \
  --primary-instructions AGENTS.md \
  --verification-command "npm run verify:pr" \
  --apply
```

migration adoptionでは、`prepare`は一時コピー上でmanifest、project policy、preview、generated skill、lock、adoption stateを完全に生成・検証してから、新規ファイルだけを反映します。既存primary instructionと既存project policyは上書きしません。previewの既定出力先は`.agent-policy/preview/AGENTS.md`です。適用時の各fileはexclusive createで作成し、その呼出しが作成に成功したfileだけを失敗時cleanupの対象にします。

主なオプション:

| オプション | 説明 |
| --- | --- |
| `--config PATH` | 作成する設定ファイル。既定は `.agent-policy.yml` |
| `--state PATH` | migration adoption state。既定は `.agent-policy/adoption.json` |
| `--apply` | stateから導かれたadoption planを適用する |
| `--toolchain-revision SHA` | 生成stateへ記録するtoolchain revision |
| `--profile NAME` | 選択するprofile。複数指定可能 |
| `--primary-instructions PATH` | migration adoptionで保持する既存instruction。fresh adoptionでは指定不可 |
| `--project-policy PATH` | project policy path。migrationでは複数の既存pathを指定でき、freshではscaffold一つを要求 |
| `--verification-command COMMAND` | repositoryの検証コマンド。freshの既定は`./scripts/verify.sh`、migrationの既定はverificationなし |
| `--no-verification` | verificationを設定しない |
| `--preview-output-path PATH` | migration adoptionのshadow instruction生成先 |
| `--skill NAME` | 生成するskill。複数指定可能。省略時は `validate-agent-policy` |
| `--no-skills` | migration adoptionでgenerated skillを作成しない。`--skill`とは同時指定不可 |

migration adoptionでは、`--primary-instructions`はinspectionで発見された`AGENTS.md`、`CLAUDE.md`、`GEMINI.md`、`.github/copilot-instructions.md`のいずれかでなければなりません。`.agents/policies`または`.agents/skills`配下のsourceはinventoryとadoption stateには記録されますがprimary instructionにはできません。policyまたはskillだけが存在するrepositoryは、対応するinstruction fileを用意するまでmigration preparationへ進めません。

migration adoptionでは複数のproject policyを指定できますが、`prepare`が新規scaffoldとして作成できるmissing fileは一つだけです。既存policyは内容を変更せずmanifest inputとして採用します。handwrittenの`.agents/skills/validate-agent-policy/SKILL.md`などがdefault generated skillと競合するときは`--no-skills`を指定します。

fresh adoptionは書込み前にskill名と、config、policy、instruction、generated skill、lockの全生成予定pathを検証します。同一path、親子overlap、通常ファイルで塞がれたancestor、既存destination conflictは部分適用せず拒否します。

## `adopt preview`

prepared migration stateに記録されたimmutable source hashと設定の整合性を検査し、現在のprofileとproject policyからshadow instruction、generated skill、lockを再生成します。project policyは編集可能なmanifest inputであり、prepare後に変更してpreviewへ反映できます。

```bash
agent-policy --repository . adopt preview
agent-policy --repository . adopt preview --state .agent-policy/adoption.json
```

prepare時に記録したprimary instructionなどのimmutable sourceが変更または削除されている場合は`ADOPTION_SOURCE_CHANGED`として停止します。fresh adoptionはstaged adoption stateを作らないため`adopt preview`を使用しません。

## `adopt finalize`

prepared migration stateを正式なmanaged stateへ切り替えます。既定ではdry-runであり、source hash、state/config整合性、preview freshness、backup path、最終renderを一時コピー上で検証するだけです。

```bash
agent-policy --repository . adopt finalize
```

cutoverを適用する場合は`--apply`を明示します。

```bash
agent-policy --repository . adopt finalize \
  --backup-path .agent-policy/adoption/original/AGENTS.md \
  --apply
```

finalizeは次の変更を一つのtransactionとして扱います。

- handwritten primary instructionをbackup pathへbyte-for-byteで保存する
- `.agent-policy.yml`のagent outputをprimary instruction pathへ切り替える
- primary instructionを生成済みinstructionへ置き換える
- `.agent-policy.lock`を更新する
- adoption stateを`finalized`へ更新する
- shadow previewを削除する

finalizeはconfig、state、lock、preview、adoption stateに記録された全immutable source、project policyを一つの入力snapshotとして扱います。temporary repositoryがそのsnapshotと一致することをrender前に検査し、最初の実書込み直前にもlive repositoryのbytesを再比較します。したがってvalidationとstagingの間、またはstagingとtransactionの間にprimary、追加instruction、handwritten skill、policyのいずれかが変更された場合もcutoverせず停止します。config、state、lock、preview、primary instructionはlexical path上の通常ファイルでなければなりません。prepareとpreviewではrepository内の安全なprimary symlinkを保持できますが、finalize前には同じ意図した内容を持つ通常ファイルへmaterializeする必要があります。strict finalization pathがsymlinkへ置換された場合やsymlinked ancestorが導入された場合はreferentを変更せず拒否します。適用後の`check`が失敗した場合を含め、transaction途中の失敗ではtransactionが変更したfileだけを変更前へ戻します。backup pathが既に存在する場合、previewまたはlockがstaleな場合もcutoverしません。

主なオプション:

| オプション | 説明 |
| --- | --- |
| `--state PATH` | prepared migration adoption state。既定は `.agent-policy/adoption.json` |
| `--backup-path PATH` | handwritten primary instructionの保存先 |
| `--apply` | 検証済みcutoverを実際に適用する |

## `validate`

設定ファイルと参照対象の整合性を検査します。

```bash
agent-policy --repository . validate
agent-policy --repository . validate --config .agent-policy.yml
```

検査対象には、YAML／スキーマ、未知のキー、プロファイル、規約ファイル、規則ID、override、入力・出力パスの安全性が含まれます。

## `render`

共通規約と製品固有規約を合成し、生成物と `.agent-policy.lock` を更新します。

```bash
agent-policy --repository . render
```

生成物は直接編集せず、入力規約または `.agent-policy.yml` を変更して再生成します。

## `check`

設定、入力、ロックファイル、生成物が一致しているかを読み取り専用で確認します。

```bash
agent-policy --repository . check
```

CIではこのコマンドを使い、規約変更後の再生成漏れや生成物の手動改変を検出します。

## JSON出力

エージェントやCIから診断を処理する場合は、共通オプションの `--format json` を使います。

```bash
agent-policy --repository . --format json validate
```

終了コードは、エラー診断が一件以上あれば非ゼロになります。
