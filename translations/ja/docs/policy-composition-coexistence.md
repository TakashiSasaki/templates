# Policy–Composition 共存契約

> **参考訳（非正本）:** この文書は英語正本の参考訳です。内容に差異がある場合は英語正本が優先されます。

## 目的

`policy` と `composition` は独立した canonical authority であり、consumer repository では個別に使うことも、同時に使うこともできます。この契約は、直接の runtime dependency、共有 consumer lock、第三の consumer-management tool を導入せず、安全に共存するために必要な最小限の authority 間境界を定義します。

この契約は integration boundary です。Policy の意味論を Composition に移したり、Composition の意味論を Policy に移したりするものではありません。

## Authority matrix

| Authority | 所有するもの | 所有しないもの |
| --- | --- | --- |
| `policy` | application type に依存しない coding-agent operating semantics、`agent-policy` toolchain、Policy の adoption / render / validate / check behavior、Policy configuration、lock、runtime selection、cache、release identity | artifact semantics、Composition component selection、Composition material ownership、Composer update / upgrade / recovery |
| `composition` | `artifact.*`、`capability.*`、`lifecycle.*` semantics、recipe と schema、deterministic resolution / materialization、Composition lock、ownership、update / upgrade、recovery | coding-agent operating policy、Policy profile、Policy runtime / release、Policy configuration / lock state の解釈 |
| `site` | publication protocol、reviewed provider revision selection、reader-facing information architecture、cross-provider integration validation、Pages / PWA publication | Policy semantics、Composition semantics、consumer repository state の変更 |

## 独立した adoption state

consumer repository は、次のいずれの状態でも正当です。

1. どちらの authority も使わない
2. Policy のみを使う
3. Composition のみを使う
4. Policy と Composition の両方を使う

両者が `TakashiSasaki/templates` で保守されているという理由だけで、一方の provider が他方を前提条件にしてはなりません。

## 排他的 namespace

次の Policy metadata は Policy 所有であり、Composition が claim または変更してはなりません。

```text
.agent-policy.yml
.agent-policy.lock
.agent-policy/**
```

次の Composition metadata は Composition 所有であり、Policy が claim または変更してはなりません。

```text
.template-composition/lock.json
.template-composition/transaction.json
.template-composition/staging/**
```

将来追加する provider-private metadata は、明確に所有された namespace 内に置くか、別の provider が同じ path を claim できるようにする前にこの契約へ追加しなければなりません。

## 禁止される dependency

authority の分離は、次の negative contract によって維持されます。

- Composition component、recipe、schema、Composer operation は Policy adoption を要求してはならない。
- Policy profile、compiler / runtime behavior、Policy adoption / managed operation は Composition adoption を要求してはならない。
- Composer は `agent-policy` CLI を呼び出したり、`.agent-policy.yml` / `.agent-policy.lock` を Composition state として解釈したりしてはならない。
- `agent-policy` は Composer を呼び出したり、`.template-composition/**` を Policy state として解釈したりしてはならない。
- 将来の architecture decision でこの契約を明示的に置き換えない限り、Policy を `capability.agent-policy` などの Composition component として表現してはならない。
- Policy lock と Composition lock を一つの shared lock に統合してはならない。
- Policy と Composition の transaction / recovery state を一つの shared transaction manager に統合してはならない。
- Site は、Policy と Composition の上位に第三の management plane となる consumer-mutating umbrella CLI を導入してはならない。

shared publication infrastructure と integration test は provider publication / input contract を対象とし、consumer management state を扱わないため、これらの制約には違反しません。

## Ownership handoff

通常の repository path の中には、時間の経過とともに複数の lifecycle に正当に関与できるものがあります。そのような path には明示的な ownership handoff が必要であり、暗黙の overwrite precedence に依存して共存してはなりません。

`AGENTS.md` は Skill artifact における現在の主要例です。Composition は Skill artifact の `AGENTS.md` を `seed` として materialize します。初回 materialization 後、その内容は Composition-managed ではなく consumer-owned になります。その後、明示的な Policy adoption を行う場合は Policy adoption contract に従って既存 instruction を検査・移行し、最終的には repository の通常の Policy-managed instruction projection を生成できます。

意図する順序は次のとおりです。

```text
Composition initial
  -> seed materialization
  -> consumer ownership
  -> optional explicit Policy adoption
  -> Policy-generated steady-state instructions
```

Composition update / upgrade は Composition の seed contract に従って、すでに materialize 済みの active seed を保持しなければなりません。Policy adoption は Composition lock の存在を、Composition-exclusive metadata を変更する許可とみなしてはなりません。

Policy-generated path から、同じ destination に新しく選択された Composition material へ逆方向に遷移する一般規則は定義されていません。そのようなケースの明示的 migration contract が存在するまでは、ownership transfer を推測せず、destination conflict で fail closed しなければなりません。

既知の handoff path を `seed` から Composition `managed` または `generated` ownership に変更する将来の変更は cross-authority compatibility change であり、この coexistence contract と integration test の再レビューが必要です。

## Collision rule

cross-authority collision は次の規則に従います。

1. provider-exclusive metadata path は、他方の provider の material / output destination として決して正当ではない。
2. 他の authority がすでに制御している通常の repository path を、第二の authority の adoption / upgrade を理由に上書きしてはならない。
3. ownership transfer は、現在の所有 contract が明示的に ownership を解放し、受け取り側 operation が既存 state を明示的に受け入れ / migrate する場合にのみ有効である。
4. 既知の collision がないことは、他方の provider の internal schema への hidden dependency を導入する許可ではない。
5. conflict resolution は新たな claim を行おうとする authority に属する。Site integration validation は conflict を検出できるが、解決のために consumer を変更しない。

