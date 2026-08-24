# Webapp product walkthrough

> **参考訳（非正本）:** この文書は英語版 `docs/guides/webapp-product-walkthrough.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

これは Composition で Web アプリケーションを作成するための canonical な first-use walkthrough です。この repository を初めて使う場合は、Composition architecture を先に読む必要はありません。このページを上から順に進めてください。

例として扱う product は **Task Ledger** です。最終的には、task の作成・一覧・編集・完了・削除・filter を行う browser UI、永続化、browser とは独立して利用できる HTTP JSON API、`list` / `export` を提供する小さな CLI を実装します。

Composition が提供するのは contracts、managed validation material、deterministic lifecycle です。product の framework、database、API implementation、deployment platform、product test system は選びません。後半で Python と SQLite を使うのは Task Ledger の具体的な product decision にすぎません。

## 0. この walkthrough で何を作るか

`task-ledger` という **別 product repository** を作成します。`TakashiSasaki/templates` を clone し、その中に Task Ledger を実装し始めるのではありません。通常の関係は次のとおりです。

```text
TakashiSasaki/templates
        |
        | Composition tooling と contracts を提供
        v
あなたの別 task-ledger product repository
```

最初の milestone では次の状態に到達します。

```text
別 product repository
        ↓
repository の外に Composition を install
        ↓
composition.json
        ↓
inspect → plan → review → apply → validate
        ↓
valid な Composition scaffold
        ↓
明確な editing boundary と product development の開始地点
```

最初の `VALID` scaffold は、Web アプリケーションが実装済み・product-tested であるという claim では**ありません**。後半では同じ repository を使って、実際の product code、product verification、implementation evidence、optional Policy adoption、通常の Composition maintenance まで進めます。

以下の command 例は POSIX shell syntax と `/absolute/path/to/task-ledger` のような絶対 placeholder path を使います。他の shell / OS では directory 作成操作を相当するものに置き換えてください。ただし Python runner の argument semantics は同じです。特に first-use の canonical 例では `--repository` と `--config` に absolute path を使い、path resolution を推論しなくてよい形にします。

## 1. 別 product repository を作る

`TakashiSasaki/templates` checkout の**外側**に通常の development location を選びます。

**Run**

```sh
mkdir /absolute/path/to/task-ledger
cd /absolute/path/to/task-ledger
git init
```

**Expected**

- `/absolute/path/to/task-ledger` が独立した Git repository として存在する。
- `.template-composition/lock.json` はまだ存在しない。

**Repository change**

あり。この操作では product repository 自体を作成します。Composition material はまだ追加されません。

**What this means**

Task Ledger が consumer repository です。`TakashiSasaki/templates` は Composition / Policy authority の provider のままであり、これから実装する application repository ではありません。

**Next**

Composition runner の2つの prerequisite を確認します。

## 2. Prerequisites を確認する

supported runner prerequisites は、`PATH` 上の Git と CPython 3.11、3.12、3.13、3.14 です。

**Run**

```sh
git --version
python --version
```

**Expected**

- Git が version を表示して正常終了する。
- Python が 3.11 から 3.14 のいずれかを表示する。

**Repository change**

なし。

**What this means**

この環境で supported immutable Composition installer / runner を実行できます。sandbox / CI などで通常の user cache が writable でない場合は、最初の runner invocation 前に product repository 外の writable directory を `COMPOSITION_RUNTIME_CACHE` / `COMPOSITION_VALIDATION_CACHE` に設定してください。詳細は [Using Composition](../consumer-guide.md#install-and-run-the-composition-skill) にあります。

**Next**

Task Ledger の外側に published Composition skill を install します。

## 3. Composition を install する

通常の consumer は reviewed immutable installer を使用します。product repository 外の installation directory を選びます。この walkthrough では `/absolute/path/to/agent-skills/composition` とします。

**Run**

```sh
python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/TakashiSasaki/templates/452cef1960612353b9ea206447b97a022ac1c2d7/scripts/install_composition_skill.py', timeout=30).read())" /absolute/path/to/agent-skills/composition
```

その destination に Composition skill がすでに存在する場合は、任意 directory を削除・上書きせず、[Using Composition](../consumer-guide.md#install-and-run-the-composition-skill) に記載された `--replace` workflow を使用してください。

**Expected**

`/absolute/path/to/agent-skills/composition/scripts/run.py` が repository-facing runner として存在する。

**Repository change**

Task Ledger には変更なし。skill は別に選択した destination へ install されます。その後の runner / validator cache も product repository 外に作成されます。

**What this means**

通常の consumer entry point を利用できる状態です。full-SHA installer URL は意図的です。Composition は mutable branch/tag ではなく reviewed immutable source identity を使います。installer / skill / toolchain の各 SHA role を理解しなくても先へ進めます。必要になった時点で [Using Composition](../consumer-guide.md#immutable-source-runtime-selection-and-cache-reuse) を参照してください。

**Next**

Task Ledger product repository に Composition intent file を作ります。

## 4. `composition.json` を作る

Task Ledger は Webapp baseline に加え、3つの caller-visible concern を意図的にサポートします。

| Requirement | Selection | Why |
| --- | --- | --- |
| Browser product UI | `webapp` recipe baseline | Webapp artifact が browser surface、route、visible state、viewport、Web-specific validation をすでに定義する。 |
| Python process と execution commands | `capability.runtime` | product が maintained application runtime を持つ。 |
| 独立 HTTP JSON API | `capability.service` | non-browser caller が browser UI なしで API を利用できる。 |
| maintained `list` / `export` CLI | `capability.cli` | CLI が supported caller-visible interface である。 |

process や port を共有していても caller-visible contracts は統合されません。逆に、implementation 内部で process、route、library を使うという理由だけで capability を選ばないでください。

`/absolute/path/to/task-ledger/composition.json` を次の内容で作成します。

```json
{
  "schema_version": 1,
  "recipe": "webapp",
  "components": {
    "include": [
      "capability.cli",
      "capability.runtime",
      "capability.service"
    ],
    "exclude": []
  },
  "parameters": {}
}
```

同じ machine-checked example は Composition authority の `examples/onboarding/task-ledger/composition.json` に保存されています。recipe dependency closure が required lifecycle components を追加します。closure を説明する目的だけで required components を `include` に重複記載しないでください。

**Expected**

Task Ledger product repository root に `composition.json` が存在する。

**Repository change**

あり。`composition.json` は consumer が作成した intent です。Composition scaffold material はまだ作られていません。

**What this means**

作りたい artifact と externally supported capabilities を宣言しました。repository mutation はまだ要求していません。

**Next**

target state を inspect します。

## 5. Repository を inspect する

**Run**

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  inspect
```

