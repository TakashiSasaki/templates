# Bootstrap model

The unrelated `bootstrap-agent-policy` branch is a directly installable onboarding skill package. It contains no policy compiler, renderer, or adoption transaction logic. It reads a manifest that pins one full `main` commit SHA and invokes only routes declared by that immutable trust seed.

## Operational onboarding routes

The bootstrap skill supports two routes through the same pinned CLI revision:

```text
unmanaged repository
  |
  +-- no existing instruction assets --> agent-policy init
  |
  +-- existing instruction assets ----> agent-policy adopt prepare
```

Repository classification is performed by the read-only `agent-policy adopt inspect` command. Automatic route selection is advisory and available only for dry runs. Any mutation must explicitly select `--route init` or `--route adopt`.

The bootstrap script refuses repositories classified as `managed` or `inconsistent`. It does not bypass handwritten-file conflicts, repair partial onboarding state, or infer a destructive operation from a successful inspection.

## Initialization

Initialization is used for an `unmanaged-empty` repository. The bootstrap script invokes the pinned `agent-policy init` route in dry-run mode, or with `--apply` after explicit route selection. Applied initialization creates the manifest, project-policy scaffold, generated instructions, lock file, and normal-operation skills, then requires `agent-policy validate` and `agent-policy check` to succeed.

Existing non-generated instruction conflicts continue to stop initialization. They are not converted into adoption merely because `init` failed; the read-only inspection result determines the permitted route before any mutation.

## Adoption preparation

Adoption is used for an `unmanaged-existing` repository. The bootstrap skill reports discovered instruction sources and requires one supported source to be selected as the primary instructions.

The operational phases are:

1. inspect repository state and sources;
2. run `adopt prepare` in dry-run mode;
3. apply preparation only after explicit `--route adopt --apply` authorization;
4. run `adopt preview` to regenerate and check the prepared preview;
5. help migrate semantic requirements into shared profiles and project policy;
6. review the generated preview against the preserved handwritten sources;
7. invoke `adopt finalize --apply` only after a separate explicit instruction.

A generic bootstrap apply operation may apply adoption preparation and run preview. It never finalizes adoption. The bootstrap manifest deliberately declares no finalization route, so the orchestration script cannot collapse preparation and cutover into one unattended action.

## Repository-state routing

The pinned CLI inspection produces one of four states:

| State | Bootstrap behavior |
|---|---|
| `unmanaged-empty` | Recommend `init`; allow explicit initialization apply |
| `unmanaged-existing` | Recommend `adopt`; allow explicit preparation apply |
| `managed` | Stop bootstrap and use normal managed-repository commands |
| `inconsistent` | Stop mutation and require explicit repair |

The route selected for mutation must match the inspection result. A mismatched explicit route is rejected.

## Control transfer

After initialization, or after adoption has been finalized separately, control transfers to the product repository's committed state:

- `.agent-policy.yml`;
- `.agent-policy.lock`;
- generated agent instructions;
- generated normal-operation skills;
- repository-local tests and CI.

The bootstrap skill is not a runtime dependency of the managed product repository.

During prepared adoption, the bootstrap skill remains an orchestration aid while the product repository already contains an adoption configuration, state record, preview, generated skills, and lock. The handwritten primary instructions remain authoritative until explicit finalization.

## Trust boundary

The bootstrap branch and `main` remain unrelated histories because the onboarding skill is an independently distributed trust seed. The skill contains only the minimum logic needed to validate its manifest, obtain the pinned CLI revision, invoke declared commands, classify outputs, and report results.

Changing the pinned SHA, route declarations, bootstrap safety constraints, skill instructions, invocation script, or bootstrap tests is a trust-anchor change and is reviewed independently from ordinary policy or documentation updates.

The manifest uses a full commit SHA rather than `main`, a tag, a short SHA, or another mutable reference. Initialization and adoption do not justify a third unrelated branch: both routes use the same executable toolchain and differ only in repository state and the safe transition explicitly selected by the user.
