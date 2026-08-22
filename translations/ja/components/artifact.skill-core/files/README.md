# Agent Skill Composition レシピ

> **参考訳（非正本）:** この文書は英語版 `components/artifact.skill-core/files/README.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

この scaffold は、`skill` Composition レシピによって生成される Skill artifact です。

この architecture では、次の責務を分離します。

- **Skill semantics** は `artifact.skill-core` が所有します。対象は trigger、workflow、resource、agent routing、output、安全性です。
- runtime、CLI、MCP、MCP Apps、standalone Web、headless service などの **application capability** は、再利用可能な `capability.*` component として提供されます。

単純な Skill に application runtime は不要です。まず `SKILL.md` から始め、workflow が必要とする場合にだけ reference、asset、helper script を追加してください。使用しない interface document を残しておくのではなく、application capability は Composition を通じて選択します。

## Skill profiles

Skill 固有の profile は意図的に小さく保たれています。

- `instruction-only`
- `knowledge-augmented`
- `asset-driven`
- `script-assisted`

旧 `packaged-cli`、`mcp-enabled`、`browser-interface`、`headless-service` profile tag は、新しい Skill profile model には含まれません。これらの責務は Composition capability が担います。

未カスタマイズの seed では、scaffold sentinel として `Selected profiles: template-scaffold` を使用します。これは5つ目の具体的な Skill profile ではありません。repository を実運用の Skill にする前に置き換えてください。具体的な Skill が使用できるのは上記4つの profile だけです。

## Public interfaces

capability を選択した場合は、その materialized contract を完成させ、推奨する agent route と fallback を `SKILL.md` に要約してください。

`INTERFACES.md` は意図的に新しい artifact に含めていません。agent routing は Skill に属し、caller-visible な interface behavior は generic capability contract に属します。

## Validation

次を実行します。

```sh
python .github/scripts/validate_skill.py .
```

validator は frontmatter、Skill profile の選択、宣言された resource path、capability file の dependency relationship、および存在する場合は `.template-composition/lock.json` から既知の Composition capability が正しく projection されているかを検査します。

Composition lock 自体は Composer が所有し、Composition validation contract によって検証されます。
