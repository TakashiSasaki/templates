# Bootstrap model

The onboarding trust seed is stored at `skills/bootstrap-agent-policy/` in `TakashiSasaki/templates:policy`. It contains no policy compiler, renderer, or adoption transaction implementation. It validates a manifest that pins one full commit SHA and invokes only the routes declared by that immutable trust record.

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

Initialization is used for an `unmanaged-empty` repository. The bootstrap script invokes pinned `agent-policy init` in dry-run mode, or with `--apply` after explicit route selection. Applied initialization creates the manifest, project-policy scaffold, generated instructions, lock file, and normal-operation skills, then requires `agent-policy validate` and `agent-policy check` to succeed.

Existing non-generated instruction conflicts continue to stop initialization. They are not converted into adoption merely because `init` failed; the read-only inspection result determines the permitted route before mutation.

## Adoption preparation

Adoption is used for an `unmanaged-existing` repository. The bootstrap skill reports discovered instruction sources and requires one supported source to be selected as the primary instructions.

The operational phases are:

1. inspect repository state and sources;
2. run `adopt prepare` in dry-run mode;
3. apply preparation only after explicit `--route adopt --apply` authorization;
4. run `adopt preview` to regenerate and check the prepared preview;
5. help migrate semantic requirements into shared profiles and project policy;
6. review the generated preview against preserved handwritten sources;
7. invoke `adopt finalize --apply` only after a separate explicit instruction.

A generic bootstrap apply operation may apply adoption preparation and run preview. It never finalizes adoption. The bootstrap manifest deliberately declares no finalization route.

## Repository-state routing

| State | Bootstrap behavior |
|---|---|
| `unmanaged-empty` | Recommend `init`; allow explicit initialization apply |
| `unmanaged-existing` | Recommend `adopt`; allow explicit preparation apply |
| `managed` | Stop bootstrap and use managed-repository commands |
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

## Integrated trust boundary

Sharing the `policy` history does not make the bootstrap script execute the branch tip. `skills/bootstrap-agent-policy/bootstrap-manifest.yml` pins `TakashiSasaki/templates` at the full revision `270645381849431b922bee87afecedc540e52ed1`. That revision contains the migrated toolchain identity and precedes the commit that adds the bootstrap package, avoiding a self-referential pin.

Changing the pinned SHA, repository, route declarations, skill instructions, orchestration script, installer, or bootstrap tests is a trust-anchor change and is reviewed independently from ordinary policy text changes.

The manifest uses a full commit SHA rather than `policy`, `main`, a tag, a short SHA, or another mutable reference. Initialization and adoption use the same executable toolchain and differ only in repository state and the safe transition explicitly selected by the user.
