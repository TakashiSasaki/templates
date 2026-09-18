# Agent instructions — Modeling authority

These are canonical, handwritten, English branch-local instructions. Read AUTHORITY.md before making changes. This file defines local application of the authority boundary; it does not replace the Policy authority's general repository-change policy.

## Local skills and required commands

For resource registration or revision, read `.agents/skills/register-information-model/SKILL.md` and `docs/intake.md`. These apply this authority's contract without acquiring another authority's decision rights.

## Adaptive review scope

Use the immutable Policy landing Skill's review-scope planner after the local
generator/qualification preflight and before an independent review request.
Modeling owns resource records, local schemas/profiles/mappings, identifiers,
record revisions, provenance claims, and catalog/export meaning. A small record
update inside an unchanged contract can use an independent exact-head delta
review covering the source claim and generated projection. Schema/profile
meaning, mapping or identifier rules, observed-versus-verified bytes, rights or
provenance scope, and export contracts expand to the related Modeling stack;
external registration is not Integration/Site adoption. A valid completed
result is reusable only when its candidate, purpose, coverage, and binding
inputs still match. Tests, generated receipts, or cost thresholds never waive
independent review.

## Templates maintainer landing route

For maintenance of the `modeling` authority, load
`.agents/skills/land-templates-stack/SKILL.md` for a single PR or
same-authority stack and verify its adjacent immutable `source.json`. It pins
`TakashiSasaki/templates@fff57bfbb5f45d8608aa10c34519be7a0254f1d3`,
`repository-skills/land-templates-stack/SKILL.md`, blob
`06efa38681e374636bcabcbcb984be5ec43b47ee`; its rule and review-scope planner
are resolved from that
same snapshot, never from a mutable branch or local fallback. Then load
`.agents/skills/pr-merge-gate/SKILL.md` for the separate shared acceptance
gate. Modeling qualification and review evidence do not authorize merge,
Integration/Site adoption, or deployment; this task does not merge or enable
auto-merge.

Install the pinned tooling with `python -m pip install -r requirements-dev.txt`. After source edits, run `python tools/catalog.py generate` and then **`python tools/qualify.py`**. The latter is the canonical local/CI entrypoint: it checks generated freshness and executes the discovered tests, rejecting an empty test run. Dependency installation may use the network; catalog qualification must not retrieve upstream definitions.

The initial administrative profile deliberately has narrower capabilities than the conceptual authority domain. Read its documented limits before adding an unsupported language, identifier, snapshot, relationship scope, or adoption state. Extend the contract and tests rather than misrepresenting the resource to pass validation.

## Before mutation

1. Retrieve live branch/head, relevant PRs, and affected authority contracts. Verify the actual branch and history. Do not trust an old conversation's SHA or infer ownership from file placement.
2. Keep `modeling` independent from `composition`, `policy`, `integration`, and `site`. Never import their Git ancestry. Do not change another authority or enable publication without explicit authorization.
3. State scope, non-goals, acceptance evidence, and the stopping boundary. There is no production compatibility requirement.

## Resource intake

- Decide whether the contribution is a locally owned model, an external resource description, a local profile/mapping, an implementation, or presentation. File extensions do not decide ownership.
- Record upstream normative ownership separately from local record ownership. Registration is not endorsement, adoption, or transfer. Existing authority-specific schemas stay with their semantic owner.
- Read primary sources. Preserve canonical identifiers, original edition labels, applicable languages, source URLs, and bounded observation claims. An inspected landing page does not prove a downloaded distribution's checksum or legal status.
- Use English for English canonical sources and Japanese for Japanese canonical sources. Keep canonical titles and mark translations; do not silently translate normative meaning.
- Distinguish resource, release, representation, distribution, snapshot, record, and Git identities. Do not label a mutable URL immutable, equate an open subset with a full classification, or claim every representation is lossless.
- External bodies are reference-only by default. Do not vendor full standards, classification databases, license text, or executable code merely because publicly accessible. Check permissions and provenance before any separate snapshot intake.
- Use established relationship predicates when their actual semantics fit. Keep exact/close matches, class equivalence, individual identity, and dependency separate. Attribute local assertions explicitly and bind version-sensitive assertions to versions.

## Editing and validation

- Treat individually authored records as source and generated catalogs as projections. Never independently edit a generated index.
- Reuse an established JSON Schema/RDF validation engine rather than implementing a competing partial schema interpreter. Network access must not be required to validate the committed registry.
- Validate schemas, record shape, semantic invariants, duplicate identities, references, languages, provenance, and generated-output freshness. Add negative tests for new invariants.
- Do not invent hashes, licenses, reviewed state, or passing tests. Bind results to the exact file tree or commit and distinguish local checks, CI, and independent review.
- Keep CI lean: use the GitHub-hosted Ubuntu runner and its existing `python3`; do not select a Python minor version or add a compatibility matrix. Run local checks before expensive CI; do not add unrelated Site builds.
- Keep normative constraints, validators, test vectors, results, and browser UI separate. Unsupported checks must not report conformance.

## Collaboration and completion

- Prefer logically separated stacked PRs, each based on its predecessor. Do not block downstream implementation on upstream CI, review, or merge.
- Preserve independent authority histories and leave existing authorities unchanged unless explicitly authorized.
- Maintain operational work/resume state in PR descriptions/comments, not in a Git-tracked session transcript. GitHub remains canonical for PR/head/CI/review facts. Do not duplicate review-finding ledgers.
- After the final stack member, prepare one logical final review packet and let the immutable Policy planner select the diagnostic scope from dependencies, overlap/gaps, design consistency, final behavior, test adequacy, and unrelated changes. Include the authority's root/seed changes where relevant. Additional independent coverage remains available when a new head, contract, binding, or material evidence gap justifies it; do not duplicate an active request or poll after handoff.
- Unless explicitly instructed otherwise, stop after that request and hand off without waiting for review and without merging. Report PR topology, exact heads, tests, outstanding CI/review, start/end/duration, and any tool limitation.
