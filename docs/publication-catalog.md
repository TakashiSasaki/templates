# Composition publication boundary

The `composition` branch owns one provider publication boundary for the reusable composition system. It replaces the former assumption that Skill and Webapp documentation must be published from two independent template authorities.

The generic schema-v3 publication protocol is Site-owned. Composition owns the declarations in its catalog and the provider-specific semantics layered on top of that shared protocol. Composition CI consumes the Site implementation from reviewed full commit SHA `3ae5d1e60c65e7a8ebf5f9af0436044484e42983`; it does not maintain a second generic parser or follow the mutable `site` branch.

This is a development/publication dependency only. The Composer runtime, managed-repository lifecycle, lock/transaction machinery, recipes, and consumer validators do not import or invoke the Site publication protocol.

## Reader-facing boundary

`docs/publication-catalog.json` is a schema-version-3 allowlist. Its generic field/path/source contract is validated by the Site-owned protocol. Composition-specific validation additionally requires `README.md` to remain the provider home and `docs/glossary.yml` to remain the Composition terminology declaration.

The catalog publishes explanatory Markdown for:

- composition architecture and the deterministic composer;
- the Agent Skill artifact model;
- the Web application artifact model;
- reusable runtime, CLI, MCP, MCP Apps, browser, and service capabilities;
- reusable composition-state, contract-evolution, implementation-evidence, release-execution, release-evidence, and release-bundle lifecycle contracts; and
- one consolidated authority-migration history that explains why former monolithic Skill/Webapp responsibilities moved to their present authorities and points to immutable PR provenance for stage-level detail.

The publication home is the branch `README.md`. `docs/index.md` is the provider-owned progressive-disclosure root used by guided navigation.

## Markdown classification boundary

The catalog is an allowlist, but absence from the allowlist must also be intentional. Composition therefore closes the repository-source Markdown maintenance boundary with two additional Composition-owned declarations: `translations/manifest.json` for non-authoritative derivatives and `docs/publication-classification.json` for explicit non-publication exclusions. Neither declaration is part of the generic Site publication protocol.

Every Markdown file in the Composition source tree must be exactly one of:

1. **published** — its source path appears in `docs/publication-catalog.json` under `documents`;
2. **translation-declared** — its path appears as a `translation` in `translations/manifest.json`, making it a non-authoritative derivative of a canonical document; or
3. **explicitly excluded** — its source path appears in `docs/publication-classification.json` with a non-empty maintenance reason.

Local execution-state directories such as Git metadata, virtual environments, tool caches, and the temporary `.site-publication-protocol` checkout are not repository source and are excluded from discovery. A newly introduced Markdown class such as `docs/guides/*.md`, a new component-local documentation subtree, a new top-level Markdown file, or an undeclared translation therefore fails validation until its publication intent is classified explicitly.

An exclusion does not suppress a known reader-facing requirement: the existing Composition-owned reader-coverage rules still require provider roots, current architecture, the consolidated authority-migration history, schema/catalog guides, and reader material declared by production components to be published. Published, translation-declared, and explicitly excluded Markdown classes are pairwise disjoint.

The current explicit exclusions are:

- operational consumer-agent instructions (`components/artifact.skill-core/files/AGENTS.md`);
- the stage-specific PR2 and PR3 authority-migration notes (`docs/migrations/pr2-skill-capabilities.md` and `docs/migrations/pr3-webapp-lifecycle.md`), which are retained as Composition authority maintenance provenance while the consolidated history and immutable PR records form the reader-facing history surface;
- non-production executable-fixture guidance (`examples/README.md`);
- repository-level immutable installer publication guidance (`release/README.md`), which documents operational release identities while reader-facing installation guidance is assembled separately by Site;
- repository-facing Composition skill instructions (`skills/composition/SKILL.md`), which are distributed as executable skill material rather than canonical reader publication; and
- provider-owned translation maintenance guidance (`translations/README.md`).

Provider-owned translation derivatives are not duplicated in the exclusion list. Their paths are classified solely by `translations/manifest.json`; the translation validator separately enforces canonical-path mirroring, current canonical blob identity, notice requirements, surface eligibility, and complete declaration of translation Markdown.

The classification file and translation manifest are Composition maintenance metadata, not Site publication assets, and do not change publication-catalog schema version 3.

## Machine-readable boundary

Machine-readable source authorities are published as supporting assets rather than rendered documentation. Composition-specific coverage validation requires the catalog assets to cover:

- `catalog/catalog.json`;
- both production recipes;
- every top-level composition JSON Schema, including the immutable skill-installer release schema;
- the stable `release/composition-installer.json` identity descriptor;
- every production component descriptor;
- Webapp domain contract/schema seeds;
- reusable lifecycle contract/schema seeds; and
- the consumer composition-lock schema.

The stable installer descriptor separates three full-SHA roles: the remote installer script revision, the installed skill-source revision, and the Composition toolchain revision selected by that skill. Repository CI verifies those identities against Git history, the pinned installer source, the skill runtime manifest, the runtime-lock digest, and strict `toolchain -> skill source -> installer -> publication` ancestry. The descriptor itself is therefore published as machine-readable authority even though `release/README.md` is not reader-facing publication.

The Site-owned protocol validates the generic asset declarations, source existence, path safety, symlink boundary, overlap rules, and the prohibition on undeclared Markdown inside asset trees. Composition then validates that those generic assets cover the machine-readable authorities required by its own production catalog.

A machine-readable file is not public merely because it exists in the branch. It must be covered by an explicit asset entry.

`contracts/manifest.json` is deliberately absent from the source publication assets. It is a deterministic **generated consumer material** owned by `lifecycle.contract-evolution`; no canonical source file exists in the composition checkout. The publication instead exposes the component registrations and schemas from which the composer generates the manifest.

## Authority and URL model

The provider identity is `composition`. Skill and Webapp remain distinct artifact semantics inside that provider, not independent source authorities. Site integration may group their documents separately for readers, but it must not reconstruct separate canonical Skill/Webapp source ownership.

This repository is not yet production-facing, so the composition migration does not preserve the former provider URL namespace merely for backward compatibility. Site information architecture is a Site-owned concern and is handled separately from this provider allowlist.

## Glossary ownership

`docs/glossary.yml` is the Composition-owned terminology source. Its record semantics remain validated by Composition after the generic Site protocol confirms that the catalog declares an existing safe `.yml` glossary source.

It retains `templates-skill-profile` because Policy legitimately relates Policy profiles to Skill profiles, but definitions that depended on the retired copyable-template architecture are not preserved. Generic composition/lifecycle concepts use composition-owned IDs rather than being mislabeled as Webapp-only or Skill-only concepts.

The glossary file is encoded as strict JSON, which is a valid YAML 1.2 subset. This lets Composition validate its provider-specific terminology semantics with the Python standard library while remaining compatible with the Site glossary reader.

## Local validation

The reviewed shared protocol is not copied into Composition. To reproduce CI, obtain `scripts/publication_contract.py` from Site commit `3ae5d1e60c65e7a8ebf5f9af0436044484e42983` in a separate checkout and point Composition at that checkout:

```sh
export SITE_PUBLICATION_PROTOCOL_ROOT=/path/to/reviewed-site-protocol-checkout
python -I "$SITE_PUBLICATION_PROTOCOL_ROOT/scripts/publication_contract.py" --source-root .
python -I scripts/validate_publication.py
python -I scripts/verify_composition_skill_installer_release.py --git-ref HEAD
python -m unittest discover -s tests -v
```

The Site-owned step validates the generic schema-v3 publication protocol. `scripts/validate_publication.py` then dynamically loads that same reviewed module to consume its validated `PublicationCatalog` object and applies only Composition-owned declarations, Markdown classification, reader/machine authority coverage, and glossary semantics. The installer-release verifier independently binds publication metadata back to immutable Git history.

A pin update must be deliberate and reviewed. Composition CI must continue to use a 40-character full commit SHA and must not silently follow `site`, a tag, or a pull-request merge ref.

Composition-specific validation remains fail-closed for undeclared reader documentation, unclassified repository Markdown, overlap among published/translation-declared/explicitly-excluded Markdown classes, stale Markdown exclusions, missing or unsafe translation declarations, missing production descriptors/schemas/recipes, malformed Composition glossary records, obsolete glossary IDs that would reintroduce the retired copyable-template model, and inconsistent immutable installer release identities. Generic catalog failures such as unsafe paths, symbolic-link traversal, duplicate IDs/sources/destinations, invalid home declarations, or Markdown hidden inside asset trees are rejected by the Site-owned protocol before the Composition layer runs.

Site PR #270 completed the publication cutover by locking and consuming an exact reviewed Composition revision. Subsequent Composition publication changes require an explicit reviewed Site pin-forward rather than any mutable branch reference.
