# agent-policy

> **参考訳（非正本）:** この文書は `docs/overview.md` の日本語訳です。英語版が正本であり、内容に差異がある場合は英語版を優先します。

`agent-policy` は、複数の製品リポジトリと複数のコーディング／汎用エージェントで共有する規約を、検証可能かつ再現可能な形で管理するためのポリシーツールチェーンです。開発上の正本は `TakashiSasaki/templates` の `policy` ブランチです。

## ここから始める

製品リポジトリへ Policy を適用することが目的なら、最初に Provider / toolchain の内部構造を理解する必要はありません。通常の consumer workflow は次の順序です。

1. **単一の `agent-policy` skill をインストールする。** レビュー済み full-SHA installer は [Getting started](getting-started.md) に記載されています。
2. **未管理 repository を inspect する。** `python scripts/bootstrap.py --repository /path/to/product-repository` は dry run で `unmanaged-empty`、`unmanaged-existing`、`managed`、`inconsistent` のいずれかに分類し、対応する adoption path を選択します。
3. **plan を確認してから fresh adoption を apply、または migration を prepare する。** fresh adoption は `--apply` を使用できます。migration adoption は既存の primary instructions を保持し、preview 後に別の明示的 finalization を必要とします。
4. **managed repository を同じ installed skill で運用する。** `python scripts/run.py --repository . validate`、続いて `render`、`check` を実行します。

installation と adoption は [Getting started](getting-started.md) から始めてください。`.agent-policy.lock` が存在するようになった後は [Managed operation](managed-operation.md) で通常の validate / render / check loop を確認します。context にどの shared rule set を選ぶべきか判断するときは [Policy profiles](shared-policy/profiles.md) を参照してください。

Policy が制御するのは coding-agent の operating rules です。Web application、CLI、service、library などの **architecture や product requirements は定義しません**。それらの artifact / capability semantics は Composition が別の authority として管理します。

以下の節では、より深い architecture、provenance、maintenance context が必要な場合に Policy model と Provider 内部を説明します。

## 目的

- 共通規約を中央で一度だけ管理する
- 製品固有規約を各リポジトリに保持する
- `.agent-policy.yml` を単一の意味的設定入口にする
- 共通規約と製品固有規約を決定的に合成する
- `AGENTS.md` と通常運用スキルを生成してコミットする
- `.agent-policy.lock` に入力・出力ハッシュとツールチェーンの完全なコミットSHAを記録する
- 設定、lock、生成物の不整合をCIで検出する
- 既存instructionを破壊せずに導入準備・preview・明示的cutoverを行う
- adoption前後で同じinstalled `agent-policy` skillと検証済みpersistent full-SHA runtimeを使用する

## 区別すべき3つの層

`policy` という語は、リポジトリのbranch、branch内で正本として保持する共有規約、consumer repositoryで実際に有効になる規約を指し得ます。これらは別の層です。

1. **Provider / toolchain layer** — `TakashiSasaki/templates` の `policy` ブランチ全体です。共有規約だけでなく、`agent-policy` CLI、schema、renderer template、単一repository-facing skill、test、release machinery、maintainer documentationを保持します。このbranch自体がconsumer repositoryへmergeされて効力を持つわけではありません。
2. **Shared policy corpus layer** — `policy/` に置くcanonicalな共有規則と、`profiles/` に置く選択集合です。ここが複数repositoryで共有する規約意味論の正本です。規則はbranchに存在するだけではconsumerで有効にならず、consumer側の設定から選択されます。
3. **Consumer effective-policy layer** — consumer repositoryの `.agent-policy.yml` がshared profileとrepository-local policyを選択し、toolchainがそれらをcomposeして `AGENTS.md`、context output、通常運用skillなどへrenderした状態です。`.agent-policy.lock` は選択入力、toolchain revision、生成結果を固定します。実際のrepository作業で効力を持つのはこのconsumer側の選択・合成・生成結果です。

したがって、導入処理は `policy` ブランチ全体をconsumerへinjectまたはGit mergeする仕組みではありません。共有規則を **select → compose → render** し、consumer repositoryに生成projectionとlock stateを保持する仕組みです。branch間のunrelated historyは維持されます。

Index-guided navigationでもこの境界を維持し、[Provider and toolchain](provider/index.md)、[Shared policy corpus](shared-policy/index.md)、[Applying policy to a consumer repository](consumer/index.md) を別の入口として扱います。

## `policy`ブランチの構成

`policy`は、`templates`リポジトリの`skill`、`site`、`webapp`とはunrelated historyです。このbranch内で次を管理します。

| パス | 役割 |
|---|---|
| `policy/`, `profiles/` | application-type-independentな共有規約と適用集合 |
| `src/agent_policy/` | Python CLIとadoption transaction |
| `schemas/`, `templates/` | consumer設定・stateのschemaと生成template |
| `skills/agent-policy/` | unmanaged adoption、managed command dispatch、immutable pin selection、persistent runtime-cache管理を担う単一repository-facing skill |
| `tests/` | compiler、path safety、lock、adoption、release identity、runtime distribution、single-skill/cache boundaryの検証 |
| `docs/` | 導入、設計、ADR、publication資産 |

unmanaged repositoryでは `skills/agent-policy/runtime-manifest.json` がレビュー済みstable full-SHA trust seedとruntime-lock digestを提供します。adoption後は同じskillがconsumerの `.agent-policy.lock` に記録されたfull SHAを優先します。validなruntime cache entryはnetworkなしで再利用できます。

## 提供コマンド

```text
agent-policy adopt inspect
agent-policy adopt prepare
agent-policy adopt preview
agent-policy adopt finalize
agent-policy validate
agent-policy render
agent-policy check
```

- `adopt inspect`: repository stateをread-onlyで分類する
- `adopt prepare`: state-derived fresh/migration preparationを実行し、fresh adoptionでは必要に応じてhidden initializationを内部利用する
- `adopt preview`: staged migration outputを再生成・検査する
- `adopt finalize`: 別途明示的に許可されたmigration cutoverを実行する
- `validate`: 設定、参照、規則ID、path safetyなどを検査する
- `render`: 共通規約と製品固有規約を合成して生成物とlockを更新する
- `check`: 設定、入力、lock、生成物が一致しているかをread-onlyで確認する

installed skillのgeneric bootstrap操作はmigration finalizationを公開しません。finalizationは別の明示的managed commandです。

## 次に読むページ

- [Provider and toolchain](provider/index.md) — `policy`ブランチ自体とtoolchainの設計・保守・release boundaryをたどります。
- [Shared policy corpus](shared-policy/index.md) — consumerから選択されるcanonical shared policyとprofileをたどります。
- [Applying policy to a consumer repository](consumer/index.md) — adoption、configuration、effective policy、managed operationをたどります。
- [CLIリファレンス](cli.md) — `agent-policy` コマンドと各サブコマンドの契約を確認します。
- [Architecture decisions](adr/) — 現在有効なADRを短い説明付きで一覧します。
- [脅威モデル](threat-model.md) — toolchainが防御する脅威と信頼境界を確認します。
