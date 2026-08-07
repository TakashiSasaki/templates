# Configuration

`.agent-policy.yml` is the sole semantic configuration entry point in a managed product repository. It selects a full-SHA toolchain revision, policy profiles, project-specific policy files, output targets, and generated skills. Unknown keys are rejected. Input and output paths must remain inside the repository and must not overlap.

## Optional verification command

The `verification` section is optional. When present, it declares the repository command that generated agent instructions require for verification.

```yaml
verification:
  command: npm run verify:pr
```

Repositories with tiered or task-dependent verification may omit this field and express the detailed rules in repository-local policy until the configuration schema supports richer verification tiers.

## Schema version 1

Schema version 1 preserves the original single-context model. Top-level `profiles` and `project_policy.files` define one implicit `default` policy context, and `outputs.agents` is rendered through the `agents-md` renderer.

```yaml
schema_version: 1
toolchain:
  repository: TakashiSasaki/templates
  revision: 0123456789abcdef0123456789abcdef01234567
profiles:
  - core
  - security-baseline
project_policy:
  files:
    - policy/project.md
outputs:
  agents:
    enabled: true
    path: AGENTS.md
skills:
  enabled:
    - validate-agent-policy
```

The `init` and `adopt` commands continue to emit schema version 1 in this phase. Existing managed repositories therefore do not need a configuration migration merely because the toolchain learns schema version 2.

## Schema version 2 policy contexts

Schema version 2 separates semantic policy selection from output presentation. Each named entry under `contexts` selects shared profiles and repository-local policy files. Each named output then references exactly one context and one renderer.

```yaml
schema_version: 2
toolchain:
  repository: TakashiSasaki/templates
  revision: 0123456789abcdef0123456789abcdef01234567
contexts:
  coding:
    profiles:
      - core
      - security-baseline
    project_policy:
      files:
        - policy/coding.md
  review:
    profiles:
      - core
      - security-baseline
      - review
    project_policy:
      files:
        - policy/review.md
outputs:
  agents:
    enabled: true
    path: AGENTS.md
    context: coding
    renderer: agents-md
  review:
    enabled: true
    path: .github/REVIEW_GUIDELINES.md
    context: review
    renderer: policy-context-md
skills:
  enabled:
    - validate-agent-policy
```

The context is the semantic authority boundary. A renderer does not select, add, remove, or override policy rules; it only presents the rules selected by its referenced context.

`agents-md` preserves the established repository-agent instruction surface. `policy-context-md` produces a provider-neutral context document for uses such as pull-request review.

`github-review-json-v1` is an additive renderer available to `.agent-policy.yml` configuration schema version 2 for a GitHub-oriented blocking-review transport. The configuration schema version and the adapter response schema are independent: this adapter currently emits JSON with `schema_version: 1`. It renders exactly the same semantic rules selected by the referenced context, then adds only the output protocol: review completeness fields, GitHub event mapping, `path`/`line`/`LEFT`/`RIGHT` inline anchors, numeric confidence serialization, and the version-1 JSON response shape. These adapter requirements are not shared review semantics and must not be copied into `policy/review/*.md`.

A repository that needs the GitHub JSON adapter can select it without changing its semantic review context:

```yaml
outputs:
  review:
    enabled: true
    path: .github/REVIEW_GUIDELINES.md
    context: review
    renderer: github-review-json-v1
```

Codex, Gemini, Antigravity, or another engine may consume the generated adapter document; engine invocation details remain outside the semantic policy. Other provider-specific event names, APIs, or serialization contracts require their own renderer or external adapter rather than changes to the review-rule modules.

All configured repository-local policy inputs are included in the generated lock. Each output, however, is rendered only from the profiles and repository-local policy files belonging to its referenced context. Output paths must be unique and must not overwrite configuration, policy input, or reserved generated-state paths.

## Agent output

In schema version 1 the agent instruction output keeps both an enable flag and a path.

```yaml
outputs:
  agents:
    enabled: true
    path: AGENTS.md
```

When `enabled` is `false`, the path remains declarative but no agent instruction file is rendered. This permits a later explicit cutover without losing the intended destination. Adoption preparation instead enables output at a shadow path such as `.agent-policy/preview/AGENTS.md`. Finalization rewrites this path to the retained primary instruction path and regenerates the lock.

