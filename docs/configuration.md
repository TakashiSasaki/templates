# Configuration

`.agent-policy.yml` is the sole semantic configuration entry point in a managed product repository. It selects a full-SHA toolchain revision, policy profiles, project-specific policy files, output targets, and generated skills. Unknown keys are rejected. Input and output paths must remain inside the repository and must not overlap.

## Optional verification command

The `verification` section is optional. When present, it declares the repository command that generated agent instructions require for verification.

```yaml
verification:
  command: npm run verify:pr
```

Repositories with tiered or task-dependent verification may omit this field and express the detailed rules in repository-local policy until the configuration schema supports richer verification tiers.

## Agent output

The agent instruction output keeps both an enable flag and a path.

```yaml
outputs:
  agents:
    enabled: true
    path: AGENTS.md
```

When `enabled` is `false`, the path remains declarative but no agent instruction file is rendered. This permits a later explicit cutover without losing the intended destination. Adoption preparation instead enables output at a shadow path such as `.agent-policy/preview/AGENTS.md`.

## Project policy files

`project_policy.files` accepts an ordered list of repository-local policy files. The low-level manifest builder supports multiple files. The `init` command intentionally scaffolds exactly one placeholder file; adoption of an existing repository can preserve multiple existing policy files through `adopt prepare`.

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

The state is validated against `schemas/adoption-state.schema.json` and serialized deterministically. It exists to support later preview comparison and explicit finalization. Editing it manually is unsupported.
