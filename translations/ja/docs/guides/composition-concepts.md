# 初見者向け Composition concepts

> **参考訳（非正本）:** この文書は英語版 `docs/guides/composition-concepts.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

このページは **説明用ガイド** であり、第二の semantic authority ではありません。task-oriented walkthrough は追えるものの、*recipe*、*artifact*、*component*、*contract*、*material*、*lock* といった一般語がこの repository でどのような固有の意味を持つか、短い mental model が欲しい読者を対象にしています。

canonical な repository terminology は `docs/glossary.yml` にあります。厳密な Composition semantics は component descriptor、recipe、schema、および [Composition model](../architecture/composition-model.md) にあります。operation の正確な挙動は [Composer reference](../reference/composer.md) が正本です。このページがそれらと食い違う場合は authority を優先し、このページを修正してください。

Web application や Agent Skill を作り始める前に、このページを読む必要は **ありません**。first-use walkthrough が引き続き主要な zero-to-one path です。

## Mental model

Composition は、作りたい artifact の種類と明示的な consumer intent から始まります。再利用可能な authority を resolve し、それらが宣言する file を別の consumer repository に materialize します。

```text
作りたいもの
    |
    v
  recipe  +  consumer intent
    |
    v
resolved component closure
    |          |          |          |
    v          v          v          v
artifact   foundation capability  lifecycle
component  components components  components
    |          ^          |          |
    +--requires-+---------+----------+
                         |
                         v
                      Composer
               |
               v
       consumer repository
       |- contracts/
       |- schemas/
       |- ordinary product files
       `- .template-composition/
```

重要なのは **selection**、**semantics**、**materialization** を区別することです。

- **recipe** は consumer-facing な開始時の selection です。
- **component** は直接または transitive に選ばれる再利用可能な source authority です。
- component は contract document と schema を register したり、その他の file を materialize したりできます。
- **Composer** は complete component closure を resolve して materialize します。
- **Composition lock** は materialization 成功後の exact resolved state を記録します。

## 一般語と Composition 固有の読み方

| Word | こう決めつけない | この repository では |
| --- | --- | --- |
| **Recipe** | CLI 手順や tutorial の順番 | exactly one artifact component を選び、required/default/selectable な capability/lifecycle component を定める開始 selection です。walkthrough が手順であり、recipe は selection authority です。 |
| **Artifact** | 1個の生成 file | identity-specific semantics を定義する「作られるものの種類」です。現在の production recipe は Agent Skill または Web application を作ります。 |
| **Artifact component** | 完成した product そのもの | artifact 固有の再利用可能 semantics を所有する Composition component です。現在は `artifact.skill-core` と `artifact.webapp-core` があります。 |
| **Component** | UI widget や package dependency | closed reusable Composition source authority です。descriptor が component role、dependency、conflict、materialized destination、ownership mode、optional contract registration を宣言します。 |
| **Foundation component** | 明示的に include する capability | artifact dependency により導入される共有必須 baseline です。foundation は推移的に resolve され、recipe から選択する consumer capability ではありません。 |
| **Capability component** | artifact なら自動的に付く性質 | runtime、packaged CLI、MCP、MCP Apps、standalone browser interface、headless service などの optional で artifact-neutral な behavior です。product が実際にその behavior を公開するときだけ選びます。 |
| **Lifecycle component** | 時系列上の project phase | Composition state、contract evolution、implementation evidence、lifecycle checkpoint、release behavior などの再利用可能な product-lifecycle machinery です。 |
| **Contract** | HTTP/API contract だけ | 選択された component は artifact または lifecycle behavior について machine-readable な contract document と schema を register できます。exact meaning は各 registered contract と owner component が持ち、単一の generic `contract.json` はありません。 |
| **Material** | 抽象的な設計素材 | resolved component から consumer repository へ materialize される file destination です。各 destination には exactly one component owner と one ownership mode があります。 |
| **Seed material** | immutable な template output | 初期 content で、materialization 後に byte ownership が consumer へ移ります。selected である間 file 自体は必要ですが、consumer edit は initial digest から diverge できます。 |
| **Managed / generated material** | consumer が自由に置換できる file | Composition-controlled bytes です。consumer-time validation では resolved lock state との一致が必要です。 |
| **Composition lock** | mutex や process lock | `.template-composition/lock.json` にある deterministic record です。exact source revision、normalized intent、resolved components、ownership、material digest を記録します。 |

### Artifact component と Artifact contract は同じではない

