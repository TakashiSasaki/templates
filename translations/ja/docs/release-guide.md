# プロダクトリリースの生成

> **参考訳（非正本）:** この文書は英語版 `docs/release-guide.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

このガイドは、release-evidence lifecycle と release-bundle lifecycle を選択した Composition-managed repository の consumer 向けです。実装済み contract evidence から revision-bound な release handoff を生成する通常の product-owned 手順を説明します。

Composition は CI provider、package manager、deployment system、secret source、external approval system、signing system、artifact store を選択しません。一方で、1つの exact candidate revision を、その revision を承認した proof と、その後に handoff する digest-closed contract bundle に結び付ける repository-local contract と deterministic producer を提供します。

## 通常のリリース手順

product release candidate では次の順序を使用します。

```text
Composition apply / update / upgrade
  -> Composition validate
  -> product を実装
  -> implementation evidence を scaffold して完成
  -> fixed release argv を定義
  -> 開発中に product proof を実行
  -> exact candidate を commit
  -> その exact 40-hex commit に対して produce_release.py を実行
  -> revision-bound evidence と bundle を validate
  -> product-owned packaging / deployment / archival
```

release production を candidate commit より前に移動しないでください。managed release producer が証明する対象は mutable working tree に偶然存在する bytes ではなく、immutable candidate revision です。

## 1. Repository を materialize して validate する

最初に通常の Composition lifecycle を使用します。新規 repository では `apply --config ...`、managed repository では `apply --mode update` または `apply --mode upgrade --config ...` になる場合があります。

apply が成功した後、product-specific な release claim を追加する前に Composition validation を実行します。

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  validate
```

generated release contract の初期状態は template mode です。template mode は scaffold であり、実際の product が release gate を通過した証拠ではありません。

## 2. Product implementation evidence を完成させる

`contracts/implementation-evidence.json` は、generated contract target と product implementation / proof evidence の対応関係に関する authority です。

Web application では target identifier を手作業で考案せず、deterministic worklist から開始します。

```sh
python scripts/scaffold_webapp_evidence.py
```

scaffold は non-destructive です。生成された record を使用し、product-mode implementation evidence に次を記録します。

- 必要な各 target の implementation boundary。
- positive evidence。
- 必要な場合の negative evidence。
- authoritative proof の `commandId`。
- その proof を利用する release gate ID。

implementation evidence に保存する human-readable な `command` は、review と digest binding のために proof を識別します。release producer がこれを shell input として parse することはありません。

record を埋める間も implementation-evidence validator と Webapp evidence validator を実行してください。必要な target と release gate がすべて cover されるまで product evidence は fail closed であるべきです。

## 3. 実行可能な release argv を定義する

`contracts/release-execution.json` は、implementation evidence の authoritative command を、release production 時に実行する exact executable argument vector と working directory に結び付けます。

product-mode entry の概念的な形は次のとおりです。

```json
{
  "commandId": "product-proof",
  "argv": ["python", "product/prove_product.py"],
  "workingDirectory": "."
}
```

この argv は product が所有します。Composition は array を直接実行し、human-readable command を shell で parse しません。product が reviewed argv の一部として shell executable を明示的に選択するのでない限り、shell syntax、redirection、interpolation、ambient command rewriting を authoritative execution binding に持ち込まないでください。

product-mode release execution は implementation evidence が宣言した authoritative command を正確に cover しなければなりません。missing、duplicate、extra、malformed、unsafe な execution binding は release evidence が approved になる前に拒否されます。

## 4. Exact candidate を commit する

release production の前に、proof が承認対象とする tracked candidate input をすべて commit します。producer に渡す revision は repository の現在の `HEAD` と一致し、full lowercase 40-hex commit ID でなければなりません。

producer は proof 実行の前後で candidate の physical state を検証します。staged change、変更または削除された tracked input、unsafe な tracked-path topology、non-ignored untracked candidate state は fail closed になります。通常の ignored local environment は存在しても構いませんが、candidate revision の一部として claim されません。product が hermetic environment identity を必要とする場合、その強い product contract を別途明示して review してください。

canonical release-evidence file と release-bundle file は lifecycle output です。その他の tracked candidate input が named revision に binding されたままであれば、これらは committed template bytes または前回 release の bytes と異なっていても構いません。

## 5. Release evidence と bundle を1つの transaction で生成する

通常の consumer command は次のとおりです。

```sh
python -I .template-composition/release/produce_release.py \
  --revision <40-hex-revision>
```

Python isolated mode (`-I`) が必須です。通常の release run では mutable branch name、tag、abbreviated SHA、uppercase hex、revision 省略は受け付けません。