Schema version 2 generalizes the same enable/path semantics to every named output and additionally requires `context` and `renderer`.

## Project policy files

In schema version 1, `project_policy.files` accepts an ordered list of repository-local policy files. In schema version 2, each `contexts.<name>.project_policy.files` list has the same meaning but is scoped to that context.

The low-level manifest builder supports multiple files. The `init` command intentionally scaffolds exactly one placeholder file; adoption of an existing repository can preserve multiple existing policy files through `adopt prepare`.

## Explicit shared-policy overrides

Schema version 2 requires repository-local replacement of a shared rule to be declared explicitly. Reusing an overridable shared rule ID in a context-local policy file is not sufficient by itself. The same context must declare the exact rule ID under `overrides` and provide a non-empty reason.

```yaml
contexts:
  coding:
    profiles:
      - core
    project_policy:
      files:
        - policy/generated-artifacts.md
    overrides:
      - id: consistency.synchronize-derived-artifacts
        reason: This repository uses a separately validated generation authority.
```

An override declaration is an exception record, not a second source of policy text. The repository-local policy file supplies the replacement rule body; `overrides` records which canonical shared rule is intentionally being replaced and why.

Validation rejects all of the following in schema version 2:

- a repository-local rule that reuses a shared rule ID without a matching override declaration;
- an override declaration for a rule that is not actually replaced in that context;
- replacement of a shared rule whose metadata has `overridable: false`;
- duplicate repository-local rule IDs within one context; and
- duplicate override declarations for the same rule ID within one context.

Schema version 1 keeps its legacy implicit override behavior for compatibility. New multi-context configurations should use schema version 2 and explicit override declarations so that exceptions to shared normative authority are reviewable and machine-checkable.

## Adoption state

`.agent-policy/adoption.json` is a generated migration-state record, not a second semantic configuration source. In the prepared phase it records:

- the pinned toolchain revision
- the configuration and state paths
- the retained primary instruction path
- SHA-256 hashes of discovered existing instruction, policy, and skill sources
- the preview output path
- selected profiles and project policy inputs
- the verification command, if any
- generated skill names

Newly prepared states also serialize `backup_path: null` and `final_output: null`. These fields remain optional while `status` is `prepared` so that repositories prepared by the earlier command version can be previewed and finalized after upgrading. A `finalized` state requires both fields to contain non-empty repository-local paths.

`adopt preview` requires the state to remain `prepared`, verifies the recorded immutable-source hashes and exact agreement with `.agent-policy.yml`, then regenerates the shadow output and lock. Project-policy files are editable manifest inputs and are intentionally excluded from the immutable-source hash guard unless one is also the retained primary instruction.

Before `adopt finalize --apply` stages or writes the cutover, it snapshots the config, adoption state, lock, preview, every immutable source recorded in the adoption inventory, and every project-policy input. The temporary repository must contain exactly those bytes before rendering, and the live repository must still contain them immediately before the transaction. A concurrent change therefore aborts rather than finalizing against an unvalidated instruction, handwritten skill, or policy revision. The immutable set uses the same classification as source-hash validation: editable project policies are excluded unless they are also the retained primary instruction, while secondary instructions and handwritten skills remain guarded. Config, state, lock, preview, and the retained primary instruction must remain regular files at their lexical paths during finalization. A symlinked primary can be inspected and prepared, but it must be materialized as a regular file with the same intended content before finalization. Replacing any strict finalization path with a symlink, or introducing a symlinked path component, is rejected without modifying the referent. Absolute source symlinks are rejected during inspection and preparation whether the absolute link is the source itself or an ancestor component such as `.agents` or `.github`, because preserving such links in a temporary staging root would redirect source resolution back to the live repository.

After a successful finalization, the state remains in the repository with:

- `status: finalized`
- the immutable backup path containing the original primary instruction bytes
- the final generated instruction path

The state is validated against `schemas/adoption-state.schema.json` and serialized deterministically. Editing it manually is unsupported. The source hashes are cutover guards for the prepared phase; after finalization the generated primary instruction no longer matches the original source hash by design.
