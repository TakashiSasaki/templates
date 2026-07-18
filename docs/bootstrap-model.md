# Bootstrap model

!!! warning "Current implementation supports initialization only"
    The published `bootstrap-agent-policy` skill currently invokes only `agent-policy init`. This page also defines a planned two-route bootstrap model, but the adoption route is not executable until the CLI implementation, pinned manifest revision, skill instructions, bootstrap script, and tests have all been updated and reviewed.

The unrelated `bootstrap-agent-policy` branch is a directly installable onboarding skill package. It contains no policy compiler, renderer, or adoption transaction logic. It reads a manifest that pins one full `main` commit SHA and invokes only that immutable revision.

## Current implementation

The current bootstrap skill has one operational route:

```text
unmanaged repository
  |
  +-- no conflicting instruction assets --> agent-policy init
  |
  +-- existing instruction assets --------> stop and report conflict
```

The current bootstrap script always constructs an `agent-policy init` invocation. It does not run repository classification, select `agent-policy adopt`, prepare an adoption preview, or finalize adoption. Existing non-generated output conflicts therefore stop initialization rather than selecting another route.

## Planned onboarding routes

The target bootstrap model adds a second route through the same pinned CLI revision:

```text
unmanaged repository
  |
  +-- no existing instruction assets --> agent-policy init
  |
  +-- existing instruction assets ----> agent-policy adopt
```

In the planned model, repository classification is performed by a read-only CLI inspection command. Automatic selection is advisory only. A mutation must explicitly select initialization or adoption.

This route becomes operational only after all of the following trust-anchor changes are complete:

1. CLI adoption support is merged and tested on `main`;
2. `bootstrap-manifest.yml` pins the exact reviewed implementation commit;
3. `SKILL.md` documents repository classification and explicit route selection;
4. `scripts/bootstrap.py` invokes the selected route without bypassing handwritten-file conflicts;
5. bootstrap tests cover initialization, adoption preparation, refusal states, and the prohibition on automatic finalization.

Until then, this section is a design specification rather than current bootstrap behavior.

## Initialization

Initialization is the current operational route when no conflicting handwritten instruction output exists. It creates the manifest, project-policy scaffold, generated instructions, lock file, and normal-operation skills. Existing non-generated output conflicts continue to stop initialization.

## Planned adoption extension

Adoption is intended for repositories that already contain handwritten instructions or related policy assets. After the planned bootstrap extension is implemented, the skill will help interpret those assets and invoke deterministic CLI phases from the pinned `main` revision:

1. inspect repository state;
2. prepare an adoption scaffold and non-conflicting preview;
3. help migrate semantic requirements into shared profiles and project policy;
4. regenerate and review the preview;
5. invoke finalization only after a separate, explicit instruction.

In that future implementation, a generic bootstrap `--apply` operation may apply initialization or adoption preparation. It must not finalize adoption automatically.

## Control transfer

After current initialization, or after the future adoption flow has been completed, control transfers to the product repository's committed state:

- `.agent-policy.yml`;
- `.agent-policy.lock`;
- generated agent instructions;
- generated normal-operation skills;
- repository-local tests and CI.

The bootstrap skill is not a runtime dependency of the managed product repository.

## Trust boundary

The bootstrap branch and `main` remain unrelated histories because the onboarding skill is an independently distributed trust seed. The skill contains only the minimum logic needed to validate its manifest, obtain the pinned CLI revision, invoke explicit commands, and report results.

CLI adoption support is merged and tested on `main` before the bootstrap manifest is updated. Changing the pinned SHA, bootstrap safety constraints, skill routing instructions, invocation script, or bootstrap tests is a trust-anchor change and is reviewed independently from ordinary policy updates.

Initialization and adoption do not justify a third unrelated branch. The planned routes use the same executable toolchain and differ only in the repository state and safe transition selected by the skill.