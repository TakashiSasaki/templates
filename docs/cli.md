# CLI

## 共通形式

```bash
agent-policy [--repository PATH] [--format text|json] COMMAND [OPTIONS]
```

`--repository` と `--format` はサブコマンドより前に指定します。`--repository` を省略すると、現在位置からGitリポジトリルートを探索します。

## `init`

未導入かつ既存規約を持たないリポジトリの初期化計画を作成します。既定ではファイルを書き換えません。既存instructionを保持しながら導入する場合は、後続の`adopt`機能を使用し、`init`で競合を回避しないでください。

```bash
agent-policy --repository /path/to/repository init
```

適用する場合は `--apply` を指定します。

```bash
agent-policy --repository /path/to/repository init \
  --toolchain-revision <FULL_COMMIT_SHA> \
  --profile core \
  --profile security-baseline \
  --verification-command "npm run verify:pr" \
  --apply
```

主なオプション:

| オプション | 説明 |
| --- | --- |
| `--config PATH` | 設定ファイルのパス。既定は `.agent-policy.yml` |
| `--apply` | 計画を実際に適用する |
| `--toolchain-revision SHA` | 設定とロックへ記録するツールチェーンの完全なコミットSHA |
| `--profile NAME` | 初期プロファイル。複数指定可能 |
| `--project-policy PATH` | 作成する単一のproject policy scaffold。既定は `policy/project.md` |
| `--verification-command COMMAND` | 生成指示へ記載する検証コマンド。既定は `./scripts/verify.sh` |
| `--no-verification` | `verification` セクションを初期設定へ含めない |
| `--agents-output-path PATH` | agent instructionの生成先。既定は `AGENTS.md` |
| `--disable-agents-output` | agent instruction生成を初期設定で無効にする。pathは将来の有効化に備えて保持される |
| `--skill NAME` | 初期状態で生成するskill。`[a-z0-9][a-z0-9-]*`形式で複数指定可能。省略時は `validate-agent-policy` |

プロファイルを省略した場合は `core` と `security-baseline` が選択されます。`init`はplaceholder rule IDの重複を避けるため、project policy scaffoldを一つだけ作成します。複数の既存project policyを保持する導入は`adopt prepare`の責務です。

`init`は書き込み前に、skill名をschema相当の形式で検証し、設定、project policy、agent instruction、generated skillの各ファイル、`.agent-policy.lock`の生成予定pathを正規化して比較します。同一path、一方が他方の親pathとなる組合せ、いずれかの生成先の途中に既存の通常ファイルがある場合を拒否し、部分的な初期化を行いません。生成予定物同士の重複は`INIT_PATH_COLLISION`、既存pathによる妨害は`FILE_CONFLICT`として報告します。

既存挙動との互換性のため、verificationを指定しない場合は`./scripts/verify.sh`が設定されます。そのコマンドを持たないリポジトリでは、実際の検証コマンドを明示するか、`--no-verification`を指定します。

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

既存instructionを正本として保持したまま、agent-policy管理へ移行する準備状態を作ります。既定ではdry-runであり、実リポジトリには書き込みません。

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

`prepare`は一時コピー上でmanifest、project policy、preview、generated skill、lock、adoption stateを完全に生成・検証してから、新規ファイルだけを反映します。既存primary instructionと既存project policyは上書きしません。previewの既定出力先は`.agent-policy/preview/AGENTS.md`です。適用時の各fileはexclusive createで作成し、その呼出しが作成に成功したfileだけを失敗時cleanupの対象にします。

主なオプション:

| オプション | 説明 |
| --- | --- |
| `--config PATH` | 作成する設定ファイル。既定は `.agent-policy.yml` |
| `--state PATH` | adoption state。既定は `.agent-policy/adoption.json` |
| `--apply` | 検証済み準備状態を実際に作成する |
| `--toolchain-revision SHA` | 設定、lock、stateへ記録するtoolchain revision |
| `--profile NAME` | 選択するprofile。複数指定可能 |
| `--primary-instructions PATH` | 保持する既存instruction file。既定は `AGENTS.md` |
| `--project-policy PATH` | 既存または作成対象のproject policy。複数指定可能 |
| `--verification-command COMMAND` | repositoryの検証コマンド |
| `--no-verification` | verificationを設定しない。adoptionではこれが実質的な既定 |
| `--preview-output-path PATH` | shadow instructionの生成先 |
| `--skill NAME` | 生成するskill。複数指定可能。省略時は `validate-agent-policy` |
| `--no-skills` | generated skillを作成しない。`--skill`とは同時指定不可 |

`--primary-instructions`は、inspectionで発見された`AGENTS.md`、`CLAUDE.md`、`GEMINI.md`、`.github/copilot-instructions.md`のいずれかでなければなりません。`.agents/policies`または`.agents/skills`配下のsourceはinventoryとadoption stateには記録されますが、primary instructionとしては選択できません。policyまたはskillだけが存在するrepositoryは、対応するinstruction fileを用意するまで`adopt prepare`を実行できません。

複数のproject policyを指定できますが、`prepare`が新規scaffoldとして作成できるmissing fileは一つだけです。既存policyは内容を変更せず、そのままmanifest inputとして採用します。handwrittenの`.agents/skills/validate-agent-policy/SKILL.md`を保持する場合など、既存skillとdefault generated skillが競合するときは`--no-skills`を指定します。

## `adopt preview`

prepared stateに記録された不変sourceのhashと設定の整合性を検査し、現在のprofileとproject policyからshadow instruction、generated skill、lockを再生成します。project policyは編集可能なmanifest inputであり、prepare後に変更してpreviewへ反映できます。

```bash
agent-policy --repository . adopt preview
agent-policy --repository . adopt preview --state .agent-policy/adoption.json
```

prepare時に記録したprimary instructionなどの不変sourceが変更または削除されている場合は、`ADOPTION_SOURCE_CHANGED`として停止します。

## `adopt finalize`

prepared stateを正式なmanaged stateへ切り替えます。既定ではdry-runであり、source hash、state/config整合性、preview freshness、backup path、最終renderを一時コピー上で検証するだけです。

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

finalizeはconfig、state、lock、preview、adoption stateに記録された全immutable source、project policyを一つの入力snapshotとして扱います。temporary repositoryがそのsnapshotと一致することをrender前に検査し、最初の実書込み直前にもlive repositoryのbytesを再比較します。したがって、validationとstagingの間、またはstagingとtransactionの間にprimary、追加instruction、handwritten skill、policyのいずれかが変更された場合もcutoverせず停止します。config、state、lock、preview、primary instructionはlexical path上の通常ファイルでなければなりません。prepareとpreviewではrepository内の安全なprimary symlinkを保持できますが、finalize前には同じ意図した内容を持つ通常ファイルへmaterializeする必要があります。strict finalization pathがsymlinkへ置換された場合やsymlinked ancestorが導入された場合は、referentを変更せず拒否します。適用後の`check`が失敗した場合を含め、transaction途中の失敗ではtransactionが変更したfileだけを変更前へ戻します。backup pathが既に存在する場合、previewまたはlockがstaleな場合もcutoverしません。

主なオプション:

| オプション | 説明 |
| --- | --- |
| `--state PATH` | prepared adoption state。既定は `.agent-policy/adoption.json` |
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
