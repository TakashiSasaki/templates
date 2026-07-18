# Threat model

Primary risks include mutable executable references, path traversal, symbolic-link escape, accidental overwrite of handwritten instructions, stale generated files, and privileged cross-repository tokens. The design pins executable commits, constrains paths, marks generated files, defaults mutation to dry-run, and performs repository-local synchronization through reviewable changes.

## Adoption-specific risks

Adopting an existing repository adds risks that are not present in empty-repository initialization.

### Premature replacement

A generated `AGENTS.md` could replace handwritten instructions before their semantic requirements have been migrated. Preparation therefore renders to a non-conflicting preview path. Replacing the primary instruction file is permitted only during explicit finalization after the original has been preserved.

### Stale source baseline

The handwritten source may change after inspection or preparation. Adoption records byte hashes and refuses finalization if inventoried source files changed. Git branch ancestry is contextual information and is not a substitute for current file hashes.

### Stale or misleading preview

A preview may no longer correspond to the current profiles, project policy, configuration, or toolchain. Preview and finalization require configuration validation, deterministic regeneration, and normal generated-output checking before cutover.

### Unsafe backup or output paths

An attacker or accidental configuration could direct a backup or output outside the repository, through `.git`, or through an escaping symbolic link. All adoption paths are resolved against the repository root using the same path-safety rules as normal rendering. Existing backup targets and unrelated non-generated files are not overwritten.

### Partial finalization

Failure after moving the original instruction file but before completing rendering or lock generation could leave the repository without valid instructions. Finalization is transactional: it stages the new configuration and generated output, preserves the original byte-for-byte, and restores the pre-finalization state if any later step fails.

### Implicit destructive action

Automatic repository classification could select and execute finalization without adequate review. Automatic mode selection is read-only. Mutation requires an explicit initialization or adoption mode, and finalization requires a separate explicit command.

### Semantic overreach

A deterministic CLI cannot reliably distinguish permanent policy, temporary work priorities, historical notes, obsolete guidance, or justified exceptions in free-form prose. The CLI inventories and hashes sources but does not semantically rewrite them. An agent skill may propose a migration, but a human-reviewable preview remains required.

### Trust-anchor drift

The bootstrap skill could invoke a mutable branch or silently change to a newer CLI revision. The bootstrap manifest pins a full commit SHA. Adoption support is merged and tested on `main` first; the later manifest update is reviewed as an independent trust-anchor change.

### Existing skill collision

A repository may already contain a handwritten skill at a path that adoption intends to generate. The process stops on non-generated conflicts and reports them. It does not replace arbitrary product-specific skill manifests automatically.

## Explicitly excluded powers

Neither initialization nor adoption requires credentials that can modify another repository, deploy a product, rewrite Git history, change branch protection, or alter GitHub settings. Bootstrap scripts do not commit, push, merge, or deploy unless a separate higher-level workflow is explicitly authorized.
