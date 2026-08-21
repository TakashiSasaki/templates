# Repository language policy

This policy applies to the current `site`, `policy`, and `composition` authority branches in `TakashiSasaki/templates`. Historical retired or archived branch authorities do not define the current translation contract.

## Canonical language

English is the canonical language for maintained repository documentation, technical guidance, repository instructions, policy explanations, artifact contracts, interface contracts, architecture records, and other prose that defines or explains repository behavior.

An English canonical document remains authoritative even when one or more translations are provided. A translation is a non-authoritative derivative. If wording or meaning differs, the English canonical source controls.

This rule does not prohibit non-English text when the text itself is the subject of an example, test fixture, localization resource, interoperability case, quoted external material, or translation.

## Translation layout

The authority that owns a canonical document also owns its translation files and translation synchronization metadata. For provider publications, the `policy` and `composition` branches therefore own translations of their own canonical documents; `site` does not maintain independent copies of those translations.

A translated document should mirror the canonical repository path under `translations/<language>/`.

For example:

```text
docs/overview.md
translations/ja/docs/overview.md
```

A root canonical document mirrors in the same way:

```text
README.md
translations/ja/README.md
```

Translations must identify themselves as non-authoritative and must not introduce requirements absent from the English canonical source.

Provider-owned translation metadata must make the canonical/translation relationship explicit and must record enough source identity to detect when the canonical content changes. A canonical edit invalidates the translation's synchronized state until the translation has been reviewed against the new canonical content.

## Publication boundary

`docs/publication-catalog.json` remains the allowlist of canonical documents and canonical supporting assets. Translation metadata is separate from that canonical publication contract.

The `site` branch may expose translated reader routes only from explicit provider-owned translation metadata at the same reviewed full commit SHA used for the provider's canonical publication. It must not discover translations by unrestricted directory scanning or infer authority from file names alone.

A translated route must:

- retain a link or other unambiguous reference to the corresponding English canonical page;
- state that the translation is non-authoritative;
- use the same locked provider revision as the canonical page; and
- fail closed when translation metadata is stale, malformed, unsafe, or inconsistent with the canonical source identity.

The absence or staleness of a translation must not replace, hide, or invalidate an otherwise valid English canonical page.

## Copyable artifacts

Translations intended only for repository documentation should remain outside Composition-managed copyable artifact material. A translation belongs inside a copyable artifact only when the downstream artifact contract deliberately requires that translation as part of the product delivered to consumers.

## Change workflow

When a canonical document changes:

1. update the English canonical document first;
2. identify every declared translation of that canonical path;
3. review and update each translation that should remain synchronized;
4. update the owning authority's translation synchronization metadata only after that review; and
5. validate both the canonical publication boundary and translation metadata before integrating the provider revision into `site`.

A translation may be intentionally removed instead of updated. It must not remain declared as synchronized when it has not been reviewed against the current canonical bytes.
