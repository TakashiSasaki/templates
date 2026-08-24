# Agent Skill first-use walkthrough

> **参考訳（非正本）:** この文書は英語版 `docs/guides/skill-first-use-walkthrough.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

これは Composition で Agent Skill を作成するための canonical first-use walkthrough です。Composition architecture を先に理解するのではなく、小さな再利用可能 agent workflow を作ることが目的なら、このページを上から順に進めます。

例は **Release Note Helper** です。repository change summary から簡潔な release note を作成し、repository-owned writing guide を参照する `knowledge-augmented` Skill とします。application runtime、CLI、MCP server、browser interface、headless service は不要です。

## 0. この walkthrough で何を作るか

Skill は **別 consumer repository** に作成します。`TakashiSasaki/templates` の内部へ実装しません。

```text
TakashiSasaki/templates
        |
        | Composition tooling と Skill contracts を提供
        v
あなたの別 release-note-helper repository
```

到達する経路は次です。

```text
repository を作る
  ↓
Composition を install
  ↓
composition.json を作る
  ↓
inspect → plan → review → apply → validate
  ↓
valid Skill scaffold
  ↓
consumer-owned SKILL.md を編集
  ↓
実在する references/ resource を追加
  ↓
Skill validation + Composition validation
```

initial scaffold が valid でも operational Skill ではありません。`template-scaffold` sentinel と TODO guidance を、具体的な trigger、workflow、resource、output、validation、安全性へ置き換える必要があります。

## 1. Product repository を作る

**Run**

```sh
mkdir /absolute/path/to/release-note-helper
cd /absolute/path/to/release-note-helper
git init
```

**Expected**

独立した Git repository が存在し、`.template-composition/lock.json` はまだありません。

**Repository change**

あり。consumer repository 自体を作りました。Composition はまだ materialize していません。

**Next**

prerequisites を確認します。

## 2. Prerequisites を確認する

Composition は `PATH` 上の Git と CPython 3.11–3.14 を support します。

**Run**

```sh
git --version
python --version
```

**Expected**

両方が成功し、Python が 3.11–3.14 を表示します。

**Repository change**

なし。

**Next**

consumer repository の外へ Composition を install します。

## 3. Composition を install する

reviewed immutable installer を使います。この例では `/absolute/path/to/agent-skills/composition` へ install します。

**Run**

```sh
python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/TakashiSasaki/templates/452cef1960612353b9ea206447b97a022ac1c2d7/scripts/install_composition_skill.py', timeout=30).read())" /absolute/path/to/agent-skills/composition
```

**Expected**

`/absolute/path/to/agent-skills/composition/scripts/run.py` が存在します。

**Repository change**

Release Note Helper には変更なし。Composition skill と runtime/validation cache は consumer repository 外に置かれます。

**What this means**

通常の repository-facing Composition runner が使える状態です。full SHA は reviewed immutable-source model を維持するため意図的です。installer/toolchain identity の詳細は [Using Composition](../consumer-guide.md#immutable-source-runtime-selection-and-cache-reuse) を参照してください。

**Next**

Skill composition intent を作ります。

## 4. `composition.json` を作る

Release Note Helper に必要なのは `skill` recipe baseline だけです。knowledge reference は Skill-owned resource であり application capability を要求しません。

`/absolute/path/to/release-note-helper/composition.json` を作成します。

```json
{
  "schema_version": 1,
  "recipe": "skill",
  "components": {
    "include": [],
    "exclude": []
  },
  "parameters": {}
}
```

同じ machine-checked example は Composition authority の `examples/onboarding/release-note-helper/composition.json` にあります。

agent がこの workflow を実行するという理由だけで `capability.runtime` を追加しないでください。application capability は maintained product interface/runtime behavior を表し、agent 自体がどこかで実行されることを表すものではありません。

**Repository change**

あり。`composition.json` は consumer-authored intent です。scaffold material はまだありません。

**Next**

target を inspect します。

## 5. Inspect

**Run**

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/release-note-helper \
  inspect
```

**Expected**

新規 directory なので JSON output は `state: "unmanaged"` を報告します。

**Repository change**

なし。`inspect` は read-only です。

**What this means**

