# Lifecycle contract と repository ledger

> **参考訳（非正本）:** このページは英語正本の参考訳です。内容に差異がある場合は英語正本が優先されます。

この Site 所有の読者向けページでは、リポジトリ内の複数の ledger / lifecycle-history の仕組みがどのように関係するかを説明します。これは新しい semantic authority ではありません。product lifecycle の canonical semantics は引き続き `composition` provider が所有し、repository-change と review の手続きは Policy が所有します。

## なぜ複数の ledger があるのか

Git history、pull request、CI run、review thread は重要な provider fact を保存しますが、product contract や validated lifecycle history とは異なる問いに答えます。そのため、このリポジトリでは永続的な記録を一種類の generic ledger とみなさず、役割の異なる複数の logical record を使います。

| Record | 答える問い | Authority | 通常の durable storage | Git tracked? |
| --- | --- | --- | --- | --- |
| Requirement / evidence ledger | 現在の product requirement は何か、どの contract target が対応し、どの proof が必要または記録済みか | Composition lifecycle contracts | `contracts/implementation-evidence.json` | Yes |
| Lifecycle checkpoint ledger | どの validated planning/product state が product の semantic transition history を構成するか | Composition lifecycle contracts | `contracts/lifecycle-checkpoints.json` と content-addressed `artifacts/lifecycle/...` snapshot | Yes |
| Review-finding ledger | どの material review finding が適用中で、その disposition と closure evidence は何か | Policy review procedure | Review/PR surface または execution state | 必須ではない |
| Repository-change Work ledger | repository change の現在の resumable state、binding 済み evidence、次の safe action は何か | staged Policy repository-change candidate | Provider-side PR/issue checkpoint と execution-local state | 原則 No |

これらは相互に関係しますが、どれか一つが他を暗黙に置き換えることはありません。

**Publication status:** Requirement/Evidence と lifecycle の説明は現在選択されている Composition contract を反映し、review-finding model はすでに公開済みの Policy procedure です。Work-ledger の行は review 済みだが未マージの Policy candidate `#754 -> #755` を説明しています。下記の anti-stall 節は別の staged Policy candidate `#773 -> #774` を projection しています。この Site が現在公開している Policy revision は `5574ea46d2076bb1f5c51d4b0e8c9483a17d8fe2` であり、いずれの staged candidate set も含みません。したがって Work ledger candidate と anti-stall projection はここでは staged architecture であり、現在公開済みの Policy authority ではありません。

## Requirement と evidence: 現在の product state

[Implementation evidence](/lifecycle/implementation-evidence/) contract は、選択された Composition lifecycle における canonical requirement/evidence ledger です。stable requirement ID を contract target に結び付け、product mode ではさらに implementation boundary、positive/negative proof、authoritative command、execution capability、release gate に接続します。

Planning mode は implementation evidence が存在する前に target-bound requirement を記録します。Product mode は stable requirement identity を維持したまま implementation/evidence graph を有効化します。したがって、この ledger が答えるのは「現在の product state では何が要求され、どの evidence がそれを支えるか」です。これらの claim 自体が consumer/product contract の一部なので、repository で追跡されます。

## Lifecycle checkpoint: validated transition history

[Lifecycle checkpoints](/lifecycle/checkpoints/) contract は requirement/evidence ledger を置き換えずに historical transition evidence を保存します。planning checkpoint は product implementation が満たすべき exact validated contract baseline を固定し、product checkpoint がその transition を閉じます。後続の specification change は直前の product state を parent とする新しい planning checkpoint を作ります。

Checkpoint chronology は sequence、parent edge、phase alternation、content hash で表されます。snapshot manifest は historical contract、schema、validation result、利用可能な Composition validation authority を binding します。これは current evidence とは別の「この product state はどの validated semantic state から来たか」という問いに答えます。

## Review finding: review-process state

Policy の review-finding ledger は、既知の material actionable review finding を、current-head disposition が検証され必要な closure evidence が記録されるまで追跡します。これは logical tracking model であり、mandatory repository JSON/YAML artifact ではありません。active procedure に応じて inline review thread、durable PR/review comment、PR body section、execution state などに表現できます。

Finding の詳細はこの ledger に残します。repository-change orchestration はそれを参照し、disposition、repair reasoning、qualification、closure evidence を別の authority として複製しません。

## Work ledger: resumable repository-change state

Repository-change Work ledger はさらに別の目的を持ち、進行中 change の operational projection です。logical state には objective/scope、authority snapshot、PR/branch topology、mutation unit、stability/qualification state、evidence binding、blocker、asynchronous dependency、review-finding-ledger reference、next safe action、stop/handoff boundary などを含められます。

