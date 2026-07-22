# 退行を抑制する普遍規約

このページは、複数のリポジトリでコーディングエージェントを利用した際に繰り返し観察された退行と、その抑止に有効だった対策のうち、特定の言語、フレームワーク、製品、またはUI実装に依存しないものを整理します。

`policy/core/` には、生成されるエージェント指示へ直接含める短い規範だけを置きます。このページは、その採用理由、適用境界、および機械的強制との関係を説明する非規範的な文書です。

## 採用基準

普遍規約へ含める項目は、原則として次の条件を満たすものに限定します。

1. 複数のリポジトリまたは異なる種類の変更で同型の失敗が観察されている。
2. 特定の技術スタックを前提とせず、一般的なソフトウェア変更へ適用できる。
3. エージェントが実行可能な指示として短く表現できる。
4. diff、テスト、生成差分、現在のrevision、または操作対象の状態など、何らかの証拠で遵守を確認できる。
5. 過剰な探索や無関係な作業を誘発する一般論ではなく、具体的な失敗経路を閉じる。

## core profileへ含める原則

### 変更契約を先に確定する

変更対象だけを指定しても、保存すべき既存挙動、非目標、受入証拠が暗黙のままでは、エージェントが実装上の都合で範囲を拡大しやすくなります。そのため、編集前に次を識別します。

- requested outcome
- allowed change surface
- preserved behavior and invariants
- explicit non-goals
- acceptance evidence

指定されていない既存挙動は、要求された変更に不可避でない限り保存対象として扱います。これは `changes.define-contract` と `changes.minimize-scope` の組合せで表現します。

### Acceptance baselineを作業中に動かさない

変更契約を定義しても、実装またはauditの途中でscope、非目標、完了条件、必要証拠、停止条件を遡及的に拡張すると、完了可能性と過去のevidenceが失われます。`changes.preserve-acceptance-baseline` は、開始後のbaselineを固定し、rebaselineを明示的なowner decisionとして扱います。

Rebaselineが必要な場合は、少なくとも次を記録します。

- 変更するbaseline項目
- 変更理由
- 既に完了した作業への影響
- 以前の検証結果が引き続き有効か
- 新しい停止条件

Auditは新しい要求を発見する場になり得ますが、その要求を現在の作業へ自動的に遡及適用してはいけません。別の作業単位へdeferするか、明示的にrebaselineします。

### 意味に関わる曖昧さを推測で閉じない

実装方法の小さな選択はエージェントが判断できますが、observable behavior、data meaning、compatibility、architecture、risk、scopeを変える選択はowner decisionです。`decisions.escalate-semantic-ambiguity` は、単に質問するのではなく、次を提示してdependent changeを止めます。

- viable options
- trade-offs
- impact
- recommendation
- decision required

この規約は、些細な実装詳細ごとに確認を要求するものではありません。結果の意味または契約を変える選択だけをgateします。

### 発見した失敗を回帰テストとして固定する

既存テストを弱めないだけでなく、再現可能な不具合修正では、修正前に失敗し修正後に成功するテストを追加します。一般的なテスト数の増加より、実際に発見された反例を固定する方が、同型の退行に対する直接的な検出力を持ちます。

再現が環境依存または非決定的である場合は、再現できなかった事実を成功として扱わず、対象となる危険な条件、追加した防御、実行した代替検証を報告します。

### 検証の実行と合格を区別する

コマンドを起動したこと、workflowが存在すること、レビューが設定されていることは、現在の変更が検証済みであることを意味しません。検証結果は、少なくとも次の状態を区別します。

- passed
- failed
- pending
- skipped
- not triggered
- stale for the current revision
- blocked by the environment
- inspected or inferred only

必要な検証が変更surfaceを実際に覆っているかも確認します。集約コマンドや緑色のCIだけを、未包含のテスト、path filterで除外されたworkflow、または古いcommitに対する結果の代替にしてはいけません。

### Evidence layerを相互に代用しない

`verification.separate-evidence-layers` は、検証結果をexact revisionまたはartifactと、その結果を生成したlayerへ結び付けます。標準的には次を分けます。

- repository-local checks
- environment-dependent checks
- remote CI
- independent audit

