# Composition の公開境界

> **参考訳（非正本）:** この文書は英語版 `docs/publication-catalog.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

`composition` branch は、再利用可能な composition system に対する1つの provider publication boundary を所有します。これは、Skill と Webapp の documentation を2つの独立した template authority から公開しなければならない、という従来の前提を置き換えるものです。

generic な schema-v3 publication protocol は Site-owned です。Composition は、自身の catalog 内の declaration と、その共有 protocol の上に重ねる provider-specific semantics を所有します。Composition CI は、review 済みの full commit SHA `3ae5d1e60c65e7a8ebf5f9af0436044484e42983` から Site implementation を利用します。Composition は generic parser の2つ目の実装を維持せず、mutable な `site` branch を追従しません。

これは development / publication dependency に限られます。Composer runtime、managed-repository lifecycle、lock / transaction machinery、recipe、consumer validator が Site publication protocol を import または invoke することはありません。

## Reader-facing boundary

`docs/publication-catalog.json` は schema-version-3 の allowlist です。generic な field / path / source contract は Site-owned protocol によって validation されます。Composition-specific validation はそれに加えて、`README.md` が provider home であり続けること、`docs/glossary.yml` が Composition terminology declaration であり続けることを要求します。

catalog は次の explanatory Markdown を公開します。

- composition architecture と deterministic Composer。
- Agent Skill artifact model。
- Web application artifact model。
- 再利用可能な runtime、CLI、MCP、MCP Apps、browser、service capability。
- 再利用可能な composition-state、contract-evolution、implementation-evidence、release-evidence、release-bundle lifecycle contract。
- 旧 monolithic Skill / Webapp responsibility が現在の authority へ移動した理由を説明し、stage-level detail の immutable PR provenance を示す、統合された1つの authority-migration history。

publication home は branch の `README.md` です。`docs/index.md` は guided navigation が使う provider-owned progressive-disclosure root です。

## Markdown classification boundary

catalog は allowlist ですが、allowlist に含まれないこと自体も意図的でなければなりません。そのため Composition は、non-authoritative derivative のための `translations/manifest.json` と、明示的な非公開 exclusion のための `docs/publication-classification.json` という、2つの追加の Composition-owned declaration によって repository-source Markdown の maintenance boundary を閉じます。どちらの declaration も generic Site publication protocol の一部ではありません。

Composition source tree 内のすべての Markdown file は、正確に次のいずれか1つでなければなりません。

1. **published** — source path が `docs/publication-catalog.json` の `documents` に現れる。
2. **translation-declared** — path が `translations/manifest.json` の `translation` として現れ、canonical document の non-authoritative derivative として宣言される。
3. **explicitly excluded** — source path が `docs/publication-classification.json` に、空でない maintenance reason とともに現れる。

Git metadata、virtual environment、tool cache、一時的な `.site-publication-protocol` checkout などの local execution-state directory は repository source ではなく discovery から除外されます。したがって `docs/guides/*.md` のような新しい Markdown class、新しい component-local documentation subtree、新しい top-level Markdown file、または manifest に未宣言の translation を導入すると、その publication intent が明示的に classification されるまで validation は失敗します。

exclusion が既知の reader-facing requirement を無効にすることはありません。既存の Composition-owned reader-coverage rule は引き続き、provider root、current architecture、統合された authority-migration history、schema / catalog guide、production component が宣言する reader material が公開されることを要求します。published、translation-declared、explicitly excluded の3つの Markdown class は互いに重複できません。

現在の explicit exclusion は次のとおりです。

- operational consumer-agent instruction (`components/artifact.skill-core/files/AGENTS.md`)。
- stage-specific な PR2 / PR3 authority-migration note (`docs/migrations/pr2-skill-capabilities.md` と `docs/migrations/pr3-webapp-lifecycle.md`)。これらは Composition authority maintenance provenance として保持されますが、統合 history と immutable PR record が reader-facing history surface を形成するため reader publication には含めません。
- non-production executable-fixture guidance (`examples/README.md`)。
- repository-level immutable installer publication guidance (`release/README.md`)。これは operational release identity を文書化しますが、reader-facing installation guidance は Site が別途 assemble します。
- repository-facing Composition skill instruction (`skills/composition/SKILL.md`)。これは canonical reader documentation ではなく executable skill material として配布されます。
- provider-owned translation maintenance guidance (`translations/README.md`)。

provider-owned translation derivative は exclusion list に重複して記載しません。その path の classification authority は `translations/manifest.json` だけです。translation validator は別途、canonical path の mirror、current canonical blob identity、notice requirement、surface eligibility、すべての translation Markdown が manifest に宣言されていることを検証します。

classification file と translation manifest は Composition maintenance metadata であり、Site publication asset ではありません。また publication-catalog schema version 3 を変更するものでもありません。

## Machine-readable boundary

Machine-readable source authority は rendered documentation ではなく supporting asset として公開されます。Composition-specific coverage validation は、catalog asset が次を網羅することを要求します。

- `catalog/catalog.json`。
- production recipe 2件すべて。
- immutable skill-installer release schema を含む、top-level composition JSON Schema すべて。
- stable な `release/composition-installer.json` identity descriptor。
- production component descriptor すべて。
- Webapp domain contract / schema seed。
- 再利用可能な lifecycle contract / schema seed。
- consumer composition-lock schema。

stable installer descriptor は、remote installer script revision、installed skill-source revision、その skill が選択する Composition toolchain revision という3つの full-SHA role を分離します。repository CI は、それらの identity を Git history、pinned installer source、skill runtime manifest、runtime-lock digest、strict な `toolchain -> skill source -> installer -> publication` ancestry と照合して検証します。そのため descriptor 自体は、`release/README.md` が reader-facing publication ではなくても machine-readable authority として公開されます。

Site-owned protocol は、generic asset declaration、source existence、path safety、symlink boundary、overlap rule、asset tree 内の undeclared Markdown 禁止を validation します。Composition はその後、自身の production catalog が要求する machine-readable authority を、それら generic asset が網羅していることを validation します。

machine-readable file は branch に存在するだけでは public になりません。explicit asset entry によって coverage されている必要があります。

`contracts/manifest.json` は source publication asset から意図的に除外されています。これは `lifecycle.contract-evolution` が所有する deterministic な **generated consumer material** であり、composition checkout に canonical source file は存在しません。publication は代わりに、Composer が manifest を生成する元となる component registration と schema を公開します。

## Authority and URL model

provider identity は `composition` です。Skill と Webapp はその provider 内部の distinct artifact semantics であり、独立した source authority ではありません。Site integration は reader 向けにそれらの document を別々に group 化できますが、別個の canonical Skill / Webapp source ownership を再構成してはなりません。

この repository はまだ production-facing ではないため、composition migration は backward compatibility だけを理由に旧 provider URL namespace を維持しません。Site information architecture は Site-owned concern であり、この provider allowlist とは別に扱われます。

## Glossary ownership

`docs/glossary.yml` は Composition-owned terminology source です。その record semantics は、generic Site protocol が catalog に existing safe `.yml` glossary source が宣言されていることを確認した後、引き続き Composition が validation します。

Policy が Policy profile と Skill profile を正当に関連付けるため `templates-skill-profile` は維持されますが、retired copyable-template architecture に依存していた definition は維持しません。generic な composition / lifecycle concept は Webapp-only や Skill-only concept と誤って分類せず、composition-owned ID を使います。

glossary file は strict JSON として encode されており、これは有効な YAML 1.2 subset です。これにより Composition は Python standard library だけで provider-specific terminology semantics を validation しつつ、Site glossary reader との compatibility を維持できます。

## Local validation

review 済みの shared protocol は Composition にコピーしません。CI を再現するには、Site commit `3ae5d1e60c65e7a8ebf5f9af0436044484e42983` から `scripts/publication_contract.py` を別 checkout に取得し、その checkout を Composition に指定します。

```sh
export SITE_PUBLICATION_PROTOCOL_ROOT=/path/to/reviewed-site-protocol-checkout
python -I "$SITE_PUBLICATION_PROTOCOL_ROOT/scripts/publication_contract.py" --source-root .
python -I scripts/validate_publication.py
python -I scripts/verify_composition_skill_installer_release.py --git-ref HEAD
python -m unittest discover -s tests -v
```

Site-owned step は generic schema-v3 publication protocol を validation します。続いて `scripts/validate_publication.py` が同じ review 済み module を dynamic load し、その validated `PublicationCatalog` object を利用して、Composition-owned declaration、Markdown classification、reader / machine authority coverage、glossary semantics だけを適用します。installer-release verifier は独立して publication metadata を immutable Git history に束縛します。

pin update は意図的かつ review 済みでなければなりません。Composition CI は今後も40文字の full commit SHA を使い、`site`、tag、pull-request merge ref を暗黙に追従してはなりません。

Composition-specific validation は、undeclared reader documentation、unclassified repository Markdown、published / translation-declared / explicitly-excluded Markdown class 間の overlap、stale Markdown exclusion、missing または unsafe な translation declaration、missing production descriptor / schema / recipe、malformed Composition glossary record、retired copyable-template model を再導入する obsolete glossary ID、inconsistent immutable installer release identity に対して引き続き fail closed します。unsafe path、symbolic-link traversal、duplicate ID / source / destination、invalid home declaration、asset tree 内に隠された Markdown などの generic catalog failure は、Composition layer が実行される前に Site-owned protocol が拒否します。

Site PR #270 は、review 済みの正確な Composition revision を lock して利用することで publication cutover を完了しました。その後の Composition publication change では、mutable branch reference ではなく、明示的に review された Site pin-forward が必要です。
