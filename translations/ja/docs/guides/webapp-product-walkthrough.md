# Webapp product walkthrough

> **参考訳（非正本）:** この文書は英語版 `docs/guides/webapp-product-walkthrough.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

この worked example は、Composition の ownership、contract、validation semantics を維持しながら、consumer が空の directory から小規模な実装済み Web アプリケーションへ進む方法を示します。

例として扱う product は **Task Ledger** です。

- browser UI から task の作成、一覧、編集、完了、削除、filter ができる。
- process restart をまたいで task が永続化される。
- HTTP JSON API を browser から独立して利用できる。
- command-line interface が `list` と `export` を提供する。
- product verification は consumer repository が所有する。

この例では product decision を具体化するために Python と SQLite を使用します。Composition がこれらの技術を推奨または選択しているわけでは**ありません**。consumer は同じ workflow に従いながら、別の runtime、framework、database、API implementation、test system を選択できます。

## 1. サポートする contract から recipe と capability を選ぶ

implementation が何 process、何 port、何 library を使うかではなく、外部に対してどの interface をサポートするかから判断します。

| Requirement | Selection | Reason |
| --- | --- | --- |
| Browser product UI | `webapp` recipe baseline | `artifact.webapp-core` が browser surfaces、routes、visible states、viewports、Web-specific validation をすでに所有する。 |
| Python process と execution commands | `capability.runtime` | application runtime の commands/environment を明示的に decision record として残す必要がある。 |
| 独立した HTTP JSON API | `capability.service` | non-browser caller が browser UI なしで API を利用できる。 |
| 保守対象の `list` / `export` CLI | `capability.cli` | CLI が caller-visible な正式 interface である。 |
| 別個の operational/diagnostic browser interface | 選択しない | 通常の Webapp surface とは別の standalone browser interface を product が持たない。 |
| MCP / MCP Apps | 選択しない | MCP contract が不要。 |
| Composition-managed release bundle | 選択しない | deployment/release production はこの小規模例の範囲外。 |

HTTP listener を共有していても、この選択は変わりません。browser と独立 JSON API が同じ server process と port を使っていても、その API は independent service contract です。反対に、browser だけが使う private backend-for-frontend route は、それだけでは `capability.service` を選ぶ理由になりません。

`composition.json` を作成します。

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

recipe の dependency closure により、Webapp baseline に必要な lifecycle components が追加されます。その closure を文書化するだけの目的で required components を `include` に重複して列挙しないでください。

## 2. Inspect、plan、apply、validate を行う

インストール済み Composition runner を使用します。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/task-ledger \
  inspect
```

新しい directory では `absent` または `unmanaged` が期待されます。

mutation の前に plan します。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/task-ledger \
  plan --config /path/to/task-ledger/composition.json
```

すべての file action と conflict を確認します。空の target なら通常 action は `create` です。byte-identical な既存 file は `adopt-identical` になる場合があります。conflict があれば apply 前に解決しなければなりません。

同じ intent を apply します。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/task-ledger \
  apply --config /path/to/task-ledger/composition.json
```

続いて validate します。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/task-ledger \
  validate
```

この時点の repository は **valid な Composition scaffold** であり、実装済み product ではありません。implementation evidence がまだ `template` mode の Webapp では、selected-component validation は product implementation-evidence check を明示的に defer しつつ、Composition validation 全体は valid のままにします。これにより human output は template validity と product claim を同一視しません。

概念的には次のようになります。

```text
PASSED: composition-state (...)
PASSED: webapp-contracts (...)
PASSED: webapp-implementation-coverage (...)
PASSED: contract-evolution (...)
DEFERRED: implementation-evidence (...)
  Implementation evidence is in TEMPLATE mode; no product implementation claim is active. ...
