# Bootstrap model

Bootstrap is an operation of the single `skills/agent-policy/` skill. It is not a separately installed skill and it does not contain a second policy compiler, renderer, or migration implementation.

`skills/agent-policy/runtime-manifest.json` pins the reviewed stable `TakashiSasaki/templates` full commit SHA and the SHA-256 of that revision's `requirements-runtime.lock`. The bootstrap operation executes that immutable toolchain through the same persistent runtime cache used for managed operation.

## One onboarding operation: adoption

An unmanaged repository enters agent-policy through adoption. Read-only inspection selects the safe strategy from repository state:

```text
unmanaged repository
  |
  +-- no existing instruction assets --> fresh adoption
  |
  +-- existing instruction assets ----> migration adoption
```

Repository classification is performed by `agent-policy adopt inspect`. The user does not choose between `init` and `adopt`. `--apply` authorizes only the transition shown by inspection and the dry-run plan.

The bootstrap operation refuses repositories classified as `managed` or `inconsistent`. Managed repositories use `scripts/run.py`; inconsistent repositories require explicit repair.

## Fresh adoption

Fresh adoption is used for `unmanaged-empty`. The pinned toolchain may use the hidden `agent-policy init` command internally to create the manifest, project-policy scaffold, generated instructions, lock file, and normal-operation skills. That primitive is an implementation detail, not a user-facing onboarding route.

After fresh adoption is applied, the same pinned runtime must complete `validate` and `check`. Existing conflicting paths stop the operation rather than being overwritten.

## Migration adoption

Migration adoption is used for `unmanaged-existing`. The skill reports discovered instruction sources and requires one supported source to be selected as primary when discovery is ambiguous.

The phases are:

1. inspect repository state and sources;
2. run migration preparation in dry-run mode;
3. apply preparation only after explicit `--apply` authorization;
4. run `adopt preview` to regenerate and check the prepared preview;
5. migrate semantic requirements into shared profiles and project policy;
6. review the generated preview against preserved handwritten sources; and
7. invoke `adopt finalize --apply` only after a separate explicit instruction through `scripts/run.py`.

Generic bootstrap `--apply` may complete fresh adoption or apply migration preparation and preview. It never finalizes migration. `runtime-manifest.json` deliberately declares no finalize route.

## Repository-state routing

| State | Bootstrap behavior |
|---|---|
| `unmanaged-empty` | Select fresh adoption; allow explicit `--apply` |
| `unmanaged-existing` | Select migration adoption; allow explicit preparation `--apply` |
| `managed` | Stop bootstrap and use `scripts/run.py` with `.agent-policy.lock` |
| `inconsistent` | Stop mutation and require explicit repair |

The selected strategy is derived from inspection state, not from a user-supplied route flag.

## Persistent runtime and control transfer

For initial adoption, the skill uses its reviewed stable default pin. After `.agent-policy.lock` exists, managed operation prefers the full SHA recorded by the repository. The same skill therefore remains the entry point before and after adoption; what changes is the authoritative pin.

Runtime identity includes repository, full revision, runtime-lock digest, Python major/minor, and platform. A validated cache hit is reused without network access. A cache miss constructs and verifies a staged runtime before switching it into place.

After fresh adoption, or after migration has been finalized separately, the committed operating records are:

- `.agent-policy.yml`;
- `.agent-policy.lock`;
- generated agent instructions;
- generated normal-operation skills; and
- repository-local tests and CI.

## Integrated trust boundary

Sharing the `policy` history does not make the skill execute the mutable branch tip. `release/toolchain.json` and `skills/agent-policy/runtime-manifest.json` carry the same stable toolchain object. The runtime manifest also binds the stable revision's runtime lock by SHA-256.

The stable candidate is a strict ancestor of the promotion state, avoiding a self-referential pin. Policy CI verifies stable ancestry, the runtime-manifest binding, pinned contracts, and the release-probe dependency environment.

Changes to the stable descriptor, runtime manifest, cache identity, route declarations, skill instructions, orchestration scripts, installer, or their tests are trust-anchor changes and are reviewed independently from ordinary policy text changes.
