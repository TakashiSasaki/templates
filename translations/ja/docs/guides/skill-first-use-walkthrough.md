# Agent Skill first-use walkthrough

> **参考訳（非正本）:** この文書は英語版 `docs/guides/skill-first-use-walkthrough.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

これは Composition で Agent Skill を作成する canonical first-use walkthrough です。Composition architecture を先に読むのではなく、小さな reusable workflow を作る目的なら上から順に進めます。

例は **Release Note Helper** です。repository change summary から repository-owned writing guide に従って release notes を作る `knowledge-augmented` Skill であり、application runtime、CLI、MCP、browser interface、headless service は不要です。

## 0. この walkthrough で何を作るか

`TakashiSasaki/templates` の中ではなく、**別 consumer repository** に Skill を作ります。

```text
TakashiSasaki/templates
        |
        | Composition tooling と Skill contracts を提供
        v
あなたの別 release-note-helper repository
```

```text
repository 作成
  ↓
Composition install
  ↓
composition.json
  ↓
inspect → plan → review → apply → validate
  ↓
valid Skill scaffold
  ↓
consumer-owned SKILL.md を concrete にする
  ↓
real references/ resource を追加
  ↓
concrete-completion check + Skill validation + Composition validation
```

initial scaffold が valid でも operational Skill ではありません。`template-scaffold` と TODO guidance を concrete semantics に置き換える必要があります。

## 1. Product repository を作る

```sh
mkdir /absolute/path/to/release-note-helper
cd /absolute/path/to/release-note-helper
git init
```

**Expected:** 独立 Git repository が存在し、`.template-composition/lock.json` はまだありません。

**Repository change:** consumer repository 自体を作成します。

## 2. Prerequisites を確認する

```sh
git --version
python --version
```

Git と CPython 3.11–3.14 が必要です。

## 3. Composition を install する

```sh
python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/TakashiSasaki/templates/9c1c093fca1e7e47a9974150e7739665ec570f6e/scripts/install_composition_skill.py', timeout=30).read())" /absolute/path/to/agent-skills/composition
```

**Expected:** `/absolute/path/to/agent-skills/composition/scripts/run.py` が存在します。

Release Note Helper repository には変更ありません。full SHA は reviewed immutable-source model のためです。

## 4. `composition.json` を作る

knowledge reference は Skill-owned resource なので application capability を追加せず、minimal `skill` recipe を使います。

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

同じ machine-checked example は `examples/onboarding/release-note-helper/composition.json` にあります。agent が Skill を実行するという理由だけで `capability.runtime` を選びません。

## 5. Inspect

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/release-note-helper \
  inspect
```