Composition validation: VALID
```

ここで `VALID` が意味するのは、選択済み Composition state と template contracts が valid であることです。Task Ledger の実装、product test、deployment、release readiness を意味しません。

## 3. 実装前に editing boundary を確立する

生成済み material を編集する前に `.template-composition/lock.json` を読みます。

| Ownership | Task Ledger での扱い |
| --- | --- |
| `seed` | product 向けに編集・具体化する。 |
| `managed` | 直接編集しない。Composition が authoritative のまま。 |
| `generated` | 直接編集しない。Composition が deterministic に再生成する。 |
| lock に存在しない | 別の repository-local authority が定めない限り通常の consumer content。 |

したがって通常の product work では、`README.md`、`TEMPLATE.md`、`RUNTIME.md`、`CLI_INTERFACE.md`、`SERVICE_INTERFACE.md`、Webapp contract JSON などの seed documents/contracts を編集し、product source と tests は通常の consumer files として追加します。

local change を valid に見せるために `.template-composition/lock.json` を編集しないでください。Composition validation を回避するために managed schema や validator を product-owned variant として複製することもしないでください。

## 4. Template assumption を実際の product contract に置き換える

product が本当に実装する contract item だけを残します。Task Ledger は意図的に小さい inventory のままで構いません。

### Browser contract

最小の具体的 inventory は seed shape に近いままにできます。

| Contract | Product decision |
| --- | --- |
| surface | `primary`: Task Ledger browser UI、local-product audience、non-diagnostic |
| route | `/` の `home`: canonical task-list/editor route |
| states | `ready` に加え、implementation が実際に表示する loading/empty/error states だけを追加 |
| viewport | tested behavior に合わせて baseline responsive lower bound と input/zoom behavior を維持または修正 |

大規模 application なら必要になるかもしれないという理由だけで authentication、administration、role-based authorization、touch support、複数 breakpoint、diagnostic surfaces を追加しないでください。

### Runtime contract

consumer decision で `RUNTIME.md` を具体化します。この例では次のようにできます。

```text
Implementation ecosystem: CPython 3.11+
Persistence: SQLite
Server command: python -m task_ledger.cli --database task-ledger.db serve --host 127.0.0.1 --port 8080
Distribution: source execution for this example
```

これらは product decision であり、Composition default ではありません。

### Service contract

JSON API を独立してサポートするため `SERVICE_INTERFACE.md` を具体化します。小規模な contract 例:

```text
GET    /api/tasks?status=all|open|completed
GET    /api/tasks/{id}
POST   /api/tasks
PATCH  /api/tasks/{id}
DELETE /api/tasks/{id}
GET    /healthz
```

request validation、result/error semantics、size limits、authentication/exposure decisions、readiness/liveness behavior、restart handling、browser UI との関係を定義します。UI と同じ process/listener を共有していても service obligations はなくなりません。

### CLI contract

保守対象 command について `CLI_INTERFACE.md` を具体化します。例:

```sh
python -m task_ledger.cli --database task-ledger.db list --status all
python -m task_ledger.cli --database task-ledger.db export
```

stdout/stderr、exit status、invalid arguments、persistence target selection、対応 API operation と CLI operation の semantics が等価かどうかを文書化します。

## 5. Consumer-owned source files に実装する

product tree の一例:

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

Composition はこの layout を要求しません。重要なのは、これらが consumer-owned implementation/verification files であり、Composition-owned managed/generated material を変更しないことです。

validator を green にするだけではなく contract を満たすよう実装します。Task Ledger では最低限、次を実証します。

- create/list/edit/complete/delete behavior。
- open/completed filtering。
- process restart をまたぐ persistence。
- independent JSON API usage。
- CLI `list` と `export`。
- declared contracts に対応する negative input/error cases。

## 6. Authoritative consumer verification command を1つ定義する

Composition は product test runner を選びません。Task Ledger では次の command を定義できます。

```sh
./scripts/verify.sh
```

例えば、この command が unit/integration tests と repository が要求する deterministic product checks を実行します。単独で再実行可能にしてください。implementation evidence は「test した」という非形式的 claim ではなく、実在する consumer command を参照するべきです。

product evidence を記録する前に command を実行し、failure を修正します。Composition validation はこの product verification command を代替しません。

## 7. 現在の evidence worklist を生成する

evidence target ID を手作業で発明しないでください。Webapp scaffold には read-only deterministic worklist generator があります。

```sh
python scripts/scaffold_webapp_evidence.py > /tmp/webapp-evidence-worklist.json
```

この command は `contracts/implementation-evidence.json` を変更しません。現在の consumer contracts から Webapp evidence targets を導出するため、surface、route、state、viewport を追加・削除すると worklist も deterministic に変わります。

worklist を product evidence authoring の checklist として使用します。現在の各 target について次を特定します。

- concrete implementation boundary。
- 少なくとも1つの positive proof。
- 少なくとも1つの negative proof。
- それらの proof を生成する authoritative command。
- referenced command を実行する release gate。

1つの test suite が複数 contract targets を実際に証明するなら、複数 record が同じ authoritative command と release gate を再利用して構いません。人工的に1 record 1 command を作らないでください。

## 8. Proof が存在してから implementation evidence を product mode にする

初期 evidence document は意図的に次の状態です。

```json
{
  "$schema": "../schemas/implementation-evidence.schema.json",
  "schemaVersion": 1,
  "mode": "template",
  "commands": [],
  "releaseGates": [],
  "records": []
}
```

`./scripts/verify.sh` が存在し、implementation/proofs が実在してから `product` mode に変更し、worklist から導出した records を埋めます。

command と gate の例:

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

各 record にはさらに、正確な worklist target、verified implementation-boundary locator、verified positive/negative proof locators、expected results、selected gate が必要です。この guide の sample target をコピーしないでください。authoritative target set は consumer repository に属します。

次に両方の verification layer を再実行します。

```sh
./scripts/verify.sh
python .template-composition/validate.py .
```

valid な product-mode document では、`implementation-evidence` は defer されず実行されます。Composition validator は closed contract/evidence relationships を検証し、`./scripts/verify.sh` は product behavior を検証します。この例が表す claim には両方が必要です。

## 9. 必要なら coding-agent Policy を明示的に adopt する

Policy は別 authority であり、Composition capability ではありません。Task Ledger を coding agents が保守するなら、Composition が materialize を行い seed files を consumer ownership に移した後で Policy getting-started workflow に従います。

結果として repository には独立した managed states が存在します。

```text
Composition initial
  -> consumer-owned seed/product implementation
  -> explicit Policy adoption
  -> Composition validation + Policy validation/check + product verification
