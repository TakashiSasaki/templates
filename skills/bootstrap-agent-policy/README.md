# bootstrap-agent-policy

This directory is the installable trust seed for onboarding repositories to the policy toolchain maintained in `TakashiSasaki/templates` branch `policy`.

The skill contains only the manifest validation and orchestration needed to invoke one immutable policy revision. Policy compilation and adoption transactions remain in the pinned `agent-policy` executable.

## Install from a policy checkout

From a checkout containing this directory:

```bash
python skills/bootstrap-agent-policy/scripts/install.py \
  /path/to/agent-skills/bootstrap-agent-policy
```

Use `--replace` only to replace a directory that is already identified by its `SKILL.md` as this skill.

## Inspect and dry-run

Dry-run is the default. The script invokes pinned `agent-policy adopt inspect`, reports the repository state and discovered sources, recommends `init` or `adopt`, and runs that route without applying changes.

```bash
python scripts/bootstrap.py --repository /path/to/product
```

The states are:

- `unmanaged-empty`: recommend `init`;
- `unmanaged-existing`: recommend adoption preparation;
- `managed`: stop because bootstrap is no longer required;
- `inconsistent`: stop and repair or remove partial/generated artifacts explicitly.

Automatic route selection is advisory and available only for dry runs. Applying a route requires an explicit route selection.

## Apply initialization

```bash
python scripts/bootstrap.py \
  --repository /path/to/product \
  --route init \
  --apply
```

After initialization, the script runs `agent-policy validate` and `agent-policy check` with the same pinned toolchain.

## Prepare adoption of existing instructions

Select one instruction file reported by inspection as the primary source:

```bash
python scripts/bootstrap.py \
  --repository /path/to/product \
  --route adopt \
  --primary-instructions AGENTS.md
```

Apply only after reviewing the preparation plan:

```bash
python scripts/bootstrap.py \
  --repository /path/to/product \
  --route adopt \
  --primary-instructions AGENTS.md \
  --apply
```

This applies `agent-policy adopt prepare` and then runs `agent-policy adopt preview`. It preserves the primary handwritten instructions and does not finalize the cutover. Finalization requires a separate explicit invocation of `agent-policy adopt finalize --apply` using the exact repository and full revision recorded in `bootstrap-manifest.yml`.

## Trust boundary

`bootstrap-manifest.yml` pins a full commit SHA and declares only inspection, initialization, adoption preparation/preview, validation, and check routes. It deliberately contains no finalization route. After successful initialization or completed adoption, the product repository's `.agent-policy.yml` and `.agent-policy.lock` become the normal trust and reproducibility records.