これらは意図的に別概念です。

- **Artifact component** は Composition の authority class であり、作られる artifact 種別に固有の再利用可能 semantics を所有します。
- **Artifact contract** は Policy が所有する repository-wide な分類で、produced artifact が何を含むべきか、何を行うべきかを定義する requirement class です。

これらの語を区別する canonical place は integrated glossary です。語が似ているという理由だけで、Composition 側に Policy-owned `Artifact contract` の第二定義を作ってはいけません。

## 例: minimal Web application

minimal static browser application は `webapp` recipe と optional component なしで開始できます。

```json
{
  "schema_version": 1,
  "recipe": "webapp",
  "components": {
    "include": [],
    "exclude": []
  },
  "parameters": {}
}
```

recipe は `artifact.webapp-core` と baseline lifecycle dependency を選びます。artifact は `foundation.web` を必要とするため、Composer はこの共有必須 baseline も transitive に resolve します。`foundation.web` は browser identity、一般化された routes、viewport/input contract を提供し、`artifact.webapp-core` は application surface、application-route behavior、UI state を提供します。materialization 後、consumer repository には次のような editable seed contract document が入ります。

```text
contracts/browser-identity.json
contracts/routes.json
contracts/viewports.json
contracts/application-routes.json
contracts/surfaces.json
contracts/ui-states.json
```

shared `routes.json` は product-neutral な path、canonical/deep-link、accessibility semantics を記述します。Webapp 固有の surface、authentication/access-failure、history、state behavior は `application-routes.json` に置き、shared route document に戻してはいけません。

これらは作ろうとしている product を記述する file であり、complete implementation ではありません。product code、framework choice、storage、test などの consumer-owned file は別途実装します。

後から maintained implementation runtime、packaged CLI、MCP、service、complete release lifecycle が必要になった場合は、該当する top-level capability/lifecycle component を include します。Composer が transitive requirement を resolve するため、consumer が全 prerequisite を列挙する必要はありません。

## 例: Agent Skill

`skill` recipe は `artifact.skill-core` を選びます。initial material には、別 consumer repository で Skill を作り始めるための Skill structure と validation が含まれます。application capability と大部分の product lifecycle machinery は、Skill だから自動的に付くのではなく opt-in です。

例えば instruction-only または knowledge-augmented Skill は、他の Skill が CLI、MCP、service behavior を公開する可能性があるという理由だけで application runtime を必要としません。

## 次に読むもの

- Web application を今すぐ作る場合は [Webapp product walkthrough](webapp-product-walkthrough.md)。
- Agent Skill を今すぐ作る場合は [Agent Skill first-use walkthrough](skill-first-use-walkthrough.md)。
- optional component を選ぶ場合は [production catalog guide](../../catalog/README.md)。
- strict semantics と ownership rule は [Composition model](../architecture/composition-model.md)。
- exact command と diagnostic は [Composer reference](../reference/composer.md)。
- canonical repository terminology と cross-authority disambiguation は、provider-owned `docs/glossary.yml` から生成される integrated glossary を参照してください。


## コンポーネントロール: 実用的なメンタルモデル

**recipe** は利用者向けの開始点です。recipe は「何を作るのか」を示す **artifact component** を選択し、利用者が明示的に選択できる optional component だけを公開します。**component** は、解決されたプロダクトに一貫した意味論とマテリアルを与える再利用可能な authority です。

コンポーネントロールは、次の四つの問いとして順に読むことができます。

1. **Foundation — どの共有基盤が必要か?** Foundation は artifact の依存関係を通じて自動導入されます。artifact に必要なら必須ですが、利用者が直接選択する product capability ではありません。
2. **Artifact — 何を作っているのか?** Artifact はプロダクトの identity と、それに固有の contract を定義します。
3. **Capability — ほかに何ができるか?** Capability は、PWA、runtime、CLI、MCP interface など externally observable な振る舞いを追加します。
4. **Lifecycle — 時間とともにどのように管理するか?** Lifecycle component は validation、evolution、evidence、checkpoint、release のための再利用可能な仕組みを提供します。

将来の Website recipe は、共有 Web foundation を必要とする Website artifact を選択できます。利用者には Website identity が提示され、PWA や runtime capability を選べます。foundation は自動解決され、include target にはなりません。descriptor ではこれを `component_role`（`foundation`、`artifact`、`capability`、`lifecycle`）で表現し、canonical definition は provider glossary に置きます。