Work ledger は repository-associated ですが、通常は Git-tracked progress file にすべきではありません。progress の記録だけを目的とした commit は candidate SHA を動かし、その evidence を記録するためだけに exact-head CI/review evidence を stale にする可能性があります。provider-side PR/issue checkpoint なら source candidate を変えずに operational state を durable にできます。GitHub の commit、branch、PR、CI、review、merge object は canonical provider fact のままであり、Work ledger はそれらを上書きせず observation と binding を記録します。

Work ledger は agent transcript でもありません。すべての fetch、command、poll を記録するのではなく、material state transition を checkpoint し、具体的な next safe action を保持します。

## anti-stall repository-change behavior

この anti-stall repository-change behavior の semantic authority は Policy が保持します。この Site の節は Policy model の読者向け projection にすぎず、独自の retry threshold、failure class、orchestration semantics を定義しません。

この説明は Policy PR `#773 -> #774` とともに **staged** です。Site が選択している published Policy revision にこれらの semantics が含まれるまでは、この節を現在公開済みの Policy artifact の semantics とみなしてはいけません。この読者向け文章を Site で公開しても、それ自体が staged Policy candidate を promote または authorize することはありません。

中心となる区別は、tool activity は material progress ではありません、ということです。repository-change worker が evidence を取得し、capability を探索し、log を調査し、status を報告していても、objective に関する知識が変わっていない場合があります。繰り返し試行しても decision-relevant な knowledge state または repository state が変わらないなら、call 数を progress とみなさず現在の diagnostic strategy を再評価します。

strategy switch は evidence gap の縮め方を実質的に変えるものです。たとえば evidence source、method、hypothesis の変更です。endpoint 名を変えたり、同じ unavailable retrieval を等価な path から繰り返したりするだけでは新しい strategy ではありません。invalidated path については、なぜ失敗したか、その判断がどこに applicability を持つか、再試行を合理化する retry condition は何かを Work ledger に保持します。これにより、中断後の新しい session が「新しい session だから」という理由だけで同じ dead end を再探索することを防ぎます。

external wait と diagnostic stall も区別します。すでに実行中の CI check、review、その他 provider event が completion state を変え得るなら、それを待つこと自体は正当です。その待機中の parallel work は、同じ completion frontier を前進させる場合にだけ productive です。一方 diagnostic stall は、現在の evidence-gathering approach が material progress を生まなくなった状態であり、strategy を切り替えるか、許可された代替手段が残っていなければ blocked と判断します。

resume のため Work ledger は evidence gap、current hypothesis、attempted / invalidated path、exhausted strategy、current strategy、diagnostic budget、progress frontier、last material progress、provider-bound qualification、next safe action を保持します。この model では resume は investigation のやり直しではなく、failed exploration の反復を避けるための compact operational state の復元です。review finding の詳細は別に保ち、review-finding ledger remains authoritative という境界を維持します。Work ledger は finding-level disposition や closure evidence を複製しません。

## Authority と storage の境界

product state と worker state を分けると整理できます。

- requirement/evidence と lifecycle checkpoint は product semantic state または semantic history なので、repository-tracked Composition contract / artifact に属します。
- review-finding と Work ledger は operational process state なので、durable representation は通常 provider-side work surface に置き、新しい product contract を作りません。
- CI result、review、commit、pull request はそれぞれ provider authority を保持します。`success` のような ledger entry は、その exact binding と locator が引き続き適用可能でなければ evidence ではありません。

したがって head/base movement では、実際に binding が変化した observation だけを無効化します。古い exact-head qualification が stale になったという理由だけで semantic implementation progress 全体を捨てる必要はありません。

## 各 record の関係

```text
repository change
    |
    +-- Work ledger ---------------------- resumable orchestration state
    |       |
    |       +-- references review-finding ledger
    |                     |
    |                     +-- finding -> disposition -> closure evidence
    |
    +-- changes product contracts
            |
            +-- requirement/evidence ledger --- current semantic state
            |
            +-- lifecycle checkpoints --------- validated transition history
```

この分離により、operational progress を product authority に変えることなく repository work を resumable にしつつ、product requirement と historical lifecycle evidence を repository 内で再現可能に保てます。

## reference consumer としての `templates`

このリポジトリ自身が、他の consumer 向けに文書化するだけでなく、これらの役割の具体例を提供しています。

### Requirement / evidence の実例

現在の canonical Site base では `contracts/implementation-evidence.json` は `product` mode です。実行可能な Website/PWA command を宣言し、product requirement を implementation record、proof kind、implementation boundary、release gate に接続しています。この file は product state なので、その claim を変更するなら consumer contract の変更として Git で追跡されます。

### Lifecycle history の実例

現在の canonical Site history には、次の6つの validated checkpoint が存在します。

