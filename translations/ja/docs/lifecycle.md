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

**Publication status:** Requirement/Evidence と lifecycle の説明は現在選択されている Composition contract を反映し、review-finding model はすでに公開済みの Policy procedure です。Work-ledger の行は review 済みだが未マージの Policy candidate `#754 -> #755` を説明しています。この Site が現在公開している Policy revision は `c5a3294809a1066bf59b83f467f1d597f885289a` であり、この candidate は含まれません。したがって Work ledger はここでは staged architecture であり、現在公開済みの Policy authority ではありません。

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

現在の canonical Site history には、次の4つの validated checkpoint が存在します。

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
```

`site-reference-adoption` は individual requirement ではなく、最初の validated planning baseline の identity です。次の checkpoint はこの identity を parent として消費します。後続の `routes-v5-publication -> routes-v5-publication-product` は、initial product state の後も同じ linear history 上で specification change が継続することを示します。root の requirement/evidence ledger が current product state を表す一方、これらの snapshot はそこへ至った validated state を保存します。

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
