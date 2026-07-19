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

The CLI on `main` owns deterministic operations:

- repository classification and file inventory;
- path and symbolic-link boundary checks;
- source hashing and adoption-state validation;
- scaffold and preview generation;
- stale-source and stale-preview detection;
- transactional backup, cutover, rollback, and lock generation.

The `bootstrap-agent-policy` skill owns agent-assisted orchestration:

- selecting initialization or adoption from inspection results;
- interpreting existing instruction prose;
- proposing profiles and project-policy decomposition;
- reviewing semantic coverage before finalization;
- invoking only the explicitly authorized CLI phase.

The CLI does not embed a language model and does not automatically convert free-form repository instructions into policy modules.

## Adoption state machine

The implemented state progression is:

```text
unmanaged
  |
  +-- init --------------------------> managed
  |
  +-- adopt inspect
        |
        +-- prepare --> prepared --> previewed --> finalize --> managed
```

Inspection is always read-only. `init`, `adopt prepare`, and `adopt finalize` default to dry-run and require `--apply` for mutation. `adopt preview` is an explicit regeneration command for prepared generated artifacts and the lock. Preparation never replaces the primary handwritten instruction file. Finalization is a separate, explicitly authorized transactional operation.

Repositories that already contain `.agent-policy.yml` use normal `validate`, `render`, and `check` operations. Partial or conflicting onboarding state is classified as inconsistent and is not automatically repaired.

## Branch architecture

The repository retains two unrelated long-lived branches:

- `main` contains policies, profiles, schemas, the compiler, deterministic adoption mechanics, tests, and documentation.
- `bootstrap-agent-policy` contains the directly cloneable onboarding skill and a manifest that pins one full `main` commit SHA.

No separate adoption branch is introduced. Initialization and adoption share the same trust seed, executable toolchain, configuration format, and lock semantics. A bootstrap manifest revision update remains an independently reviewed trust-anchor change.
