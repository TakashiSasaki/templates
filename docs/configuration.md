# Configuration

`.agent-policy.yml` is the sole semantic configuration entry point in a managed product repository. It selects a full-SHA toolchain revision, named policy contexts, output targets, and generated skills. Unknown keys are rejected. Input and output paths must remain inside the repository and must not overlap.

The current configuration contract is schema version 2. Schema version 1 is retired and is rejected rather than normalized or migrated implicitly.

## Optional verification command

The `verification` section is optional. When present, it declares the repository command that generated agent instructions require for verification.

```yaml
verification:
  command: npm run verify:pr
```

Repositories with tiered or task-dependent verification may omit this field and express the detailed rules in repository-local policy until the configuration schema supports richer verification tiers.

## Policy contexts and outputs

Schema version 2 separates semantic policy selection from output presentation. Each named entry under `contexts` selects shared profiles and repository-local policy files. Each named output references exactly one context and one renderer.

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
  review-guidelines:
    enabled: true
    path: .agents/review/REVIEW_GUIDELINES.md
    context: review
    renderer: policy-context-md
  review-github-json:
    enabled: true
    path: .agents/review/GITHUB_REVIEW_JSON_V1.md
    context: review
    renderer: github-review-json-v1
skills:
  enabled:
    - validate-agent-policy
    - pr-review
```

The context is the semantic authority boundary. A renderer does not select, add, remove, or override policy rules; it only presents or adapts material associated with the rules selected by its referenced context.

`init` and `adopt prepare` also emit schema version 2. For their single-context configuration they use an explicit `default` context and bind the `agents` output to that context through the `agents-md` renderer. The `default` name is ordinary schema-v2 context data, not a compatibility projection of an older schema.

`agents-md` preserves the established repository-agent instruction surface. `policy-context-md` produces a provider-neutral context document for uses such as pull-request review.

`github-review-json-v1` is an additive renderer available to `.agent-policy.yml` configuration schema version 2 for a GitHub-oriented blocking-review transport. The configuration schema version and the adapter response schema are independent: this adapter currently emits JSON with `schema_version: 1`.

Unlike `policy-context-md`, the GitHub renderer does **not** reproduce the semantic rule bodies. It identifies the same configured review context and adds only the output protocol: review completeness fields, GitHub event mapping, `path`/`line`/`LEFT`/`RIGHT` inline anchors, numeric confidence serialization, and the version-1 JSON response shape. These adapter requirements are not shared review semantics and must not be copied into `policy/review/*.md` or into the automated-review prompt.

A repository that needs the GitHub JSON adapter should normally generate both a provider-neutral semantic projection and the adapter from the same review context:

```yaml
outputs:
  review-guidelines:
    enabled: true
    path: .agents/review/REVIEW_GUIDELINES.md
    context: review
    renderer: policy-context-md
  review-github-json:
    enabled: true
    path: .agents/review/GITHUB_REVIEW_JSON_V1.md
    context: review
    renderer: github-review-json-v1
```

The semantic projection answers what review rules apply. The adapter answers only how an already-established semantic result is serialized for GitHub. Selecting the same named context binds both projections to the same policy selection without turning the adapter into a second policy copy.

Codex, Gemini, Antigravity, or another engine may consume these generated documents; engine invocation details remain outside the semantic policy. A generated `pr-review` Skill may orchestrate evidence collection and refer to the configured semantic and adapter projections, but the Skill likewise must not redefine their contents. Other provider-specific event names, APIs, or serialization contracts require their own renderer or external adapter rather than changes to the review-rule modules.

Output paths are repository configuration, not semantic authority. Agent-facing review projections may therefore live outside `.github/`; `.github/` should be reserved for files whose location has GitHub-defined discovery or runtime semantics. Existing consumers may migrate generated output paths only through the normal lock-bound generated-output lifecycle so modified or non-generated files are not silently removed.

All configured repository-local policy inputs are included in the generated lock. Each output, however, is associated only with the profiles and repository-local policy files belonging to its referenced context. Output paths must be unique and must not overwrite configuration, policy input, or reserved generated-state paths.

## Agent output

Every named output keeps an enable flag and path and additionally requires `context` and `renderer`.

```yaml
outputs:
  agents:
    enabled: true
    path: AGENTS.md
    context: default
    renderer: agents-md
```

When `enabled` is `false`, the path remains declarative but no output file is rendered. This permits a later explicit cutover without losing the intended destination. Adoption preparation instead enables the `agents` output at a shadow path such as `.agent-policy/preview/AGENTS.md`. Finalization rewrites this path to the retained primary instruction path and regenerates the lock while preserving the explicit `default` context and `agents-md` renderer binding.

## Project policy files

Each `contexts.<name>.project_policy.files` member accepts an ordered list of repository-local policy files scoped to that context.

The low-level manifest builder supports multiple files. The `init` command intentionally scaffolds exactly one placeholder file; adoption of an existing repository can preserve multiple existing policy files through `adopt prepare`.

## Explicit shared-policy overrides

Repository-local replacement of a shared rule must be declared explicitly. Reusing an overridable shared rule ID in a context-local policy file is not sufficient by itself. The same context must declare the exact rule ID under `overrides` and provide a non-empty reason.

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

Validation rejects all of the following:

- a repository-local rule that reuses a shared rule ID without a matching override declaration;
- an override declaration for a rule that is not actually replaced in that context;
- replacement of a shared rule whose metadata has `overridable: false`;
- duplicate repository-local rule IDs within one context; and
- duplicate override declarations for the same rule ID within one context.

Explicit override declarations make exceptions to shared normative authority reviewable and machine-checkable for every accepted configuration.

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
