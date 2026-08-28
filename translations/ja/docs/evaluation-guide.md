# Composition の評価

> **参考訳（非正本）:** この文書は英語版 `docs/evaluation-guide.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

これは Composition の independent clean-room evaluation に対する canonical entry point です。evaluator と Composition authority maintainer を対象としており、通常の consumer installation や product implementation のための文書ではありません。consumer work では、通常の consumer bootstrap と lifecycle contract が引き続き authority です。

## Canonical evaluation sequence

1. run を開始する前に [small-model clean-room protocol](../../../examples/evaluations/small-model-clean-room-protocol.txt) を読みます。protocol が要求する fresh conversation、external workspace、environment fingerprint、transcript、intervention の boundary を確立します。
2. clean-room run を実行し、chronological observation を保持します。特に、最終 repository state から ordering を推測せず、first product-code mutation と first release-readiness evaluation を記録します。
3. [evaluation scorecard guide](../../../examples/evaluations/evaluation-scorecard.txt) に従い、固定された dimension、attribution vocabulary、chronology rule、missing evidence の fail-closed treatment を使用します。
4. `evaluation-scorecard.json` を生成し、[evaluation scorecard schema](../../../examples/evaluations/evaluation-scorecard.schema.json) で validation します。`BLOCKED` や `NOT TESTED` を `PASS` に変換せず、後から得られた final state で observed ordering violation を修復しません。

output は、validation 済み scorecard JSON と、その claim を裏付ける transcript/tool evidence です。repository defect、documentation/discoverability defect、machine-contract defect、evaluator mistake、environment limitation、evidence-capture limitation は別々の attribution として維持します。

## Authority boundary

protocol、scorecard guide、scorecard schema は Composition-owned evaluation authority です。Site は discovery のためにこの guide と正確な supporting asset を公開しますが、その evaluation semantics を再解釈しません。これらは通常の consumer repository に materialize されず、Site `agent.json` consumer bootstrap に evaluator mode を追加しません。
