# Agent Skill first-use walkthrough

> **参考訳（非正本）:** この文書は英語版 `docs/guides/skill-first-use-walkthrough.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

これは Composition で Agent Skill を作成する canonical first-use walkthrough です。Composition architecture を先に読むのではなく、小さな reusable workflow を作る目的なら上から順に進めます。

例は **Release Note Helper** です。repository change summary から repository-owned writing guide に従って release notes を作る `knowledge-augmented` Skill であり、application runtime、CLI、MCP、browser interface、headless service は不要です。

## 0. この walkthrough で何を作るか

`TakashiSasaki/templates` の中ではなく、**別 consumer repository** に Skill を作ります。Composition を使うためだけに `TakashiSasaki/templates` を clone する必要もありません。

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
doctor
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

**Repository change:** consumer repository 自体を作成します。ここで Git を使うのは通常の version-controlled product repository を作るためであり、Composition consumer runner の prerequisite だからではありません。

## 2. Prerequisite を確認する

通常の Composition consumption に必要なのは CPython 3.11–3.14 です。Composition runner 自体に Git は不要で、templates checkout も不要です。

```sh
python --version
```

Python が 3.11–3.14 を報告することを確認します。cold runner execution では GitHub への HTTPS access が必要で、matching Python runtime cache が無ければ configured Python package source への access も必要です。

## 3. Composition を install する

review 済み immutable installer を使用します。stable release は installer full-SHA identity と SHA-256 digest の両方を公開しているため、downloaded bytes を write / execute する前に digest を検証します。

```sh
python -I -c '
import hashlib
import pathlib
import subprocess
import sys
import tempfile
import urllib.request

url = "https://raw.githubusercontent.com/TakashiSasaki/templates/b862171ed7d8fb7f53cb5a28a0d89eab07ab534e/scripts/install_composition_skill.py"
expected = "161b9fb7f432eec8cb104f4f49d945c7f8ef5654382fb4607a13ae0de5015cc4"
data = urllib.request.urlopen(url, timeout=30).read()
actual = hashlib.sha256(data).hexdigest()
if actual != expected:
    raise SystemExit(f"installer SHA-256 mismatch: expected {expected}, got {actual}")
print(f"Verified Composition installer SHA-256: {actual}")
with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as handle:
    handle.write(data)
    installer = pathlib.Path(handle.name)
try:
    subprocess.run([sys.executable, "-I", str(installer), *sys.argv[1:]], check=True)
finally:
    installer.unlink(missing_ok=True)
' /absolute/path/to/agent-skills/composition
```

digest mismatch では installer bytes を書き出す前かつ installer process を起動する前に終了します。出力される verified digest は audit evidence として保存できます。既存 destination にこの Composition skill がある場合は `--replace` を追加できます。`SKILL.md` によって `composition` skill と識別できない directory の replacement は拒否されます。

**Expected:** `/absolute/path/to/agent-skills/composition/scripts/run.py` が存在します。

Release Note Helper repository には変更ありません。Composition Skill と runtime/validation cache は consumer repository 外にあり、selected Composition source は ephemeral full-SHA archive snapshot として使われ、templates checkout として保持されません。

full SHA は reviewed immutable-source identity を固定し、SHA-256 は実際に受信した installer bytes を execution 前に検証します。この2つは別の check です。詳細は [Using Composition](../consumer-guide.md#immutable-source-snapshots-and-runtime-reuse) を参照してください。

最初の Composer execution 前に local bootstrap readiness を確認するには read-only `doctor` を実行します。

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/release-note-helper \
  doctor
```

`doctor --format json` では machine-readable diagnostics を取得できます。doctor は selected immutable revision、supported CPython、effective runtime-cache path、acquisition mode を確認します。normal consumer の Git は `not-required`、source acquisition は ephemeral full-SHA archive と報告されます。GitHub や package index には接続せず、source/runtime acquisition も行いません。runtime cache の transient write/atomic-rename probe は実行して後始末しますが、persistent source checkout は作りません。

したがって `READY` は local bootstrap diagnosis であり、Composition validation の成功や cold acquisition の network/package availability を保証するものではありません。

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
- `doctor` で local bootstrap readiness を read-only に確認できる。
- `composition.json` selects minimal `skill` recipe。
- `inspect -> plan -> review -> apply -> validate` を正しい順序で実行。
- plan が read-only と理解。
- seed / managed / ordinary consumer ownership を理解し、active seed destination を lock にある間保持。
- concrete-completion gate が `template-scaffold` と template TODO の除去を確認。
- `references/release-note-style.md` が実在。
- Skill-specific / Composition validation が pass。
- 次の作業が behavioral evaluation であると分かる。

exact lifecycle/recovery rules は [Using Composition](../consumer-guide.md) と [Composer reference](../reference/composer.md) を使用してください。