Composition はこの repository をまだ manage していません。managed state が返る場合は fresh initial として扱わず、[Using Composition](../consumer-guide.md#check-whether-a-repository-is-managed) の existing-repository workflow を使います。

**Next**

initial composition を plan します。

## 6. Plan と review

first-use では absolute `--config` path を使い、process working directory への依存を避けます。relative `--config` は `--repository` ではなく process current working directory から解決されます。

**Run**

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/release-note-helper \
  plan --config /absolute/path/to/release-note-helper/composition.json
```

**Expected**

JSON plan が `operation: "initial"`、resolved Skill/lifecycle components、deterministic `actions`、empty `conflicts`、`lock_preview` を報告します。fresh repository では通常 `create`、byte-identical existing destination は `adopt-identical` になることがあります。

**Repository change**

なし。planning は read-only です。

**What this means**

mutation 前の fail-closed review point です。target、intent、actions、conflicts を確認します。理解できない conflict があれば apply しません。

**Next**

review した plan を apply します。

## 7. Apply

**Run**

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/release-note-helper \
  apply --config /absolute/path/to/release-note-helper/composition.json
```

**Expected**

JSON result が `status: "applied"` と `.template-composition/lock.json` を報告します。

**Repository change**

あり。Composition が Skill scaffold を materialize し、ownership を lock に記録します。

**Next**

customize 前に scaffold を一度 validate します。

## 8. Scaffold を validate する

**Run**

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/release-note-helper \
  validate
```

**Expected**

public JSON result が `status: "valid"` を報告します。

**What this means**

Composition state と Skill scaffold structure は valid です。しかし Release Note Helper が operational Skill になった意味ではありません。`SKILL.md` はまだ `template-scaffold` と TODO guidance を含みます。

**Next**

customize 前に ownership を確認します。

## 9. 編集可能なものを具体的に確認する

`.template-composition/lock.json` を読みますが、lock 自体は編集しません。

| File | Ownership | Action |
| --- | --- | --- |
| `SKILL.md` | `seed` | **編集する。** concrete Skill contract にする。 |
| `README.md` | `seed` | **編集する。** consumer Skill repository を説明する。 |
| `AGENTS.md` | `seed` | **必要なら編集する。** initial composition 後は consumer-owned。 |
| `.editorconfig`, `.gitignore`, `LICENSE.template` | `seed` | **通常の consumer material として編集・置換可能。** |
| `.github/workflows/validate-skill.yml` | `managed` | **hand-edit しない。** Composition-owned。 |
| `.github/scripts/validate_skill.py` | `managed` | **hand-edit しない。** そのまま使う。 |
| `docs/index.md`, `docs/architecture.md`, `docs/skill-capability-map.md`, `docs/skill-profiles.md` | `managed` | **hand-edit しない。** provider-owned reference。 |
| `.template-composition/validate.py` など | `managed` | **hand-edit しない。** |
| `.template-composition/lock.json` | Composer state | **hand-edit しない。** lifecycle operation が所有する。 |
| 新しい `references/`, `assets/`, `scripts/` | ordinary consumer content | profile が必要とする場合に **通常どおり作成・編集する。** |

`seed` は initial composition 後に consumer ownership へ移ります。`managed` は Composition-owned のままです。lock にない path は別 authority が定めない限り ordinary consumer content です。

## 10. `SKILL.md` を Release Note Helper にする

Release Note Helper は1つの maintained repository reference を読む **knowledge-augmented** Skill です。template frontmatter と TODO section を concrete semantics に置き換えます。

```yaml
---
name: release-note-helper
description: Draft concise repository release notes from a supplied change summary or diff, following the repository-owned release-note style reference.
---
```

本文では少なくとも次を concrete にします。

- **Use this skill when:** release notes/changelog text を求められ、relevant changes が提示されている。
- **Do not use this skill when:** changes の捏造、release approval、repository/release state mutation を求められている。
- **Required inputs:** change summary/diff と `references/release-note-style.md`。
- **Workflow:** supplied changes を確認し、style reference を読み、user-visible changes を整理し、evidence があれば breaking/migration implication を明示し、draft 後に全 claim を input と照合する。
- **Output:** user が file change を明示しない限り release-note prose のみ。
- **Safety:** default read-only。Skill invocation だけを根拠に publish/repository mutation を行わない。
- **Validation:** factual claim が supplied repository evidence に対応し、style reference に従う。

Operational knowledge section に実在 reference を宣言します。

```text
Reference: references/release-note-style.md
Read when: every invocation that drafts release-note text
Provides: release-note structure, tone, and inclusion/exclusion rules
Authority or freshness notes: repository-owned guidance; update deliberately when release style changes
```

scaffold sentinel は次の1行へ置き換えます。

```text
Selected profiles: knowledge-augmented
```

concrete Skill が使わない Assets、Helper scripts、Public execution interfaces section は削除します。scaffold shape を保つためだけに TODO を残しません。

## 11. 実在する consumer-owned resource を追加する

`references/release-note-style.md` を作成します。例:

```markdown
# Release note style

- Lead with user-visible behavior, not internal implementation detail.
- Group changes under Added, Changed, Fixed, or Removed only when the evidence supports that category.
- State breaking changes and required migration actions explicitly.
- Do not claim performance, security, compatibility, or bug fixes without evidence in the supplied changes.
- Prefer concise bullets; omit empty sections.
```

この file は Composition が materialize していないため **ordinary consumer content** です。`knowledge-augmented` profile によりこの reference が Skill semantics 上必要になります。Skill validator は declared resource path と profile/resource structure の整合性を検査します。

## 12. Concrete Skill を validate する

まず focused Skill validator を実行します。

**Run**

```sh
python .github/scripts/validate_skill.py .
```

**Expected**

concrete frontmatter/profile/resource structure が accepted されます。stale `template-scaffold`、undeclared/missing resource、incompatible profile/resource shape が報告された場合は consumer-owned Skill material を修正し、validator を編集しません。

次に full selected Composition validation を実行します。

**Run**

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/release-note-helper \
  validate
```

**Expected**

public result が `status: "valid"` を報告します。

**What this means**

concrete Skill contract と real supporting knowledge が存在し、selected Skill/Composition contracts に整合します。initial valid scaffold と異なり、scaffold sentinel/TODO semantics を置き換えた後の validation です。

## 13. Skill behavior を exercise する

Composition validation は repository contract を検査しますが、あらゆる agent/runtime で useful release note が生成されることまでは証明しません。

少なくとも次を実利用環境で試します。

1. 明確な user-visible additive change。
2. breaking/migration implication を含む change。
3. user-visible feature と誇張してはいけない internal refactor。
4. evidence が不足し、claim を捏造せず uncertainty を報告すべきケース。

重要度が高まったら consumer repository に product-specific evaluation を記録・自動化します。

## 14. 本当に必要になったときだけ capability を追加する

この例は knowledge-augmented / instruction-driven のままです。後で maintained helper runtime、packaged CLI、MCP interface、MCP App、standalone browser interface、headless service を持つなら、`composition.json` を明示的に変更して対応する Composition capability を選択します。

application interface を Skill profile name として表現しません。Skill profile は Skill-specific resource structure、capability は maintained application/runtime/interface behavior を表します。

意図的な component/intent change は ordinary consumer edit ではなく `upgrade` の対象です。

## 15. Optional Policy adoption

Policy は Composition から独立しています。Skill profile でも Composition capability でもありません。

coding agent が Release Note Helper repository 自体を保守する場合は initial Composition materialization 後に [Policy getting-started guide](https://templates.moukaeritai.work/policy/getting-started/) から adopt します。Composition は `.agent-policy.yml`、`.agent-policy.lock`、`.agent-policy/**` を所有しません。

## 16. Ordinary maintenance

`SKILL.md`、`references/release-note-style.md`、example、consumer-owned evaluation の変更は ordinary product work です。relevant change 後は Skill validator と Composition validation を実行します。

normalized intent を変えず compatible な新しい Composition source revision へ移る場合は `update`、recipe/components/parameters を変更する場合や component-version compatibility boundary を越える場合は explicit `upgrade` を使います。mutation 前に plan を review し、成功を装うため lock を hand-edit しません。

## Completion criteria

architecture を先に読まず、次へ到達できれば first-use success です。

- Release Note Helper が別 consumer repository にある。
- Composition が repository 外に install されている。
- `composition.json` が minimal `skill` recipe を選ぶ。
- `inspect -> plan -> review -> apply -> validate` を正しい順序で進めた。
- `plan` が read-only と理解している。
- concrete seed/managed/ordinary-consumer ownership を区別できる。
- `SKILL.md` の selected profile が `template-scaffold` ではない。
- `references/release-note-style.md` が実在する declared resource である。
- Skill-specific validation と full Composition validation が pass する。
- 次に行うのが scaffold の探索ではなく concrete Skill behavior の evaluation だと分かる。

exact lifecycle/recovery rules は [Using Composition](../consumer-guide.md) と [Composer reference](../reference/composer.md) を参照します。Skill profile model と artifact/capability boundary は consumer repository に materialize される managed references を参照してください。
