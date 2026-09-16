# Site maintenance

Site maintains presentation, browser runtime, accessibility, PWA, artifact packaging
and deployment. Cross-authority publication semantics live in Integration.
Read [PUBLISHING.md](PUBLISHING.md) for exact inputs and acceptance.

## Local validation

Install the pinned requirements in `requirements-build.lock` and `requirements-visual.txt`.
Run `python scripts/run_core_tests.py --suite core` during construction. The browser
controller suite is `python scripts/run_core_tests.py --suite browser`.
`run_site_preflight.py full --bundle PATH --site-root GENERATED_SITE` reaches core,
browser and immutable Bundle reader checks. It accepts no provider checkout roots.

For physical isolation run `qualify_bundle_renderer.py --site-root . --bundle PATH
--bundle-identity DIGEST --output NEW_PATH` with a clean committed Site candidate.
The test removes Integration implementation and provider directories before rendering.
Use full GitHub qualification at a stable frontier, then exact-head review and guarded merge.

## Site-owned product and policy inputs

`reference-consumer.json` distinguishes Composition's public Website contract,
Policy's maintenance toolchain and the Integration publication selection.
The checked-in `contracts/` worksheets describe this Site product; they neither
select provider publication revisions nor reconstruct provider semantics.
Use the pinned Composition tooling to update its managed consumer state. Do not
hand-edit managed validators or locks. Site browser tests consume the public contracts.

For Policy changes edit `.agent-policy.yml` and `policy/project.md`, then regenerate
Policy-managed outputs with the exact selected toolchain. Never hand-edit `AGENTS.md`.
Toolchain/consumer adoption is independent from provider publication adoption.

## Translation maintenance

English development does not wait for Japanese completion. Site owns only translations
of Site documents. Do not update synchronization hashes until the translation has
actually been reviewed against the new English bytes. Stale Site translations use
the same warning UI as stale provider translations; provider status comes only from
Integration. See [LANGUAGE.md](LANGUAGE.md).
