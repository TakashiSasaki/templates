# Getting started

> **参考訳（非正本）:** この文書は英語版 `docs/getting-started.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

このページは、既存 Git repository に coding-agent operating rules を追加するための first-use path です。最初の dry run を実行する前に、Policy trust model、3種類の SHA identity、runtime-cache internals を理解する必要はありません。

最初の分岐は単純です。

```text
AGENTS.md / CLAUDE.md / GEMINI.md / Copilot instructions がない
        ↓
fresh adoption

既存 agent instructions がある
        ↓
migration adoption
```

ただし route を自分で推測して選ぶ必要はありません。bootstrap dry run が repository を inspect して state を判定します。

## 0. この workflow が変更するもの

Policy は coding-agent operating rules の独立 authority です。Composition capability ではありません。Composition を使う repository を含め、適切な Git repository に Policy を独立して adopt できます。

successful adoption 後の主要 ownership boundary は次です。

- **人間が編集する:** `.agent-policy.yml` と `policy/project.md` などの product-specific policy。
- **Policy toolchain が管理する:** `.agent-policy.lock`、rendered `AGENTS.md`、generated validation skills。
- migration preparation 中は existing primary agent instructions を保持し、明示的な finalize までは cutover しない。

最短 first-use path:

```text
prerequisites を確認
  ↓
agent-policy skill を install
  ↓
bootstrap dry run / inspect
  ↓
  ├─ unmanaged-empty    → fresh adoption
  └─ unmanaged-existing → migration adoption
  ↓
human-owned Policy input を編集
  ↓
render → validate → check
```

## 1. Prerequisites を確認する

target は既存 Git repository でなければなりません。Python 3.11 以降と Git が必要です。

**Run**

```bash
git --version
python --version
```

**Expected**

両方が成功し、target repository が `/path/to/product-repository` のような path で利用できます。

**Repository change**

なし。

**Next**

product repository の外に single `agent-policy` skill を install します。

## 2. `agent-policy` skill を install する

published immutable installer を使います。

**Run**

```bash
python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/TakashiSasaki/templates/bad638f58c74a12078d4e02bca62151a7bb86dea/scripts/install_agent_policy_skill.py', timeout=30).read())" /path/to/agent-skills/agent-policy
```

既存 `agent-policy` skill installation を意図的に置換する場合だけ `--replace` を追加します。

**Expected**

installed skill に `scripts/bootstrap.py` と `scripts/run.py` が存在します。

**Repository change**

product repository には変更なし。skill installation は `agent-policy` executable を global `PATH` に install する操作ではありません。

**What this means**

通常の consumer entry point が使える状態です。full-SHA installer は意図的です。immutable-source / runtime-cache trust model の詳細は後の [Trust and runtime details](#trust-and-runtime-details) で説明します。

**Next**

bootstrap inspection を実行します。default は dry run です。

## 3. Dry run で repository を inspect する

installed skill directory から実行します。

**Run**

```bash
python scripts/bootstrap.py \
  --repository /path/to/product-repository
```

**Expected**

bootstrap が pinned runtime を通じて `agent-policy adopt inspect` を実行し、target を次のいずれかに分類します。

- `unmanaged-empty` — existing instructions なし。**fresh adoption** を使う。
- `unmanaged-existing` — existing instructions または policy が存在。**migration adoption** を使う。
- `managed` — `.agent-policy.yml` と managed state が存在。first-time adoption をせず `scripts/run.py` を使う。
- `inconsistent` — partial adoption、orphaned generated artifacts、unsafe paths、その他 inconsistent state。continue 前に repair が必要。

**Repository change**

なし。`--apply` のない bootstrap は dry run です。

**What this means**

`init` / `adopt` route を手動選択しません。inspection が repository state から supported next transition を導出します。

**Next**

- `unmanaged-empty` → [4A. Fresh adoption](#4a-fresh-adoption)
- `unmanaged-existing` → [4B. Migration adoption](#4b-migration-adoption)
- `managed` → Section 6 の managed repository workflow へ進む。
- `inconsistent` → first-use adoption を停止し、toolchain が報告する diagnostic/recovery guidance に従う。

## 4A. Fresh adoption

inspection が `unmanaged-empty` を返した場合の branch です。

### Mutation 前に review する

Section 3 の dry run が adoption plan です。target と proposed changes を確認します。

### Fresh adoption を apply する

**Run**

```bash
python scripts/bootstrap.py \
  --repository /path/to/product-repository \
  --apply
