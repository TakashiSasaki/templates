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
   |          |          |
   v          v          v
artifact   capability  lifecycle
component  components  components
        \      |      /
         \     |     /
          v    v    v
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
- **component** は直接またはtransitiveに選ばれる再利用可能な source authority です。
- component は contract document と schema を register したり、その他の file を materialize したりできます。
- **Composer** は complete component closure を resolve して materialize します。
- **Composition lock** は materialization 成功後の exact resolved state を記録します。

## 一般語と Composition 固有の読み方

| Word | こう決めつけない | この repository では |
| --- | --- | --- |
| **Recipe** | CLI 手順やtutorialの順番 | exactly one artifact componentを選び、required/default/selectableな capability/lifecycle component を定める開始selectionです。walkthroughが手順であり、recipeはselection authorityです。 |
| **Artifact** | 1個の生成file | identity-specific semanticsを定義する「作られるものの種類」です。現在のproduction recipeはAgent SkillまたはWeb applicationを作ります。 |
| **Artifact component** | 完成したproductそのもの | artifact固有の再利用可能semanticsを所有するComposition componentです。現在は `artifact.skill-core` と `artifact.webapp-core` があります。 |
| **Component** | UI widgetやpackage dependency | closed reusable Composition source authorityです。descriptorがdependency、conflict、materialized destination、ownership mode、optional contract registrationを宣言します。 |
| **Capability component** | artifactなら自動的に付く性質 | runtime、packaged CLI、MCP、MCP Apps、standalone browser interface、headless serviceなどのoptionalでartifact-neutralなbehaviorです。productが実際にそのbehaviorを公開するときだけ選びます。 |
| **Lifecycle component** | 時系列上のproject phase | Composition state、contract evolution、implementation evidence、lifecycle checkpoint、release behaviorなどの再利用可能なproduct-lifecycle machineryです。 |
| **Contract** | HTTP/API contractだけ | 選択されたcomponentはartifactまたはlifecycle behaviorについてmachine-readableなcontract documentとschemaをregisterできます。exact meaningは各registered contractとowner componentが持ち、単一のgeneric `contract.json` はありません。 |
| **Material** | 抽象的な設計素材 | resolved componentからconsumer repositoryへmaterializeされるfile destinationです。各destinationにはexactly one component ownerとone ownership modeがあります。 |
| **Seed material** | immutableなtemplate output | 初期contentで、materialization後にbyte ownershipがconsumerへ移ります。selectedである間file自体は必要ですが、consumer editはinitial digestからdivergeできます。 |
| **Managed / generated material** | consumerが自由に置換できるfile | Composition-controlled bytesです。consumer-time validationではresolved lock stateとの一致が必要です。 |
| **Composition lock** | mutexやprocess lock | `.template-composition/lock.json` にあるdeterministic recordです。exact source revision、normalized intent、resolved components、ownership、material digestを記録します。 |

### Artifact component と Artifact contract は同じではない

これらは意図的に別概念です。

- **Artifact component** はCompositionのauthority classであり、作られるartifact種別に固有の再利用可能semanticsを所有します。
- **Artifact contract** はPolicyが所有するrepository-wideな分類で、produced artifactが何を含むべきか、何を行うべきかを定義するrequirement classです。

これらの語を区別するcanonical placeはintegrated glossaryです。語が似ているという理由だけで、Composition側にPolicy-owned `Artifact contract` の第二定義を作ってはいけません。

## 例: minimal Web application

minimal static browser applicationは `webapp` recipe とoptional componentなしで開始できます。

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

recipeは `artifact.webapp-core` とbaseline lifecycle dependencyを選びます。Webapp artifact componentはroutes、surfaces、UI states、viewportsなどbrowser-specific contract familyを提供します。materialization後、consumer repositoryには次のようなeditable seed contract documentが入ります。

```text
contracts/routes.json
contracts/surfaces.json
contracts/ui-states.json
contracts/viewports.json
```

これらは作ろうとしているproductを記述するfileであり、complete implementationではありません。product code、framework choice、storage、testなどのconsumer-owned fileは別途実装します。

後からmaintained implementation runtime、packaged CLI、MCP、service、complete release lifecycleが必要になった場合は、該当するtop-level capability/lifecycle componentをincludeします。Composerがtransitive requirementをresolveするため、consumerが全prerequisiteを列挙する必要はありません。

## 例: Agent Skill

`skill` recipeは `artifact.skill-core` を選びます。initial materialには、別consumer repositoryでSkillを作り始めるためのSkill structureとvalidationが含まれます。application capabilityと大部分のproduct lifecycle machineryは、Skillだから自動的に付くのではなくopt-inです。

例えばinstruction-onlyまたはknowledge-augmented Skillは、他のSkillがCLI、MCP、service behaviorを公開する可能性があるという理由だけでapplication runtimeを必要としません。

## 次に読むもの

- Web applicationを今すぐ作る場合は [Webapp product walkthrough](webapp-product-walkthrough.md)。
- Agent Skillを今すぐ作る場合は [Agent Skill first-use walkthrough](skill-first-use-walkthrough.md)。
- optional componentを選ぶ場合は [production catalog guide](../../catalog/README.md)。
- strict semanticsとownership ruleは [Composition model](../architecture/composition-model.md)。
- exact commandとdiagnosticは [Composer reference](../reference/composer.md)。
- canonical repository terminologyとcross-authority disambiguationは、provider-owned `docs/glossary.yml` から生成されるintegrated glossaryを参照してください。
