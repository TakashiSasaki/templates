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

When `enabled` is `false`, the path remains declarative but no agent instruction file is rendered. This permits a later explicit cutover without losing the intended destination. Adoption preview mode may instead enable output at a shadow path such as `.agent-policy/preview/AGENTS.md`.

## Project policy files

`project_policy.files` accepts an ordered list of repository-local policy files. The low-level manifest builder supports multiple files. The `init` command intentionally scaffolds exactly one placeholder file; adoption of an existing repository will populate and validate multiple existing policy files through the separate `adopt` workflow.