```

**Expected**

pinned toolchain は fresh-adoption primitive として内部的に `agent-policy init` を使う場合がありますが、その後同じ runtime で validation/check の成功を要求します。Initialization は別 user-facing onboarding step ではありません。

主な created files:

```text
.agent-policy.yml
.agent-policy.lock
policy/project.md
AGENTS.md
.agents/skills/validate-agent-policy/SKILL.md
```

**Repository change**

あり。first mutating Policy step です。

**What this means**

- `.agent-policy.yml` は human-owned configuration。
- `policy/project.md` は human-owned product-specific policy input。
- `.agent-policy.lock`、rendered `AGENTS.md`、generated validation skills は tool-managed output/state。

**Next**

baseline profiles を確認し、必要なら human-owned Policy input を編集して Section 6 へ進みます。

## 4B. Migration adoption

inspection が `unmanaged-existing` を返した場合の branch です。

migration は意図的に2段階です。**prepare / preview を先に行い、semantic review 後だけ finalize cutover** します。

### 必要なら authoritative existing instruction を選ぶ

`AGENTS.md`、`CLAUDE.md`、`GEMINI.md`、`.github/copilot-instructions.md` の supported instruction が1つだけ見つかれば自動選択されます。

複数存在する場合は authoritative primary を明示します。

**Run**

```bash
python scripts/bootstrap.py \
  --repository /path/to/product-repository \
  --primary-instructions AGENTS.md
```

1つだけで自動選択された場合は `--primary-instructions` を省略します。supported instruction が1つもない場合、まず supported instruction file を1つ作成します。policy/skill assets だけを primary instructions として選択できません。

**Repository change**

なし。`--apply` がなければ dry run のままです。

### Migration preparation を apply する

plan review 後:

```bash
python scripts/bootstrap.py \
  --repository /path/to/product-repository \
  --primary-instructions AGENTS.md \
  --apply
```

primary が自動選択された場合は `--primary-instructions` を省略します。

**Expected**

existing primary instruction は **replace されません**。bootstrap は prepared Policy state を作り `adopt preview` を実行します。

**What this means**

Policy は free-form existing instructions を自動的に policy へ変換しません。意図した semantics を human-owned `policy/project.md` と必要な他の Policy input に表現します。

### Policy edit ごとに preview を refresh / review する

migration preparation 中に human-owned Policy input を変更したら:

```bash
python scripts/run.py \
  --repository /path/to/product-repository \
  adopt preview
```

regenerated preview と handwritten primary instruction の semantic difference を review します。last preview 後に Policy input が変わった場合 `adopt finalize` は stale preview を拒否します。`STALE_OUTPUT` を generated state の bypass/hand-edit 理由にしません。

### Semantic review 後だけ finalize する

まず finalization dry run:

```bash
python scripts/run.py \
  --repository /path/to/product-repository \
  adopt finalize
```

review 後、明示的に mutate:

```bash
python scripts/run.py \
  --repository /path/to/product-repository \
  adopt finalize --apply