orchestrator は1つの repository-local recoverable transaction を実行します。

1. shared release lifecycle lock を取得する。
2. 以前に中断された release transaction があれば recover する。
3. operation 前の `contracts/release-evidence.json` と `contracts/release-bundle.json` の exact bytes を durable な `.git`-local backup に保存する。
4. durable transaction marker を publish する。
5. exact candidate を verify し、product-owned fixed argv を実行する。
6. revision-bound release evidence を生成する。
7. evidence stage が downstream bundle を変更していないことを verify する。
8. approved evidence と active registered contract から digest-closed release bundle を生成する。
9. canonical lifecycle output の両方を fsync する。
10. transaction marker を削除し、それを commit point とする。

成功時、release evidence は exact subject revision、command-definition digest、execution outcome、release-gate outcome、provenance、chronology、approval decision を記録します。release bundle は同じ subject revision に binding され、自分自身を除く active registered contract をすべて digest します。approved release evidence も含むため、self-reference cycle を作らず handoff を閉じます。

任意の provenance metadata は次の options で指定できます。

```text
--provenance-kind local-run|ci-run|other
--evidence-provenance-id ...
--evidence-provenance-locator ...
--bundle-provenance-id ...
--bundle-provenance-locator ...
```

既定の provenance kind は `local-run` です。provider-specific identifier と locator は product-owned metadata のままであり、candidate identity や proof semantics を変更しません。

## 6. Proof failure を partial output ではなく rejected release として扱う

proof failure、実行中の candidate change、protected lifecycle output の proof による変更、bundle production failure、final revision-bound validation failure が発生した場合、通常の cleanup が実行可能であれば orchestrator は lifecycle lock を解放する前に canonical lifecycle output の両方を operation 前の exact bytes へ復元します。

したがって failed proof は partially accepted release ではありません。product または evidence を修正し、意図する candidate revision を作成して release operation を再実行します。

failed execution を approval に変える目的で generated release evidence を手作業編集しないでください。machine-derived command digest、outcome、timestamp、gate result、chronology、revision binding は producer-owned fact です。

## 7. Abrupt interruption の後に recover する

transaction marker が durable になった後に process が kill された、または machine が停止した場合、次の通常 invocation は新しい release work を開始する前に前回 transaction を recover します。

proof を実行せず recovery だけを行うには次を実行します。

```sh
python -I .template-composition/release/produce_release.py --recover-only
```

`--recover-only` は `--revision` を受け付けません。recovery は durable marker と digest-verified backup を使用して operation 前の exact evidence / bundle bytes を復元します。

malformed marker、missing または modified backup、symbolic transaction file、unsafe canonical output path は fail closed になります。recovery validation を回避するために `.git`-local release transaction state を削除または書き換えないでください。

recovery 成功後、意図する exact candidate に対して通常 command を再実行できます。

## 8. 同じ approved candidate の再実行をサポートする

通常の orchestrator は同じ exact candidate revision に対して再実行できます。両 lifecycle output を transaction-owned output として扱いながら proof を再実行し、release evidence を再生成し、bundle を再構築します。rerun が失敗した場合も、以前の canonical evidence と bundle は snapshot されており復元されます。

通常の release work では one-command orchestrator を使用してください。standalone の `produce_release_evidence.py` と `produce_release_bundle.py` は advanced diagnostics と lifecycle maintenance のために存在します。手作業で両者を chain する方法は通常の consumer release path ではありません。

## 9. Revision-bound output を validate する

orchestrated run が成功した時点で revision-bound validation は実行済みです。release workflow が独立した明示的 check を必要とする場合、同じ exact revision を指定して managed validator を実行します。

```sh
python .template-composition/validators/validate_release_evidence.py \
  . --expected-revision <40-hex-revision>
python .template-composition/validators/validate_release_bundle.py \
  . --expected-revision <40-hex-revision>
```

expected revision は `produce_release.py` に渡した immutable candidate と同一でなければなりません。

## Composition が証明することと product-owned のまま残ること

Composition の release lifecycle が証明するのは repository-local statement です。すなわち、named candidate revision、authoritative proof definition、fixed execution binding、observed proof outcome、gate decision、digest-closed active contract set が managed validator に従って整合することです。

これだけでは deployment success、external artifact identity、secret provenance、build-environment hermeticity、signing identity、transparency-log inclusion、external human approval は証明されません。必要な場合は、それらを release evidence の暗黙的結果として扱わず、別の reviewed product contract を追加してください。

transaction と evidence model の architecture 詳細については、これら lifecycle component を選択した repository に生成される `docs/architecture/release-evidence.md` と `docs/architecture/release-bundle.md` を参照してください。
