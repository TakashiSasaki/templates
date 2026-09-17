# Site maintenance

Site maintains presentation, browser runtime, accessibility, PWA, artifact packaging
and deployment. Cross-authority publication semantics live in Integration.
Read [PUBLISHING.md](PUBLISHING.md) for exact inputs and acceptance.

## Local validation

Install the pinned requirements in `requirements-build.lock` and
`requirements-visual.txt` when working on build or browser acceptance. The
source-ready profile itself does not install packages, acquire provider
checkouts, use a GitHub API, consume a Pages artifact, or launch a browser.

For the fast construction loop, run:

`python scripts/run_site_preflight.py fast`

This checks diff hygiene, changed-file Python/JSON/tests and classifier
applicability on a dirty tree.

Before spending remote CI resources, record the committed head and run the
source-ready gate from a clean checkout:

`SITE_HEAD=$(git rev-parse HEAD) && python scripts/run_site_preflight.py source-ready --expected-head "$SITE_HEAD"`

This runs the complete classified Python core suite, every cheap Playground
Node test, Site-owned declaration/contract checks, static Python dependency
boundary checks for each CI requirements input, and the managed Composition
consumer validator. It requires the committed HEAD to match exactly and the
index, working tree and untracked-file inventory to be clean.

For an already produced Publication Bundle and rendered Site, run the
artifact-local profile with both inputs:

`python scripts/run_site_preflight.py artifact-local --bundle PATH --site-root GENERATED_SITE`

It fails closed when either path is absent and performs only explicit local
Bundle-reader and rendered-Site checks. It does not acquire or render an
artifact. Playwright, browser, PWA, cross-authority, immutable Pages-artifact
qualification and GitHub/API acceptance remain remote CI checks.

For physical isolation run `qualify_bundle_renderer.py --site-root . --bundle PATH
--bundle-identity DIGEST --output NEW_PATH` with a clean committed Site candidate.
The test removes Integration implementation and provider directories before rendering.
Use the applicable GitHub qualification at a stable frontier, then exact-head review
and guarded merge.

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