## Authority 間 invariant

両方の authority を使用する repository では、次を満たさなければなりません。

- Policy operation は `.template-composition/**` を変更しない。
- Composition operation は `.agent-policy.yml`、`.agent-policy.lock`、`.agent-policy/**` を変更しない。
- Composition update / upgrade は consumer-owned active seed の bytes を保持する。これには、明示的な Policy adoption によって後から migrate / rewrite された Skill `AGENTS.md` も含む。
- Policy-generated output を Composition-exclusive metadata path 内に設定しない。
- Composition material destination は Policy-exclusive metadata path を claim しない。
- それぞれの provider は、他方の provider が存在しない場合でも独立して valid である。
- 一方の provider の managed state の failure は、他方の provider にその state を repair / rewrite / discard する権限を与えない。

これらの invariant は Site の exact-revision integration test の候補です。各 provider の意味論については provider-local test が引き続き責任を負います。

## Consumer 向け共存 validation checklist

両 authority を adopt 済みの repository では、一方の command が成功したことを他方の provider state の証明とみなさず、それぞれを独立して検証します。この checklist は consumer verification の手順です。Site が consumer の代わりに実行するものではなく、umbrella management command を新設するものでもありません。

1. インストール済み Composition skill を使って Composition を inspect / validate します。

   ```sh
   python /path/to/agent-skills/composition/scripts/run.py \
     --repository /path/to/repository \
     inspect
   python /path/to/agent-skills/composition/scripts/run.py \
     --repository /path/to/repository \
     validate
   ```

   managed Composition state を前提に作業する前に、`inspect` が `managed-valid` を報告することを確認します。

2. 別途インストールした `agent-policy` skill を使って Policy を validate / render / check します。

   ```sh
   python /path/to/agent-skills/agent-policy/scripts/run.py \
     --repository /path/to/repository \
     validate
   python /path/to/agent-skills/agent-policy/scripts/run.py \
     --repository /path/to/repository \
     render
   python /path/to/agent-skills/agent-policy/scripts/run.py \
     --repository /path/to/repository \
     check
   ```

3. Policy の render / finalization 後に Composition の `inspect` と `validate` をもう一度実行します。正当な `AGENTS.md` handoff は、Composition が active seed を consumer ownership へ移譲済みなので引き続き valid です。一方、Policy は Composition-managed metadata と managed / generated material を変更してはなりません。

4. repository diff または同等の before / after snapshot を確認します。Policy operation は `.template-composition/**` を変更してはならず、Composition operation は `.agent-policy.yml`、`.agent-policy.lock`、`.agent-policy/**` を変更してはなりません。handoff 済み `AGENTS.md` のような通常の consumer-owned path は namespace だけでなく、明示された ownership contract に基づいて判断します。

5. failure は独立して扱います。Policy failure は Policy tooling で、Composition failure は Composition tooling で診断します。一方の provider を使って他方の private state を repair / rewrite / delete / regenerate してはいけません。

いずれかの provider で managed operation を行った後は、該当側の checklist を繰り返します。ownership handoff または cross-authority configuration change が関係する場合は、両側の手順を繰り返します。

## Shared mechanism と shared authority

code duplication があるだけでは provider を結合する十分な理由にはなりません。mechanism を共有するのは、一つの semantic owner を持つ、本当に共有された一つの protocol を実装する場合だけです。

repository-wide publication catalog protocol はその候補です。Site はすでに integrated publication を所有しており、provider documentation CI が利用する generic catalog parser / validator を一つ所有できます。provider-specific な publication classification、translation semantics、artifact inventory rule、その他 domain-specific check は各 provider に残ります。

似た名前の小さな primitive が自動的に shared protocol になるわけではありません。たとえば Policy repository-write path safety と Composition portable material-destination safety は異なる contract を持つため、別実装のままで構いません。同様に Policy diagnostics と Composer diagnostics は異なる domain semantics を表現するため provider-owned のままです。

設計規則は次のとおりです。

```text
one semantics -> one authority
one high-level tool -> one owner
one genuinely shared protocol -> one implementation
small domain-specific primitives -> local implementation when that preserves independence
```

## Site integration の責務

Site は `publication-sources.json` に記録された、レビュー済みの正確な Policy / Composition revision で coexistence を検証します。integration validation は reserved-path collision、既知の ownership handoff、stale cross-provider reference、両方の system を使う代表的 repository を確認できます。

Site はこの boundary では observer / integrator です。Policy / Composition semantics の authority にはならず、test fixture の外でどちらかの provider の代わりに consumer adoption、composition、update、render、recovery、migration を実行しません。

## 変更規則

次のいずれかを行う変更には、coordinated coexistence review が必要です。

- provider-exclusive consumer metadata path を追加または変更する。
- 既知の cross-authority handoff destination の ownership mode / owner を変更する。
- Policy-to-Composition または Composition-to-Policy の直接 runtime dependency を導入する。
- shared consumer lock、transaction state、mutating umbrella CLI を導入する。
- 以前 shared だった protocol の authority 所有者を変更する。
- 上記 cross-authority invariant のいずれかを無効にする。

この surface に影響しない provider-internal change は、引き続き独立して release できます。
