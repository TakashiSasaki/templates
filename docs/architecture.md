# Architecture

The system separates policy authorship, compilation, distribution, onboarding, and enforcement.

- Policy modules are Markdown with YAML front matter.
- Profiles select ordered policy modules.
- `.agent-policy.yml` is the sole semantic configuration entry point in a managed product repository.
- The compiler creates a deterministic intermediate rule list and renders agent-specific files.
- `.agent-policy.lock` records input and output hashes plus the immutable toolchain pin.
- Machine-enforceable quality requirements remain in project tests and CI rather than natural-language rules alone.
- `skills/agent-policy/` is the single repository-facing skill before and after adoption.

## Unified onboarding model

An unmanaged repository enters the system through one user-facing operation: adoption. Read-only inspection selects one of two internal strategies from repository state:

- **fresh adoption** for `unmanaged-empty`, where no handwritten instruction assets need to be preserved;
- **migration adoption** for `unmanaged-existing`, where existing instructions, repository-local policies, or skills remain authoritative until reviewed.

Both strategies share configuration, rendering, path safety, lock generation, deterministic diagnostics, and the same immutable runtime. They differ only in how existing instructions are treated. Fresh adoption may reuse the hidden `init` command internally and can reach managed state directly. Migration adoption records existing files as protected sources, renders to a non-conflicting preview path, and requires a later explicit finalization step.

`init` is an internal fresh-adoption primitive. It is not a separate user-facing onboarding mode.

## Single-skill responsibility boundary

The CLI in `TakashiSasaki/templates:policy` owns deterministic mechanics:

- repository classification and file inventory;
- path and symbolic-link boundary checks;
- source hashing and adoption-state validation;
- state-derived fresh or migration preparation;
- scaffold and preview generation;
- stale-source and stale-preview detection;
- transactional backup, cutover, rollback, and lock generation.

The single `skills/agent-policy/` package owns repository-facing orchestration and immutable runtime selection:

- bootstrap inspection and state-derived adoption strategy for unmanaged repositories;
- persistent full-SHA runtime acquisition and cache verification;
- `.agent-policy.lock` pin selection for managed repositories;
- interpretation of existing instruction prose during migration;
- profile and project-policy decomposition support;
- semantic review before migration finalization; and
- invocation of only the explicitly authorized CLI phase.

The CLI does not embed a language model and does not automatically convert free-form repository instructions into policy modules.

## Adoption state machine

```text
unmanaged
  |
  +-- agent-policy skill bootstrap
        |
        +-- adopt inspect
              |
              +-- unmanaged-empty
              |     |
              |     +-- fresh prepare --apply
              |             |
              |             +-- internal init primitive --> managed
              |
              +-- unmanaged-existing
                    |
                    +-- adopt prepare --apply --> prepared
                                                  |
                                                  +-- adopt preview
                                                  |
                                                  +-- separate explicit
                                                      adopt finalize --apply
```

Inspection is always read-only. Fresh bootstrap may complete onboarding and then validate/check. Migration bootstrap may prepare and preview only; it never invokes finalization. Finalization is a later explicit managed command through the same skill.

Repositories that already contain `.agent-policy.yml` and `.agent-policy.lock` use normal `validate`, `render`, `check`, and explicit adoption-phase commands through `skills/agent-policy/scripts/run.py`. Partial or conflicting onboarding state is classified as inconsistent and is not automatically repaired.

## Persistent runtime architecture

`skills/agent-policy/runtime-manifest.json` supplies the stable default toolchain for unmanaged repositories. For a managed repository, `.agent-policy.lock` takes precedence. Both require `TakashiSasaki/templates` and a full lowercase commit SHA; malformed or mutable pins fail closed.

A runtime cache identity contains:

- toolchain repository and full commit SHA;
- SHA-256 of the selected revision's `requirements-runtime.lock`;
- Python major/minor version; and
- platform plus machine architecture.

A validated cache entry is reusable without network access. On cache miss, the skill downloads the runtime lock from the exact full SHA, creates an isolated virtual environment in a staging directory, installs the exact runtime distributions with dependency resolution disabled, installs the same full-SHA project with dependencies disabled, runs `pip check`, verifies the installed distribution set, writes a marker, and only then renames the staged runtime into its final cache identity.

The cache contains derived execution state, not policy authority. The authoritative inputs remain the full commit SHA, runtime lock digest, and managed repository lock.

## Repository and package architecture

The `policy` branch is an orphan history unrelated to the repository's `main`, `site`, and `webapp` branches. Within `policy`:

- policy modules, profiles, schemas, compiler, adoption mechanics, templates, tests, and documentation are maintained together;
- the single repository-facing skill is stored under `skills/agent-policy/`;
- `release/toolchain.json` records the stable executable revision and contract versions;
- `skills/agent-policy/runtime-manifest.json` binds that stable revision to its runtime-lock digest;
- product manifests, adoption state, locks, and generated workflow templates identify the executable repository as `TakashiSasaki/templates`; and
- the Python distribution and command are named `agent-policy`.

Fresh adoption, migration adoption, and managed operation use the same toolchain identity and runtime-cache mechanism.

## Stable release promotion

The development branch and executable release are different concepts. `policy` may advance while the stable release descriptor continues to point at an earlier reviewed commit.

A candidate commit first receives complete CI and review. A later promotion change updates both `release/toolchain.json` and `skills/agent-policy/runtime-manifest.json` to that candidate SHA and records the candidate runtime-lock SHA-256. The candidate must be a strict ancestor of the promotion state. This two-step model avoids recursive self-reference and allows the promoted toolchain to be identified before the pin is committed.

The release verifier checks the stable descriptor, runtime manifest and runtime-lock digest, configuration schema, adoption-state schema, generated lock format, and rendered consumer workflow as one synchronized contract. Policy CI fetches the pull-request head or current pushed ref and verifies ancestry and required executable files at the pinned revision.

Consumer repositories are not rewritten by promotion. Each consumer updates its manifest pin and regenerates its derived artifacts in a separate reviewed change. An already managed repository continues to select the revision in its own `.agent-policy.lock`.

## Trust-anchor isolation

The single skill does not execute the mutable `policy` branch tip. Its runtime manifest records the same full toolchain SHA as the stable release descriptor and the digest of the stable runtime lock. The pinned candidate precedes the promotion commit, preventing recursive self-reference.

Bootstrap orchestration may complete fresh adoption or apply migration preparation and preview. It cannot finalize migration because no finalize route is present in the runtime manifest or bootstrap script.

A change to the stable release descriptor, runtime-manifest repository/full SHA/runtime digest, cache identity, route set, skill instructions, orchestration scripts, installer, or single-skill tests remains an independently reviewed trust-anchor change.