```

架空の `capability.policy` を `composition.json` に追加せず、Composition に `.agent-policy.yml`、`.agent-policy.lock`、`.agent-policy/**` を所有させないでください。

## 10. 通常の product change では Composition update を呼ばない

Task Ledger feature の追加、SQLite query の変更、consumer-owned seed contract の編集、product test の追加は通常の repository work です。product が変わったというだけで Composition `update` は不要です。

product change 後は次を行います。

1. consumer-owned contracts/evidence を truthful に更新する。
2. `./scripts/verify.sh` を実行する。
3. Composition validation を実行する。
4. Policy を adopt しているなら Policy validation/check を実行する。

Composition source/intent 自体が変わるときだけ Composition lifecycle operation を使用します。

## 11. 後から Composition を update または upgrade する

より新しい reviewed Composition revision が利用可能になったら、まず repository を inspect します。

intent が変わらず、component-version boundary もない場合:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/task-ledger \
  plan --mode update

python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/task-ledger \
  apply --mode update
```

apply 前に plan を確認します。consumer-owned seed changes は保存され、clean な managed/generated materials は plan に従って replace/remove される場合があります。

plan が `COMPONENT_VERSION_UPGRADE_REQUIRED` を報告する場合、または Task Ledger が recipe/components/parameters を意図的に変更する場合は、boundary を明示します。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/task-ledger \
  plan --mode upgrade --config /path/to/task-ledger/composition.json

python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/task-ledger \
  apply --mode upgrade --config /path/to/task-ledger/composition.json
```

その後、product verification と Composition validation を再実行します。update conflict を成功したように見せるために lock metadata を編集しないでください。

## Completion checklist

この例では、次のすべてが成立したとき repository は単なる valid scaffold ではなくなります。

- selected capabilities がサポート対象の caller-visible interfaces と一致する。
- consumer-owned contract seeds が template assumptions ではなく実装済み product を記述している。
- product source と tests が consumer-owned files として存在する。
- authoritative product verification command が成功する。
- implementation evidence が `product` mode で、worklist coverage と実在する positive/negative proofs が完全である。
- Composition validation が成功し、`implementation-evidence` が template-deferred ではなく実行される。
- optional Policy を adopt しているなら、その Policy state も独立して valid である。

これは「apply 直後に Composition validation が valid を返した」より意図的に強い条件です。initial template-valid state は安全な出発点であり、完成した product claim は consumer が所有し、implementation と evidence によって裏付けなければなりません。