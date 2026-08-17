# bootstrap-agent-policy

This directory is the installable trust seed for adopting repositories into the policy toolchain maintained in `TakashiSasaki/templates` branch `policy`.

The skill contains only manifest validation and orchestration needed to invoke one immutable policy revision. Policy compilation and migration transactions remain in the pinned `agent-policy` executable.

## Install from a policy checkout

From a checkout containing this directory:

```bash
python skills/bootstrap-agent-policy/scripts/install.py \
  /path/to/agent-skills/bootstrap-agent-policy
```

Use `--replace` only to replace a directory that is already identified by its `SKILL.md` as this skill.

## Inspect and dry-run

Dry-run is the default. The script invokes pinned `agent-policy adopt inspect`, reports repository state and discovered sources, selects the safe adoption strategy, and runs its dry-run plan.

```bash
python scripts/bootstrap.py --repository /path/to/product
```

The states map to adoption strategies as follows:

- `unmanaged-empty`: fresh adoption;
- `unmanaged-existing`: migration adoption;
- `managed`: stop because bootstrap is no longer required;
- `inconsistent`: stop and repair or remove partial/generated artifacts explicitly.

There is no user-selectable `init` route. Fresh initialization is an implementation detail of adoption.

## Apply fresh adoption

For an empty unmanaged repository, review the dry-run plan and then apply the inspected transition:

```bash
python scripts/bootstrap.py \
  --repository /path/to/product \
  --apply
```

The bootstrap uses the pinned `agent-policy init` primitive internally, then runs `agent-policy validate` and `agent-policy check`. Users do not select initialization as a separate onboarding operation.

## Prepare migration adoption of existing instructions

If inspection reports more than one supported instruction file, select the primary source:

```bash
python scripts/bootstrap.py \
  --repository /path/to/product \
  --primary-instructions AGENTS.md
```

Apply only after reviewing the preparation plan:

```bash
python scripts/bootstrap.py \
  --repository /path/to/product \
  --primary-instructions AGENTS.md \
  --apply
```

This applies `agent-policy adopt prepare` and then runs `agent-policy adopt preview`. It preserves the primary handwritten instructions and does not finalize the cutover. Finalization requires a separate explicit invocation of `agent-policy adopt finalize --apply` using the exact repository and full revision recorded in `bootstrap-manifest.yml`.

## Trust boundary

`bootstrap-manifest.yml` pins a full commit SHA and declares only inspection, fresh-adoption preparation, migration-adoption preparation/preview, validation, and check routes. The fresh strategy currently delegates to the pinned `agent-policy init` primitive, but that primitive is not exposed as a bootstrap route. The manifest deliberately contains no finalization route. After successful fresh adoption or completed migration adoption, the product repository's `.agent-policy.yml` and `.agent-policy.lock` become the normal trust and reproducibility records.
