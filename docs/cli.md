# CLI

## Common form

```bash
agent-policy [--repository PATH] [--format text|json] COMMAND [OPTIONS]
```

Specify `--repository` and `--format` before the subcommand. If `--repository` is omitted, the CLI searches upward from the current location for the Git repository root.

## `init`

Create an initialization plan for an unmanaged repository that has no existing policy instructions. Files are not modified by default. To adopt a repository while preserving existing instructions, use the `adopt` workflow rather than trying to bypass conflicts with `init`.

```bash
agent-policy --repository /path/to/repository init
```

Specify `--apply` to apply the plan.

```bash
agent-policy --repository /path/to/repository init \
  --toolchain-revision <FULL_COMMIT_SHA> \
  --profile core \
  --profile security-baseline \
  --verification-command "npm run verify:pr" \
  --apply
```

Main options:

| Option | Description |
| --- | --- |
| `--config PATH` | Configuration-file path. Defaults to `.agent-policy.yml`. |
| `--apply` | Actually apply the plan. |
| `--toolchain-revision SHA` | Full toolchain commit SHA recorded in configuration and lock state. |
| `--profile NAME` | Initial profile. May be specified multiple times. |
| `--project-policy PATH` | Single project-policy scaffold to create. Defaults to `policy/project.md`. |
| `--verification-command COMMAND` | Verification command recorded in generated instructions. Defaults to `./scripts/verify.sh`. |
| `--no-verification` | Omit the `verification` section from the initial configuration. |
| `--agents-output-path PATH` | Generated agent-instruction destination. Defaults to `AGENTS.md`. |
| `--disable-agents-output` | Disable agent-instruction generation initially while retaining the path for later enablement. |
| `--skill NAME` | Skill to generate initially. May be specified multiple times and must match `[a-z0-9][a-z0-9-]*`. Defaults to `validate-agent-policy` when omitted. |

If profiles are omitted, `core` and `security-baseline` are selected. To avoid duplicate placeholder rule IDs, `init` creates exactly one project-policy scaffold. Adoption that preserves multiple existing project-policy files is the responsibility of `adopt prepare`.

Before writing, `init` validates skill names against the schema-equivalent form and normalizes and compares every planned path for configuration, project policy, agent instructions, generated skills, and `.agent-policy.lock`. It rejects identical paths, parent/child path overlap, and any planned destination whose ancestor is an existing regular file, rather than performing partial initialization. Collisions among planned outputs are reported as `INIT_PATH_COLLISION`; blocking existing paths are reported as `FILE_CONFLICT`.

For compatibility with existing behavior, omitting verification configures `./scripts/verify.sh`. In a repository without that command, specify the actual verification command or use `--no-verification`.

## `adopt inspect`

Read existing agent instructions, `.agents/policies`, and `.agents/skills` without mutation and classify the repository as one of:

- `unmanaged-empty`
- `unmanaged-existing`
- `managed`
- `inconsistent`

```bash
agent-policy --repository . adopt inspect
agent-policy --repository . --format json adopt inspect
```

For each source, diagnostics report its path, SHA-256, and whether it contains a generated marker. File contents are not copied into the report. If a repository-internal symlink is discovered as a source, the report and adoption state record the discovered lexical path, while SHA-256 and the generated marker are calculated from the safely resolved target within the repository. Under known source trees, only symlinks to existing regular files are accepted as sources. Symlinks to directories, dangling targets, or other non-regular files are classified as `inconsistent`, as are symlinks that resolve outside the repository. Absolute symlinks are rejected not only when the source itself is absolute but also when an ancestor component of the lexical source path, such as `.agents` or `.github`, is an absolute symlink. Partial adoption states in which only configuration, lock state, adoption state, or generated markers remain are also classified as `inconsistent`.

## `adopt prepare`

Create a prepared state for migration to agent-policy management while preserving existing instructions as authoritative. The command is a dry run by default and does not write to the live repository.

```bash
agent-policy --repository . adopt prepare \
  --primary-instructions AGENTS.md \
  --profile core \
  --profile security-baseline \
  --project-policy .agents/policies/repository.md \
  --verification-command "npm run verify:pr"
```

Use `--apply` explicitly to apply the prepared state.

```bash
agent-policy --repository . adopt prepare \
  --primary-instructions AGENTS.md \
  --verification-command "npm run verify:pr" \
  --apply
```

`prepare` fully generates and validates the manifest, project policy, preview, generated skills, lock state, and adoption state in a temporary copy before creating only new files in the live repository. It does not overwrite the existing primary instructions or existing project policy. The default preview destination is `.agent-policy/preview/AGENTS.md`. Each file is created exclusively during application, and failure cleanup is limited to files that the current invocation successfully created.

Main options:

| Option | Description |
| --- | --- |
| `--config PATH` | Configuration file to create. Defaults to `.agent-policy.yml`. |
| `--state PATH` | Adoption-state path. Defaults to `.agent-policy/adoption.json`. |
| `--apply` | Actually create the validated prepared state. |
| `--toolchain-revision SHA` | Toolchain revision recorded in configuration, lock state, and adoption state. |
| `--profile NAME` | Profile to select. May be specified multiple times. |
| `--primary-instructions PATH` | Existing instruction file to preserve. Defaults to `AGENTS.md`. |
| `--project-policy PATH` | Existing or newly created project-policy path. May be specified multiple times. |
| `--verification-command COMMAND` | Repository verification command. |
| `--no-verification` | Do not configure verification. This is effectively the adoption default. |
| `--preview-output-path PATH` | Destination for shadow instructions. |
| `--skill NAME` | Skill to generate. May be specified multiple times. Defaults to `validate-agent-policy`. |
| `--no-skills` | Do not create generated skills. Mutually exclusive with `--skill`. |

`--primary-instructions` must name an `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, or `.github/copilot-instructions.md` discovered during inspection. Sources under `.agents/policies` or `.agents/skills` are recorded in the inventory and adoption state but cannot be selected as primary instructions. A repository containing only policy or skills cannot run `adopt prepare` until a corresponding instruction file exists.

Multiple project-policy files may be supplied, but `prepare` can create at most one missing file as a new scaffold. Existing policy is left byte-for-byte unchanged and becomes a manifest input. When an existing skill conflicts with the default generated skill, for example a handwritten `.agents/skills/validate-agent-policy/SKILL.md`, specify `--no-skills`.

## `adopt preview`

Validate the immutable-source hashes recorded in prepared state and the consistency of configuration, then regenerate shadow instructions, generated skills, and lock state from the current profiles and project policy. Project policy is an editable manifest input and may be changed after preparation before regenerating the preview.

```bash
agent-policy --repository . adopt preview
agent-policy --repository . adopt preview --state .agent-policy/adoption.json
```

If an immutable source recorded during preparation, such as the primary instructions, has been changed or removed, preview stops with `ADOPTION_SOURCE_CHANGED`.

## `adopt finalize`

Switch a prepared state into the formal managed state. The command is a dry run by default: it validates source hashes, state/configuration agreement, preview freshness, the backup path, and final rendering in a temporary copy only.

```bash
agent-policy --repository . adopt finalize
```

Use `--apply` explicitly to apply the cutover.

```bash
agent-policy --repository . adopt finalize \
  --backup-path .agent-policy/adoption/original/AGENTS.md \
  --apply
```

Finalization treats these changes as one transaction:

- preserve the handwritten primary instructions byte-for-byte at the backup path;
- switch the agent output in `.agent-policy.yml` to the primary-instruction path;
- replace the primary instructions with the generated instructions;
- update `.agent-policy.lock`;
- update the adoption state to `finalized`; and
- remove the shadow preview.

Finalization treats configuration, adoption state, lock state, preview, every immutable source recorded in adoption state, and project policy as one input snapshot. It verifies that the temporary repository matches that snapshot before rendering and re-compares live repository bytes immediately before the first real write. Therefore a change to the primary instructions, additional instructions, handwritten skills, or policy between validation and staging or between staging and the transaction causes cutover to stop. Configuration, adoption state, lock state, preview, and primary instructions must be regular files at their lexical paths. Preparation and preview may preserve a safe repository-internal primary symlink, but before finalization it must be materialized as a regular file with the same intended content. If a strict finalization path is replaced by a symlink or gains a symlinked ancestor, finalization rejects it without mutating the referent. On any transaction failure, including failure of the post-apply `check`, rollback restores only files changed by that transaction. Cutover also refuses an existing backup path or stale preview or lock state.

Main options:

| Option | Description |
| --- | --- |
| `--state PATH` | Prepared adoption-state path. Defaults to `.agent-policy/adoption.json`. |
| `--backup-path PATH` | Destination for the handwritten primary instructions. |
| `--apply` | Actually apply the validated cutover. |

## `validate`

Validate the configuration file and referenced inputs.

```bash
agent-policy --repository . validate
agent-policy --repository . validate --config .agent-policy.yml
```

Validation covers YAML/schema correctness, unknown keys, profiles, policy files, rule IDs, overrides, and input/output path safety.

## `render`

Compose shared and product-specific policy and update generated outputs and `.agent-policy.lock`.

```bash
agent-policy --repository . render
```

Do not edit generated outputs directly. Change input policy or `.agent-policy.yml` and regenerate.

## `check`

Verify read-only that configuration, inputs, lock state, and generated outputs agree.

```bash
agent-policy --repository . check
```

Use this command in CI to detect missed regeneration after policy changes and manual modification of generated outputs.

## JSON output

Use the common `--format json` option when agents or CI need to process diagnostics.

```bash
agent-policy --repository . --format json validate
```

The exit status is nonzero when one or more error diagnostics are present.