```

generic bootstrap `--apply` は migration finalization を実行できません。

**Next**

normal managed workflow へ進みます。

## 5. Baseline profile を選び human-owned Policy input を編集する

Policy profiles は context に参加する shared policy module を選択します。通常の coding/maintenance repository の baseline は:

```text
core
security-baseline
```

baseline profile は `core` と `security-baseline` です。normal bootstrap path は fresh adoption / migration preparation の両方でこの2つを使います。

operation-specific profile は実際にその operation を行う context だけに追加します。

- `pull-request` — pull-request lifecycle work を所有する context。
- `review` — blocking defect の review を行う context。
- `external-artifact-intake` — externally produced artifact を receive/stage する context。

fresh adoption は baseline profiles を持つ `.agent-policy.yml` を作ります。追加 context/profile が必要ならこの human-owned file を編集します。product-specific invariants、compatibility requirements、verification methods は canonical shared policy を copy/edit するのではなく `policy/project.md` に置きます。

完全な catalog / composition semantics は [Policy profiles](shared-policy/profiles.md) を参照してください。

## 6. Managed repository を render / validate / check する

`.agent-policy.lock` が存在したら installed `scripts/run.py` を使います。

**Run**

```bash
python scripts/run.py --repository /path/to/product-repository render
python scripts/run.py --repository /path/to/product-repository validate
python scripts/run.py --repository /path/to/product-repository check
```

**Expected**

- `render` — human-owned Policy input から tool-managed rendered instruction output を更新。
- `validate` — Policy structure/managed state を検証。
- `check` — rendered/locked Policy expectations に対して repository を検証。

**Repository change**

`render` は generated Policy output を更新する場合があります。`validate` / `check` は authoring ではなく verification operations です。

**What this means**

first-use loop は完了です。human-owned Policy input を編集し、render、validate、check を繰り返します。migration preparation 中は normal rendered instruction を preview の代用にせず、Policy edit 後に `adopt preview` を regenerate します。

runner は skill default stable pin より repository `.agent-policy.lock` の full SHA を優先します。malformed/mutable toolchain pin は fail closed し、stable default に silent fallback しません。

## Trust and runtime details

以下は reproducibility / supply-chain trust に重要ですが、first dry-run command を決めるための prerequisite ではなく reference material です。

### 3つの immutable identities

3つの full-SHA identity は意図的に分離されています。

- **installer script revision** `bad638f58c74a12078d4e02bca62151a7bb86dea` — remotely executed installer。
- **skill source revision** `20cdbc720249516e3d30fc93e050391b81eaa6b4` — installed `skills/agent-policy/` subtree。
- installed `runtime-manifest.json` の **stable runtime revision** — canonical CLI runtime。

`release/skill-installer.json` は最初の2 identity を記録します。published command は `policy` branch、tag、abbreviated SHA を実行しません。

repository-development 用には reviewed checkout installation もあります。

```bash
python skills/agent-policy/scripts/install.py \
  /path/to/agent-skills/agent-policy
```

review 中 checkout から skill tree を install する path であり、checkout が `release/skill-installer.json` の skill-source revision と一致しない限り published remote distribution と byte-identical とは限りません。published distribution の再現が目的なら remote command を使います。

`runtime-manifest.json` は reviewed stable toolchain revision を full SHA で pin し、その revision の `requirements-runtime.lock` を SHA-256 で bind します。これらを `policy`、tag、abbreviated SHA に置き換えません。

CLI/adoption reference の direct `agent-policy ...` example は canonical toolchain CLI を説明するものです。normal consumer workflow は installed skill の `scripts/bootstrap.py` / `scripts/run.py` を使います。

### Runtime-cache behavior

runtime cache identity には full toolchain SHA、runtime-lock SHA-256、Python major/minor、platform が含まれます。valid cache entry は network access なしで再利用されます。

stable default では `runtime-manifest.json` が lock digest を記録しているため network access 前に cache identity を確認できます。managed repository が別 full SHA を選ぶ場合も、same revision/Python/platform の validated cache があれば offline reuse できます。なければその revision の runtime lock を1回取得し digest を計算し、新しい staged runtime を構築します。

## Review と commit

fresh adoption、migration preparation、preview、finalization、rendering、regeneration は Git commit/push を自動実行しません。generated diff を review し、product code と同じ normal review flow で commit します。

!!! note
    adoption 前後で同じ `agent-policy` skill を使います。adoption 前は reviewed runtime manifest が default trust seed、adoption 後は `.agent-policy.lock` が managed repository の toolchain revision authority になります。