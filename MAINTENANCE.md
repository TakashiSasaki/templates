# Site maintenance

Site maintains presentation, browser runtime, accessibility, PWA, artifact packaging
and deployment. Cross-authority publication semantics live in Integration.
Read [PUBLISHING.md](PUBLISHING.md) for exact inputs and acceptance, and use the
[maintainer onboarding guide](docs/maintainer-onboarding.md) for task ownership.
The [publication automation handoff](docs/publication-automation.md) connects
current workflows and stop/recovery boundaries without enabling them.

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

Add `--jobs N` to cap test workers owned by this Site preflight. The default is
2; `--jobs 1` runs the serial debugging baseline. Source-ready runs L0 first,
then launches independent source checks in fixed budgeted waves. At `--jobs 2`,
the Python core and Node suites each receive one worker and share a wave; at 3
or 4, Python core remains at one measured worker while Node receives one or
two workers. Site core sharding is available in the runner, but its measured
jobs=2 and jobs=4 runs did not improve wall-clock time, so its current effective
cap is one.
The Site Python runner also accepts `--jobs N` directly (default 1). It keeps
new, changed, and unreviewed test modules in a serial/exclusive lane. The
parallel-module manifest pins reviewed source and test-ID fingerprints; changing
one sends that module back to the serial lane until its safety is reviewed. If
later measurements justify sharding, workers import only modules assigned to
their shard.

The Python `unittest` and Node `node --test` execution domains remain separate;
Node receives its allocated `--test-concurrency`. Before that Node child starts,
inherited test-concurrency options are removed from `NODE_OPTIONS`, while
unrelated options and their Node-compatible double-quoted values are preserved.
The explicit runner limit prevents an inherited setting from raising effective
concurrency. The Python core runner's child environment removes `NODE_OPTIONS`
and Python path overrides. The Node tests load the shipped Composition
Playground JavaScript directly and exercise its URL, rendering, event, fetch,
clipboard and async behavior. A cross-authority coordinator's
`--jobs` is a larger shared budget that it divides among authority-local
runners; invoking this Site command directly treats it as the entire Site-local
budget. See the normative worker-budget contract in the Policy authority for the
shared safety classes, nested-worker limit, and exact-SHA qualification rules.

This runs the complete classified Python core suite, every cheap Playground
Node test, Site-owned declaration/contract checks, static Python dependency
boundary checks for each CI requirements input. It deliberately does not run
the managed Composition validator: that validator is Composition-owned and
may provision a runtime or install its locked requirements.

When Composition consumer validation is needed, run its explicit managed
boundary separately (it may require package-index access on an empty cache):

`python scripts/run_site_preflight.py composition-validation --expected-head "$SITE_HEAD"`

The source-ready gate requires the committed HEAD to match exactly and the
index, working tree and untracked-file inventory to be clean. It assumes the
documented local Python and Node dependencies are already installed, but it
does not install packages, access a package index, create a Composition cache,
acquire provider checkouts, use a GitHub API, consume a Pages artifact, or
launch a browser.

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

The source/projection rule applies to this entry point too: edit Site source and
`policy/project.md`, then regenerate `AGENTS.md`; do not edit generated instructions
or rendered build artifacts directly. A Site-only task should keep
`integration-source.json` unchanged. Provider publication, Bundle selection, and
controller diagnosis route to Integration or the read-only publication handoff.

## Translation maintenance

English development does not wait for Japanese completion. Site owns only translations
of Site documents. Do not update synchronization hashes until the translation has
actually been reviewed against the new English bytes. Stale Site translations use
the same warning UI as stale provider translations; provider status comes only from
Integration. See [LANGUAGE.md](LANGUAGE.md).
