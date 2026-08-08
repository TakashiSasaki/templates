# Architecture

The system separates policy authorship, compilation, distribution, onboarding, and enforcement.

- Policy modules are Markdown with YAML front matter.
- Profiles select ordered policy modules.
- `.agent-policy.yml` is the sole semantic configuration entry point in a managed product repository.
- The compiler creates a deterministic intermediate rule list and renders agent-specific files.
- `.agent-policy.lock` records input and output hashes.
- Machine-enforceable quality requirements remain in project tests and CI rather than natural-language rules alone.

## Onboarding modes

An unmanaged repository enters the system through one of two modes:

- `init` creates the initial manifest and generated outputs when no conflicting handwritten instruction output exists.
- `adopt` preserves existing handwritten instructions while project policy is prepared, previewed, and reviewed before an explicit cutover.

The two modes share configuration, rendering, path safety, lock generation, and deterministic diagnostics. They differ in their treatment of existing instructions: initialization rejects a conflict, while adoption records the existing file as a protected source and renders to a non-conflicting preview path.

## Adoption responsibility boundary

Adoption deliberately separates semantic interpretation from mechanical mutation.

The CLI in `TakashiSasaki/templates:policy` owns deterministic operations:

- repository classification and file inventory;
- path and symbolic-link boundary checks;
- source hashing and adoption-state validation;
- scaffold and preview generation;
- stale-source and stale-preview detection;
- transactional backup, cutover, rollback, and lock generation.

The integrated `skills/bootstrap-agent-policy/` package owns agent-assisted orchestration:

- selecting initialization or adoption from inspection results;
- interpreting existing instruction prose;
- proposing profiles and project-policy decomposition;
- reviewing semantic coverage before finalization;
- invoking only the explicitly authorized CLI phase.

The CLI does not embed a language model and does not automatically convert free-form repository instructions into policy modules.

## Adoption state machine

```text
unmanaged
  |
  +-- init --apply ------------------------------> managed
  |
  +-- adopt inspect
        |
        +-- adopt prepare --apply --> prepared
                                      |
                                      +-- adopt preview (repeatable)
                                      |
                                      +-- adopt finalize --apply --> finalized / managed
```

Inspection is always read-only. `init`, `adopt prepare`, and `adopt finalize` default to dry-run and require `--apply` for mutation. `adopt preview` is an explicit regeneration command for prepared generated artifacts and the lock; it does not introduce a separate persistent state. Preparation never replaces the primary handwritten instruction file. Finalization is a separate, explicitly authorized transactional operation.

Repositories that already contain `.agent-policy.yml` use normal `validate`, `render`, and `check` operations. Partial or conflicting onboarding state is classified as inconsistent and is not automatically repaired.

## Repository and package architecture

The `policy` branch is an orphan history unrelated to the repository's `main`, `site`, and `webapp` branches. Within `policy`:

- policy modules, profiles, schemas, compiler, adoption mechanics, templates, tests, and documentation are maintained together;
- the bootstrap trust seed is stored under `skills/bootstrap-agent-policy/`;
- `release/toolchain.json` records the stable executable revision and contract versions;
- product manifests, adoption state, locks, and generated workflow templates identify the executable repository as `TakashiSasaki/templates`;
- the Python distribution and command are named `agent-policy`.

Initialization and adoption use the same trust seed, executable toolchain, configuration format, and lock semantics.

## Stable release promotion

The development branch and executable release are different concepts. `policy` may advance while the stable release descriptor continues to point at an earlier reviewed commit.

A candidate commit first receives complete CI and review. A later promotion change updates both `release/toolchain.json` and the integrated bootstrap manifest to that candidate SHA. The candidate must be a strict ancestor of the promotion state. This two-step model avoids recursive self-reference and allows the promoted toolchain to be identified before the pin is committed.

The release verifier checks the stable descriptor, bootstrap manifest, configuration schema, adoption-state schema, generated lock format, and rendered consumer workflow as one synchronized contract. Policy CI fetches the pull-request head or current pushed ref and verifies ancestry and required executable files at the pinned revision.

Consumer repositories are not rewritten by promotion. Each consumer updates its manifest pin and regenerates its derived artifacts in a separate reviewed change.

## Trust-anchor isolation

The integrated bootstrap skill does not execute the mutable `policy` branch tip. Its manifest records the same full toolchain commit SHA as the stable release descriptor and a closed route set. The pinned candidate precedes the promotion commit, preventing recursive self-reference.

The orchestration script may apply initialization or adoption preparation and preview. It cannot finalize adoption because no finalize route is present in the manifest or script.

A change to the stable release descriptor, bootstrap repository, full SHA, route set, skill instructions, orchestration script, installer, or bootstrap tests remains an independently reviewed trust-anchor change.