```text
1  site-reference-adoption
   phase: planning
   changeKind: initial
   parentId: null
   snapshotPath: artifacts/lifecycle/001-site-reference-adoption
   manifestSha256: 9ec8d87ea01cf6f178422ca39589882ac3aac86dbc6084d7cc71f5a03df667d4

2  site-reference-adoption-product
   phase: product
   changeKind: initial
   parentId: site-reference-adoption

3  routes-v5-publication
   phase: planning
   changeKind: specification-change
   parentId: site-reference-adoption-product

4  routes-v5-publication-product
   phase: product
   changeKind: specification-change
   parentId: routes-v5-publication
   snapshotPath: artifacts/lifecycle/004-routes-v5-publication-product
   manifestSha256: c3ba91ed78fc90f780213b443182b17c38316d77d92f0151fb3d00392e77d9f1

5  webmcp-reader-publication
   phase: planning
   changeKind: specification-change
   parentId: routes-v5-publication-product
   snapshotPath: artifacts/lifecycle/005-webmcp-reader-publication
   manifestSha256: a6c587cac040a7929fe4fc020acd61843598b6447bd733795d83e2b7182104dc

6  webmcp-reader-publication-product
   phase: product
   changeKind: specification-change
   parentId: webmcp-reader-publication
   snapshotPath: artifacts/lifecycle/006-webmcp-reader-publication-product
   manifestSha256: 2b434f5636675eeacc0d6c4a9676f68a64c953abfada439b1306449ed31ea2a1
```

`site-reference-adoption` は individual requirement ではなく、最初の validated planning baseline の identity です。次の checkpoint はこの identity を parent として消費します。後続の `routes-v5-publication -> routes-v5-publication-product` と `webmcp-reader-publication -> webmcp-reader-publication-product` は、initial product state の後も同じ linear history 上で specification change が継続することを示します。root の requirement/evidence ledger が current product state を表す一方、これらの snapshot はそこへ至った validated state を保存します。

### Review-finding と Work-ledger の dogfooding

このリポジトリでは operational side も実際の Policy work で検証しています。Policy PR stack `#754 -> #755` は repository-change Work ledger を formalize し、その実装作業自体を管理する canonical provider-side checkpoint を stack-tip PR 上で使用しました。checkpoint には objective、P1/P2 topology と exact head、current/stale CI binding、linked finding ledger、blocker、next safe action、immediate-stop review boundary が記録されました。finding-level disposition と closure は Work ledger に複製せず別の finding surface に保持されました。

review 済み staged identity は、P1 / #754 head `c2e23789ebabee4d1f35653e86ebe8f61ab6e8bf` と P2 / #755 head `e73757b93bb7a97c2e6a618d899f652933c9c795` です。この stack は P2 head に対する exact-head Policy CI が green となり、Codex diagnostic review も clean でした。この実例は resumability と authority separation を示しますが、それ自体によって Work ledger が現在公開されている Policy authority の一部になるわけでは**ありません**。

## 公開されている lifecycle destination

以下の canonical lifecycle semantics と source document は `composition` provider が所有します。この Site page は安定した `/lifecycle/` reader entry point を提供し、公開 destination をまとめます。

- [Composition state](/lifecycle/composition-state/)
- [Contract evolution](/lifecycle/contract-evolution/)
- [Implementation evidence](/lifecycle/implementation-evidence/)
- [Lifecycle checkpoints](/lifecycle/checkpoints/)
- [Release execution](/lifecycle/release-execution/)
- [Release evidence](/lifecycle/release-evidence/)
- [Release bundle](/lifecycle/release-bundle/)

repository 全体の ownership model と Policy / Composition の分離については [Policy–Composition coexistence](/coexistence/) を参照してください。

これらの reader path が別個の provider を作るわけではありません。build artifact 内の provenance は `build-provenance.json` に記録された exact provider revision に解決されます。

### Topology 公開の修復履歴

以下は今回の修復を検証した checkpoint です。過去の実装前に planning が存在したという遡及的な証拠ではありません。

| Sequence | Phase | ID | Snapshot | Manifest SHA-256 |
| --- | --- | --- | --- | --- |
| 7 | planning | topology-publication-remediation | artifacts/lifecycle/007-topology-publication-remediation | 5e2203e246437b1ff536430db4e042b403dab7c757b35c2a88447fbfda80c287 |
| 8 | product | topology-publication-remediation-product | artifacts/lifecycle/008-topology-publication-remediation-product | 3c10eceba4ada27893a6868a7fe9188ce02aab90e8cd641c68237d67cf9f94b8 |
| 9 | planning | topology-consumer-overview-remediation | artifacts/lifecycle/009-topology-consumer-overview-remediation | acdd54017dd8e0ca560cf1e91d25b3124953ea07b00faa49fe1d3f3cde7543ce |
| 10 | product | topology-consumer-overview-remediation-product | artifacts/lifecycle/010-topology-consumer-overview-remediation-product | 5c5f8aa08dfe96393a1de3552c16a1ccbeb366411d8688a044b31dca353cac57 |