new directory なら `state: "unmanaged"` が期待されます。`inspect` は read-only です。managed state なら fresh initial として進めず、[Using Composition](../consumer-guide.md#check-whether-a-repository-is-managed) を使います。

## 6. Plan と review

absolute `--config` を使います。relative `--config` は `--repository` ではなく process current working directory 基準です。

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/release-note-helper \
  plan --config /absolute/path/to/release-note-helper/composition.json
```

`operation: "initial"`、resolved components、`actions`、empty `conflicts`、`lock_preview` を確認します。Planning is read-only です。理解できない conflict があれば apply しません。

## 7. Apply

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/release-note-helper \
  apply --config /absolute/path/to/release-note-helper/composition.json
```

**Expected:** `status: "applied"` と `.template-composition/lock.json`。

**Repository change:** Composition が Skill scaffold を materialize します。

## 8. Scaffold を validate する

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/release-note-helper \
  validate
```

**Expected:** `status: "valid"`。

これは Composition state / Skill scaffold structure が valid という意味です。`SKILL.md` が `template-scaffold` と TODO guidance のままでも初期 scaffold としては valid です。Skill validator もこの sentinel を意図的に許容するため、後で concrete-completion check を別に実行します。

## 9. 編集可能なものを具体的に確認する

`.template-composition/lock.json` を読みますが hand-edit しません。

| File | Ownership | Action |
| --- | --- | --- |
| `SKILL.md` | `seed` | **in-place で編集する。** concrete Skill contract にする。 |
| `README.md` | `seed` | **in-place で編集する。** consumer repository を説明する。 |
| `AGENTS.md` | `seed` | 必要なら **in-place で編集する。** |
| `.editorconfig`, `.gitignore`, `LICENSE.template` | `seed` | bytes は consumer-owned だが、lock に active entry として残る間は destination を保持する。削除/rename せず in-place edit する。別 `LICENSE` の追加は可能。 |
| `.github/workflows/validate-skill.yml` | `managed` | **hand-edit しない。** |
| `.github/scripts/validate_skill.py` | `managed` | **hand-edit しない。** |
| `docs/index.md`, `docs/architecture.md`, `docs/skill-capability-map.md`, `docs/skill-profiles.md` | `managed` | **hand-edit しない。** |
| `.template-composition/validate.py` など | `managed` | **hand-edit しない。** |
| `.template-composition/lock.json` | Composer state | **hand-edit しない。** |
| 新規 `references/`, `assets/`, `scripts/` | ordinary consumer content | 必要に応じ通常どおり作成・編集する。 |

`seed` は initial composition 後に consumer-owned bytes になりますが、active seed destination は resolved Composition state の一部なので lock にある間は存在し続ける必要があります。path 自体を Composition state から除去・rename したい場合は local delete ではなく explicit source/upgrade transition とします。

## 10. `SKILL.md` を Release Note Helper にする

frontmatter と TODO section を concrete semantics に置き換えます。

```yaml
---
name: release-note-helper
description: Draft concise repository release notes from a supplied change summary or diff, following the repository-owned release-note style reference.
---
```

本文では trigger、非適用条件、required inputs、workflow、output、validation、安全性を具体化します。Operational knowledge section に次を宣言します。

```text
Reference: references/release-note-style.md
Read when: every invocation that drafts release-note text
Provides: release-note structure, tone, and inclusion/exclusion rules
Authority or freshness notes: repository-owned guidance; update deliberately when release style changes
```

sentinel は次へ置き換えます。

```text
Selected profiles: knowledge-augmented
```

未使用 Assets / Helper scripts / Public execution interfaces section と template TODO を残しません。

## 11. 実在する consumer-owned resource を追加する

`references/release-note-style.md` を作ります。

```markdown
# Release note style

- Lead with user-visible behavior, not internal implementation detail.
- Group changes under Added, Changed, Fixed, or Removed only when the evidence supports that category.
- State breaking changes and required migration actions explicitly.
- Do not claim performance, security, compatibility, or bug fixes without evidence in the supplied changes.
- Prefer concise bullets; omit empty sections.
```

これは Composition が materialize していない **ordinary consumer content** です。

## 12. Concrete completion を確認してから Skill を validate する

structural Skill validator は fresh scaffold を valid starting state として扱うため `template-scaffold` を意図的に許容します。operational Release Note Helper と呼ぶ前に consumer-owned completion gate を実行します。

```sh
if grep -q 'Selected profiles: template-scaffold' SKILL.md; then
  echo 'SKILL.md still selects template-scaffold' >&2
  exit 1
fi
if grep -q '\bTODO\b' SKILL.md; then
  echo 'SKILL.md still contains template TODO guidance' >&2
  exit 1
fi
```

silent success なら sentinel / template TODO は置換済みです。この gate が **concrete completion** を確認し、provider structural validator とは役割が異なります。

次に Skill validator:

```sh
python .github/scripts/validate_skill.py .
```

undeclared/missing resource や incompatible profile/resource shape があれば consumer-owned material を直し、validator を hand-edit しません。structural validation だけを sentinel replacement の証明にしないでください。

最後に full Composition validation:

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/release-note-helper \
  validate
```

**Expected:** `status: "valid"`。initial scaffold と違い、この結果は explicit completion gate と組み合わせて concrete Skill completion を示します。

## 13. Skill behavior を exercise する

contract validation は useful output をあらゆる agent/runtime で証明するわけではありません。少なくとも以下を実利用環境で試します。

1. clear user-visible additive change。
2. breaking/migration implication を含む change。
3. feature と誇張してはいけない internal refactor。
4. evidence 不足時に claim を捏造せず uncertainty を報告するケース。

必要なら consumer-owned evaluation を自動化します。

## 14. 本当に必要な capability だけ追加する

later Skill が maintained runtime、packaged CLI、MCP、MCP App、standalone browser、headless service を持つ場合だけ corresponding `capability.*` を `composition.json` に追加します。application interface を Skill profile name として表現しません。intent/component change は explicit `upgrade` の対象です。

## 15. Optional Policy adoption

Policy は Composition から独立しており、Skill profile / Composition capability ではありません。coding agents が Release Note Helper repository を保守する場合は [Policy getting-started guide](https://templates.moukaeritai.work/policy/getting-started/) を使います。Composition は `.agent-policy.yml`、`.agent-policy.lock`、`.agent-policy/**` を所有しません。

## 16. Ordinary maintenance

`SKILL.md`、`references/release-note-style.md`、examples、consumer-owned evaluation の変更は ordinary product work です。relevant change 後は concrete-completion gate、Skill validator、Composition validation を実行します。

unchanged intent で compatible Composition source revision へ移るなら `update`、recipe/components/parameters や component-version boundary を変えるなら explicit `upgrade` を使います。plan review を先に行い、lock を hand-edit して成功させません。

## Completion criteria

first-use success:

- separate consumer repository。
- Composition が repository 外に install 済み。
- minimal `skill` recipe の `composition.json`。
- `inspect -> plan -> review -> apply -> validate` を正しい順序で実行。
- plan が read-only と理解。
- seed / managed / ordinary consumer ownership を理解し、active seed destination を lock にある間保持。
- concrete-completion gate が `template-scaffold` と template TODO の除去を確認。
- `references/release-note-style.md` が実在。
- Skill-specific / Composition validation が pass。
- 次の作業が behavioral evaluation であると分かる。

exact lifecycle/recovery rules は [Using Composition](../consumer-guide.md) と [Composer reference](../reference/composer.md) を使用してください。