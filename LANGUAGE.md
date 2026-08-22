# Repository language policy

This policy applies to the current `site`, `policy`, and `composition` authority branches in `TakashiSasaki/templates`. Historical retired or archived branch authorities do not define the current translation contract.

## Canonical language

English is the canonical language for maintained repository documentation, technical guidance, repository instructions, policy explanations, artifact contracts, interface contracts, architecture records, and other prose that defines or explains repository behavior.

An English canonical document remains authoritative even when one or more translations are provided. A translation is a non-authoritative derivative. If wording or meaning differs, the English canonical source controls.

This rule does not prohibit non-English text when the text itself is the subject of an example, test fixture, localization resource, interoperability case, quoted external material, or translation.

## Translation layout

The authority that owns a canonical document also owns its translation files and translation synchronization metadata. For provider publications, the `policy` and `composition` branches therefore own translations of their own canonical documents; `site` does not maintain independent copies of those translations. Site-owned canonical reader documents follow the same rule: `site` owns their translations and synchronization metadata in the Site history.

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

Translation metadata must make the canonical/translation relationship explicit and must record enough source identity to detect when the canonical content changes. A canonical edit invalidates the translation's synchronized state until the translation has been reviewed against the new canonical content.

## Translation availability

Translation availability is derived from canonical bytes and authority-owned synchronization metadata. For each declared translation, `canonical_blob_sha` identifies the exact canonical Git blob against which the derivative was reviewed.

A declared translation has one of two synchronization states:

- `current` when the recorded blob identity matches the current canonical file bytes; or
- `stale` when the canonical bytes have changed since the translation was reviewed.

For reader coverage, a canonical page may additionally be `missing` for a language when no `reader` translation is declared for that page. `missing` is a coverage state, not malformed metadata.

`current`, `stale`, and `missing` are availability states. Structural failures remain distinct. Malformed manifests, unsafe paths, missing files that are still explicitly declared, symlink traversal, duplicate mappings, invalid surfaces, or declarations that point outside the applicable canonical publication/graph are contract errors and continue to fail closed.

A stale derivative must not be published. It is treated as unavailable for the affected surface while the valid English canonical page remains available. This rule applies independently to reader routes and localized guided-navigation overlays.

## Publication boundary

`docs/publication-catalog.json` remains the allowlist of canonical documents and canonical supporting assets. Translation metadata is separate from that canonical publication contract.

The `site` branch may expose translated reader routes only from explicit translation metadata owned by the same authority as the canonical document. For external provider publications, both canonical content and translation metadata come from the same reviewed full provider commit SHA selected by Site. For Site-owned documents, both come from the exact Site revision being built. Site must not discover translations by unrestricted directory scanning, infer authority from file names alone, or maintain shadow copies of provider translations.

A translated route must:

- retain a link or other unambiguous reference to the corresponding English canonical page;
- state that the translation is non-authoritative;
- use the same owning-authority revision as the canonical page; and
- fail closed when translation metadata is malformed, unsafe, structurally inconsistent, or not synchronized with the canonical source identity.

For a stale declaration, "fail closed" means the translated route or localized overlay is omitted; it does not mean that an otherwise valid canonical publication fails. The absence or staleness of a translation must not replace, hide, or invalidate an otherwise valid English canonical page.

The Site build may emit derived translation-coverage diagnostics. Such diagnostics are not authority metadata: they are regenerated from the canonical publication graph, authority-owned translation manifests, and current canonical blob identities.

## Copyable artifacts

Translations intended only for repository documentation should remain outside Composition-managed copyable artifact material. A translation belongs inside a copyable artifact only when the downstream artifact contract deliberately requires that translation as part of the product delivered to consumers.

## Change workflow

When a canonical document changes:

1. update the English canonical document first;
2. identify every declared translation of that canonical path;
3. review and update each translation that should remain synchronized;
4. update the owning authority's translation synchronization metadata only after that review; and
5. validate both the canonical publication boundary and translation metadata before integrating or publishing that authority revision.

A translation may be intentionally removed instead of updated. It must not remain declared as synchronized when it has not been reviewed against the current canonical bytes. If a canonical change is integrated before its translation is refreshed, the Site must omit that stale derivative and report it as stale rather than suppressing the canonical English page.