例えば、local validatorのPASSはremote CIの実行を証明せず、remote CIのPASSはindependent auditのacceptanceを証明しません。Schema validation、filesystem validation、transfer hash、semantic acceptanceも、それぞれ異なる主張です。

### 正本と派生物を同期する

生成ファイル、複製された設定、コンパイル済み資産、manifest、fixture、公開文書などは、正本の変更後に陳腐化しやすい対象です。関連する変更では、リポジトリが定める生成または同期手順を使用し、欠落または差分が残っていないことを検査します。

派生物の同期は、人間やエージェントの注意だけに依存させず、可能ならgeneratorのcheck mode、再生成後のdiff、hash、schema検証、またはCIの完全一致検査で強制します。

### 破壊的操作の直前に状態を再検証する

削除、上書き、migration、deploy、publish、force updateなどの操作では、作業開始時に取得した状態が実行時にも有効とは限りません。操作直前に、少なくとも対象のidentity、scope、revision、保護状態、および競合利用を再確認します。

可能な場合はdry-run、最小scope、冪等な操作を優先します。以前の検索結果や局所的な処理結果だけから、現在の全体状態を推定して破壊的操作を許可してはいけません。

### Rollbackを現在の操作が所有する変更へ限定する

複数段階のmutationでは、失敗時cleanupが別processまたは作業前から存在したfileを削除すること自体が退行になります。`safety.limit-rollback-to-owned-changes` は、最初のwriteより前にpreflightを完了し、commit boundaryでlive stateを再検証し、現在の操作がcreateまたはchangeしたpathを追跡することを要求します。

Rollbackでは、そのownershipが確認できる変更だけを戻します。競合processが作成したfile、作業前から存在したfile、今回変更していないreferentをcleanupの名目で削除または上書きしてはいけません。

### 外部契約と報告の真実性を保存する

公開API、保存形式、設定形式、CLI、migration pathなどの外部契約は、明示的に許可された非互換変更でない限り保存します。また、implemented、generated、executed、verified、inferredを区別し、未検証事項を完了として報告しません。

## Optional profileへ分離する項目

外部archive、historical source、vendor bundle、生成物などの受領では、provenance、digest、archive path、declared intent、exact-byte staging、dependency closureといった追加規約が必要です。これらは一般的な変更すべてに必要ではないため、`external-artifact-intake` profileへ分離します。

具体的な規則と適用順序は[外部artifact受領規約プロファイル](external-artifact-intake.md)を参照してください。製品固有のmanifest schema、source allowlist、destination mapping、activation gateは製品repositoryのpolicyとvalidatorに残します。

## 自然言語規約と機械的強制

自然言語規約は、エージェントが判断するための共通契約です。ただし、記載されているだけでは統合ゲートになりません。可能な項目は、次の順に機械化します。

1. repository-specific testまたはvalidator
2. generatorのcheck modeと差分検査
3. 現在のcommitを対象とするCI status
4. required checkまたはrequired review
5. 操作直前のprecondition check

`agent-policy` 自体は、生成された指示とlock fileの整合性を検査します。製品固有の不変条件や受入試験は、製品リポジトリのテストとCIで強制します。

## coreへ含めない項目

次の知見は有用ですが、適用条件が技術領域に依存するため、現時点では普遍的なcore規約には含めません。

- 非同期UIでrequest IDまたは選択対象を各`await`後に再確認すること
- 補助的な表示機能を基礎機能より先に待たないこと
- fail-openとfail-closedの具体的な選択
- CODEOWNERSや特定reviewerの必須化
- 全platform、全package、全test suiteの一律実行
- fuzz test、形式手法、特定coverage値の一律必須化
- 特定のarchive形式、hash algorithm、署名方式の一律強制

これらは、frontend、workflow、database、release、security、artifact intakeなどのdomain profile、または製品リポジトリ固有のpolicyとして追加する方が適切です。

## タスク固有契約の最小形

恒久規約とは別に、個々のタスクでは次の情報を明示すると、core規約を具体化できます。

```text
Outcome:
Allowed changes:
Preserved invariants:
Non-goals:
Acceptance evidence:
Destructive or externally visible actions:
Stop condition:
```

この契約は恒久規約へ蓄積せず、issue、pull request、作業指示、または一時的な作業文書で管理します。
