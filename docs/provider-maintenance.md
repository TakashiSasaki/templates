# Maintaining the Composition provider

This is the canonical overview for people maintaining the Composition authority
itself: its components, recipes, catalog, Composer, schemas, documentation, and
provider publication/release machinery. It is not guidance for maintaining a
Website, Web application, or Agent Skill produced by Composition. Those are
consumer repositories; begin with the [consumer guide](consumer-guide.md) and
the appropriate product walkthrough instead.

## Change the semantic source of truth

- Develop or revise reusable artifacts, capabilities, lifecycle contracts, and
  recipes through the [production catalog guide](../catalog/README.md) and the
  [catalog architecture](architecture/catalog.md). Component descriptors and
  their owned material define the product-facing contracts.
- Change Composer resolution, managed-state behavior, transactions, recovery,
  and diagnostics through the [Composer architecture](architecture/composer-mvp.md)
  and the [Composer reference](reference/composer.md). The reference remains a
  shared contract: consumer operators and provider implementers consult the
  same identity.
- Maintain component, recipe, configuration, lock, transaction, and catalog
  schemas through the [schema guide](../schemas/README.md). The
  [Composition model](architecture/composition-model.md) and
  [generated contract manifest](architecture/generated-contract-manifest.md)
  describe the surrounding semantic and generated-contract boundaries.

## Validate and evaluate the provider

Run the focused and broader checks selected by the changed contract; current
workflows and tests are the executable authority for exact commands. The
[evaluation guide](evaluation-guide.md) is the canonical clean-room and
independent-evaluator path. It evaluates the Composition provider, rather than
validating a consumer product that happens to have been composed from it.

For repeated local editing, run `python scripts/run_composition_preflight.py fast`.
Before starting expensive CI, run the exact-head ready gate from a clean checkout:

```sh
HEAD_SHA=$(git rev-parse HEAD)
python scripts/run_composition_preflight.py ready \
  --component-version-base <BASE_REF> \
  --expected-head "$HEAD_SHA"
```

`ready` runs the Composition-owned validators, the consumer spine, the complete
core unittest suite, Playground projection provenance, and dependency-boundary
checks. It does not download ChromeDriver, contact GitHub, fetch a remote
installer, use an external Integration checkout, or run the browser suite. The
five core publication-contract tests that consume the reviewed Integration
protocol remain in the canonical core suite and are reported as skipped unless
`INTEGRATION_PUBLICATION_PROTOCOL_ROOT` is supplied; CI runs them with the
exact reviewed protocol checkout. For on-demand local runtime checks, run
`python -I scripts/run_composer_runtime_checks.py --check runtime-core` (or
`--check all`). The `full` profile is the explicit browser, remote-installer and
Integration-protocol path; CI uses the Ubuntu runner's browser and driver
components rather than downloading a second browser driver.

The [authority migration history](migrations/composition-authority-migration.md)
is retained as provenance for provider maintenance. It is not a consumer
contract-migration procedure.

## Publish and release the provider

The [publication boundary](publication-catalog.md) defines the Composition
provider catalog and the handoff to integrated publication. A catalog identity
is not reader navigation metadata, and a provider document must not acquire
another authority's navigation terminology to be published.

For the installable Composition Skill, use the [installer release record](../release/README.md).
Its descriptor is the authority for immutable installer, skill-source, and
toolchain identities. That provider release record is distinct from consumer
bootstrap, replacement, update, and product-release workflows; the record links
to their canonical consumer documentation instead of duplicating it.

## Keep responsibilities separate

Composition owns reusable semantics and deterministic composition behavior.
Consumer repositories own their product implementation, product operation, and
product release evidence. Policy owns coding-agent operational policy. When a
change crosses an authority boundary, retain the canonical semantic source in
its owner and use the owner’s current integration procedure rather than copying
or redefining it here.


### Refresh failure boundary

`generate_composition_playground_publication.py --refresh-dir generated` stages
and validates the manifest and both gzip assets before replacing the snapshot
directory. Use an exclusively owned checkout. Staging failures leave the previous
snapshot intact; a failed commit rename restores the previous directory. This is
not a crash-atomic directory exchange: readers can observe a rename gap, and an
uncatchable process termination can leave a sibling `.generated.refresh-*`
directory. If rollback fails, the error names its preserved `previous` directory;
recover that complete snapshot before retrying instead of combining its files
with partially staged output.