**Expected**

先ほど directory を作り、Composition lock は存在しないため、JSON output には次が含まれます。

```json
{
  "state": "unmanaged"
}
```

実際の output には absolute `target` も含まれます。directory 作成前に inspect した場合は `absent` も正常な new-target state です。

**Repository change**

なし。`inspect` は read-only です。

**What this means**

Composition は現在この repository を manage していません。first-use として期待される状態です。

`managed-valid`、`managed-invalid`、`managed-interrupted` が表示された場合は、fresh initial composition として進めないでください。[Using Composition](../consumer-guide.md#check-whether-a-repository-is-managed) の state-specific workflow を使用します。特に interrupted repository は再初期化ではなく recovery が必要です。

**Next**

作成した configuration を使い initial materialization を plan します。

## 6. Initial materialization を plan する

canonical example では **absolute `--config` path** を使います。

**Run**

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  plan --config /absolute/path/to/task-ledger/composition.json
```

**Expected**

JSON plan には次が含まれます。

- `operation: "initial"`
- normalized `intent`
- resolved components
- fresh repository では通常 `create` が中心となる `actions`
- proceed 前に empty であるべき `conflicts`
- 記録予定 state を示す `lock_preview`

byte-identical な pre-existing destination は `create` ではなく `adopt-identical` と表示される場合があります。

**Repository change**

なし。initial planning は read-only であり、lock も scaffold も作りません。

**What this means**

mutation を許可する前に、complete deterministic mutation proposal を確認しています。

`--config` には重要な path rule があります。relative path は `--repository` ではなく **runner を起動した process current working directory** を基準に解決されます。上記の absolute path は、その関係を推論しなくてよいように意図的に使用しています。新しい `upgrade` の `--config` も同じです。

**Next**

plan を review します。configuration から直接 `apply` へ飛ばないでください。

## 7. Plan を review する

直前の command の `actions` と `conflicts` を確認します。

次を確認できたら進みます。

- target が `/absolute/path/to/task-ledger`
- recipe / component intent が選択したものと一致
- 各 action を理解している（fresh target なら `create` または意図した `adopt-identical`）
- `conflicts` が empty

conflict があれば、apply 前に destination に異なる bytes が存在する理由を解決します。Composition metadata を rename/delete して conflict を見えなくしないでください。

**Repository change**

なし。plan review は human decision point であり mutation step ではありません。

**What this means**

`plan` は intent と mutation の間にある fail-closed safety boundary です。

**Next**

review した intent をそのまま apply します。

## 8. Scaffold を apply する

**Run**

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  apply --config /absolute/path/to/task-ledger/composition.json
```

**Expected**

JSON result が `status: "applied"`、`operation: "initial"`、created/adopted destinations、`lock: ".template-composition/lock.json"` を報告します。

**Repository change**

あり。この walkthrough で初めて scaffold を materialize する Composition command です。planned files の installation と source-state validation に成功した後、`.template-composition/lock.json` が最後に書かれます。

**What this means**

Task Ledger は Composition-managed consumer repository になりました。materialized file ごとの ownership が lock に記録されています。

**Next**

product implementation を始める前に scaffold を validate します。

## 9. Scaffold を validate する

**Run**

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  validate
```

**Expected**

public JSON result が `status: "valid"` になります。selected-component checks には resolved component set が要求する Webapp / lifecycle validators が含まれます。implementation evidence は最初 `template` mode なので、product claim として asserted されるのではなく implementation-evidence check が deferred になります。

**Repository change**

product repository content は意図的には変更されません。cold validation は repository 外の isolated cache を作成・再利用する場合があります。

**What this means**

> **Composition validation: VALID** は resolved Composition state と template contracts が valid という意味です。Task Ledger が実装済み、product-tested、deployed、release-ready という意味では**ありません**。

これは safe scaffold と finished product の境界です。

**Next**

Composition が生成した file を編集する前に ownership を確認します。

## 10. Generated tree と editing boundary を確認する

`.template-composition/lock.json` を読みます。lock 自体は編集しません。各 materialized file の component owner、ownership mode、materialized digest が記録されています。

この Task Ledger configuration では、具体例は次のとおりです。

| File | Ownership | 何をするか |
| --- | --- | --- |
| `README.md` | `seed` | **編集する。** scaffold wording を Task Ledger 固有の内容に置き換える。 |
| `TEMPLATE.md` | `seed` | **編集する。** Webapp product contract を具体化する。 |
| `RUNTIME.md` | `seed` | **編集する。** 実際の runtime decision を記録する。 |
| `CLI_INTERFACE.md` | `seed` | **編集する。** supported `list` / `export` behavior を定義する。 |
| `SERVICE_INTERFACE.md` | `seed` | **編集する。** 独立して supported な JSON API を定義する。 |
| `contracts/routes.json`, `contracts/surfaces.json`, `contracts/ui-states.json`, `contracts/viewports.json` | `seed` | **編集する。** Task Ledger の browser contract を truthful にする。 |
| `contracts/implementation-evidence.json` | `seed` | **real proof ができてから編集する。** 最初は `template` mode のままにする。 |
| `contracts/manifest.json` | `generated` | **hand-edit しない。** Composition が deterministic に再生成する。 |
| `schemas/*.schema.json` | `managed` | **hand-edit しない。** Composition-owned のまま。 |
| `.github/workflows/validate-webapp.yml` | `managed` | **hand-edit しない。** Composition-owned validation wiring。 |
| `scripts/validate_contracts.py`, `scripts/scaffold_webapp_evidence.py` などの scaffold validator | `managed` | **hand-edit しない。** そのまま使用する。 |
| `.template-composition/validate.py` など `.template-composition` validator material | `managed` | **hand-edit しない。** |
| `.template-composition/lock.json` | Composer state | **hand-edit しない。** lifecycle operation が所有する。 |
| `task_ledger/server.py` や `tests/test_task_ledger.py` など新しい file | ordinary consumer content | **通常どおり作成・編集する。** product implementation であり Composition-owned ではない。 |

generic rule は、`seed` は initial materialization 後に consumer ownership へ移り、`managed` / `generated` は Composition-owned のまま、lock にない path は別 repository-local authority が定めない限り ordinary consumer content、です。

validation を回避するため managed schema/validator を product-owned variant として copy しないでください。

**Next**

editable seed を truthful な Task Ledger contract にし、ordinary consumer files に product を実装します。

## 11. Template assumption を実際の product contract に置き換える

product が本当に実装する contract item だけを残します。

### Browser contract

小さな Task Ledger inventory の例:

| Contract | Product decision |
| --- | --- |
| surface | `primary`: Task Ledger browser UI、local-product audience、non-diagnostic |
| route | `/` の `home`: canonical task-list/editor route |
| states | `ready` と、implementation が実際に表示する loading/empty/error state だけ |
| viewport | tested behavior に合わせて responsive lower bound と input/zoom behavior を維持または修正 |

大規模 application なら必要かもしれないという理由だけで authentication、administration、role-based authorization、touch support、複数 breakpoint、diagnostic surface を追加しないでください。

### Runtime contract

`RUNTIME.md` を consumer decision で具体化します。この例では:

```text
Implementation ecosystem: CPython 3.11+
Persistence: SQLite
Server command: python -m task_ledger.cli --database task-ledger.db serve --host 127.0.0.1 --port 8080
Distribution: source execution for this example
```

これらは product decision であり Composition default ではありません。

### Service contract

JSON API を独立して support するため `SERVICE_INTERFACE.md` を具体化します。

```text
GET    /api/tasks?status=all|open|completed
GET    /api/tasks/{id}
POST   /api/tasks
PATCH  /api/tasks/{id}
DELETE /api/tasks/{id}
GET    /healthz
```

request validation、result/error semantics、size limits、authentication/exposure decisions、readiness/liveness behavior、restart handling、browser UI との関係を定義します。UI と同じ process/listener を共有しても service obligations はなくなりません。

### CLI contract

`CLI_INTERFACE.md` を具体化します。

```sh
python -m task_ledger.cli --database task-ledger.db list --status all
python -m task_ledger.cli --database task-ledger.db export
```

stdout/stderr、exit status、invalid arguments、persistence-target selection、対応 API operation と CLI operation の semantics が等価かを記述します。

## 12. Consumer-owned source files に実装する

product tree の一例です。

```text
task-ledger/
├── task_ledger/
│   ├── cli.py
│   ├── server.py
│   ├── store.py
│   └── static/
│       ├── index.html
│       ├── app.js
│       └── style.css
├── tests/
│   └── test_task_ledger.py
└── scripts/
    └── verify.sh
```

Composition はこの layout を要求しません。これらは ordinary consumer-owned implementation/verification files であり、managed/generated Composition material は変更しません。

validator を green にするだけでなく contracts を満たすよう実装します。少なくとも create/list/edit/complete/delete、open/completed filtering、restart をまたぐ persistence、independent JSON API use、CLI `list` / `export`、declared contract に対応する negative input/error cases を実証します。

## 13. Authoritative product verification を定義して実行する

Composition は product test runner を選びません。Task Ledger では独立して実行可能な command を1つ定義できます。

**Run**

```sh
./scripts/verify.sh
```

**Expected**

consumer-owned unit/integration/product checks が pass し、command が正常終了する。

**Repository change**

command 自体は Composition-owned material を書き換えないようにします。事前に `scripts/verify.sh` と product tests を追加することは通常の consumer development です。

**What this means**

Composition structural/contract validation とは別の product-behavior evidence が存在します。

**Next**

Evidence target ID を推測せず、current contracts から exact target を導出します。

## 14. 現在の evidence worklist を生成する

Webapp scaffold には read-only deterministic generator が含まれます。

**Run**

```sh
python scripts/scaffold_webapp_evidence.py > /tmp/webapp-evidence-worklist.json
```

**Expected**

選択した output file に JSON worklist が書かれ、`contracts/implementation-evidence.json` は変更されない。

**Repository change**

generator 自体による変更なし。上の redirect destination は repository 外です。

**What this means**

target set は actual current surface/route/state/viewport contracts から得られます。それらを変更したら worklist を再生成します。

**Next**

current target ごとに implementation boundary、少なくとも1つの positive proof、少なくとも1つの negative proof、それらを生成する authoritative command、referenced command を実行する release gate を特定します。

1つの suite が複数 target を本当に prove する場合、複数 record が同じ command/gate を再利用して構いません。人工的な one-command-per-record は不要です。

## 15. Proof が存在してから implementation evidence を product mode にする

初期 `contracts/implementation-evidence.json` は意図的に `template` mode で、product implementation claim を持ちません。implementation、`./scripts/verify.sh`、referenced proof location が実在してから `product` mode に切り替えます。

command / gate の例:

```json
{
  "commands": [
    {
      "id": "verify-product",
      "command": "./scripts/verify.sh",
      "purpose": "Run Task Ledger product verification."
    }
  ],
  "releaseGates": [
    {
      "id": "product-verification",
      "purpose": "Require the authoritative product verification command.",
      "commandIds": ["verify-product"]
    }
  ]
}
```

各 record には exact worklist target、verified implementation-boundary locator、verified positive/negative proof locators、expected results、selected gate がさらに必要です。この guide から sample target を copy しないでください。authoritative target set は consumer repository に属します。

両方の verification layer を実行します。

**Run**

```sh
./scripts/verify.sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  validate
```

**Expected**

- product verification command が pass する。
- Composition validation が `status: "valid"` を返し、implementation evidence が template-deferred ではなく executed される。

**What this means**

Task Ledger は consumer tests に裏付けられた product-behavior claim と、valid な closed Composition contract/evidence relationship の両方を持ちます。「valid scaffold」と「implemented, product-tested application」の両条件を満たした地点であり、両者を混同していません。

## 16. 必要なら coding-agent Policy を adopt する

Policy は **separate authority** であり Composition capability ではありません。`composition.json` に架空の `capability.policy` を追加しないでください。

coding agents が Task Ledger を保守するなら、Composition が seed を materialize して consumer ownership に移した後で Policy getting-started workflow に従います。

```text
Composition initial
  → consumer-owned seed/product implementation
  → explicit Policy adoption
  → Composition validation + Policy validation/check + product verification
```

Composition は `.agent-policy.yml`、`.agent-policy.lock`、`.agent-policy/**` を所有しません。Policy-owned commands をこの Composition tutorial に copy するのではなく、published [Policy getting-started guide](https://templates.moukaeritai.work/policy/getting-started/) を使用してください。

## 17. 通常の product change は通常どおり行う

Task Ledger feature の追加、SQLite query の変更、consumer-owned seed contract の編集、product test の追加は ordinary repository work です。product が変わったというだけで Composition `update` は不要です。

product change 後は:

1. consumer-owned contracts/evidence を truthful に更新する。
2. `./scripts/verify.sh` を実行する。
3. Composition `validate` を実行する。
4. Policy を adopt している場合は Policy validation/check も実行する。

Composition lifecycle operation は Composition source/intent 自体が変わる場合に使います。

## 18. 後で Composition を update / upgrade する

installed runner がより新しい reviewed Composition revision を選ぶようになったら、まず inspect します。

intent が同じで compatibility-boundary change がない場合:

**Run**

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  inspect
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  plan --mode update
```

read-only plan を review し、問題なければ:

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  apply --mode update
```

consumer-owned seed changes は preserve され、clean managed/generated material は reviewed plan に従って replace/remove される場合があります。

plan が `COMPONENT_VERSION_UPGRADE_REQUIRED` を報告する場合、または Task Ledger が recipe/components/parameters を意図的に変更する場合は boundary を explicit にします。

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  plan --mode upgrade --config /absolute/path/to/task-ledger/composition.json

python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  apply --mode upgrade --config /absolute/path/to/task-ledger/composition.json
```

その後、product verification と Composition validation を再実行します。update/upgrade conflict を見かけ上成功にするため lock metadata を編集しないでください。

## Completion checklist

**First-use scaffold milestone** は次を満たした時点です。

- Task Ledger が別 product repository である。
- Composition skill がその repository 外に install されている。
- `composition.json` が intended Webapp/capability selection を表す。
- `inspect → plan → review → apply → validate` を正しい順序で実行した。
- mutation 前に plan が read-only であると理解して review した。
- Composition validation が valid。
- concrete file を editable seed、Composition-owned managed/generated material、ordinary product code に分類できる。

**Implemented-product milestone** はさらに強く、次も必要です。

- consumer-owned contracts が template assumption ではなく実際の product を記述する。
- product source/tests が存在する。
- authoritative product verification command が pass する。
- implementation evidence が `product` mode で current target を完全に cover し、real positive/negative proof を持つ。
- Composition validation が implementation evidence を template-deferred ではなく executed して pass する。
- optional Policy を adopt した場合、その state も独立して valid である。

first milestone に到達したなら、次の作業を推論する必要はありません。consumer-owned Task Ledger contracts を編集し、ordinary product source/tests を追加して Sections 11–15 を進めます。architecture、exact ownership rules、managed recovery、immutable-source details は必要になった時点で [Using Composition](../consumer-guide.md) と [Composer reference](../reference/composer.md) を参照してください。
