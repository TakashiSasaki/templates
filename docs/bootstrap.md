# Bootstrap skill

## Role

`skills/bootstrap-agent-policy/` is an agent skill that inspects a Git repository without `.agent-policy.yml` and adopts it into agent-policy management. Empty repositories use a fresh strategy; repositories with existing handwritten instructions use a migration strategy.

The skill is maintained in the `policy` branch of `TakashiSasaki/templates`, but it never trusts the mutable branch tip at runtime. `bootstrap-manifest.yml` pins a reviewed full commit SHA and the allowed internal CLI routes.

## Install from a reviewed checkout

From a reviewed `policy` commit checkout, run the installer:

```bash
python skills/bootstrap-agent-policy/scripts/install.py \
  /path/to/agent-skills/bootstrap-agent-policy
```

Use `--replace` only when replacing an existing skill with the same identity. The installer refuses replacement when the target `SKILL.md` does not identify this skill.

If a permanent checkout of the whole repository is unnecessary, use a sparse checkout:

```bash
git clone --filter=blob:none --no-checkout \
  --branch policy --single-branch \
  https://github.com/TakashiSasaki/templates.git \
  templates-policy

git -C templates-policy sparse-checkout init --cone
git -C templates-policy sparse-checkout set skills/bootstrap-agent-policy
git -C templates-policy checkout <reviewed-full-commit-sha>

python templates-policy/skills/bootstrap-agent-policy/scripts/install.py \
  /path/to/agent-skills/bootstrap-agent-policy
```

Do not replace `<reviewed-full-commit-sha>` with `policy`, a tag, an abbreviated SHA, or another mutable or ambiguous reference.

## Skill contents

```text
skills/bootstrap-agent-policy/
  SKILL.md
  README.md
  bootstrap-manifest.yml
  scripts/
    bootstrap.py
    install.py
    uninstall.py
```

Repository test `tests/test_bootstrap_skill.py` verifies the manifest, full-SHA pin, state parsing, strategy selection, refusal states, the absence of a finalize route, and post-apply commands.

## Repository inspection and dry run

Run from the installed skill directory:

```bash
python scripts/bootstrap.py --repository /path/to/product
```

The command does not modify files by default. It invokes `agent-policy adopt inspect` through the pinned CLI and reports one of the following states:

| State | Adoption strategy |
|---|---|
| `unmanaged-empty` | fresh adoption |
| `unmanaged-existing` | migration adoption |
| `managed` | stop bootstrap and use normal managed operation |
| `inconsistent` | make no changes; repair partial adoption or unsafe paths first |

The strategy is derived from repository state. There is no user-selectable `init` route.

## Apply fresh adoption

For `unmanaged-empty`, review the dry-run plan and then authorize the inspected transition:

```bash
python scripts/bootstrap.py \
  --repository /path/to/product \
  --apply
```

The bootstrap currently invokes pinned `agent-policy init` as an internal fresh-adoption primitive. After application, `validate` and `check` run through the same pinned toolchain. Initialization is not a separate bootstrap operation.

## Prepare migration adoption of existing instructions

When inspection finds multiple supported instruction files, choose one authoritative primary source:

```bash
python scripts/bootstrap.py \
  --repository /path/to/product \
  --primary-instructions AGENTS.md
```

After reviewing the plan, add `--apply` only when the prepared state should be created:

```bash
python scripts/bootstrap.py \
  --repository /path/to/product \
  --primary-instructions AGENTS.md \
  --apply
```

Application runs `adopt prepare --apply` and then `adopt preview`. The existing primary instructions are not replaced.

After project policy and the preview have been reviewed, `adopt finalize --apply` is a separate explicit action using the CLI from the same repository and full SHA recorded in the manifest. The bootstrap manifest and `scripts/bootstrap.py` do not expose a finalize route.

## Trust boundary

Before adoption, review these components together as the trust seed:

- the safety constraints in `SKILL.md`;
- the repository, full SHA, and internal route set in `bootstrap-manifest.yml`;
- inspection, strategy selection, and application logic in `scripts/bootstrap.py`;
- installer and uninstaller behavior; and
- bootstrap tests.

After fresh adoption or migration finalization, these become the normal operating records:

- `.agent-policy.yml`;
- `.agent-policy.lock`;
- generated agent instructions and normal-operation skills; and
- repository-local CI.

The bootstrap skill is not a runtime dependency of a managed repository.
