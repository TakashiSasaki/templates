# Bootstrap model

The unrelated `bootstrap-agent-policy` branch is a directly installable onboarding skill package. It contains no policy compiler, renderer, or adoption transaction logic. It reads a manifest that pins one full `main` commit SHA and invokes only that immutable revision.

## Onboarding routes

The bootstrap skill supports two routes through the same pinned CLI:

```text
unmanaged repository
  |
  +-- no existing instruction assets --> agent-policy init
  |
  +-- existing instruction assets ----> agent-policy adopt
```

Repository classification is performed by a read-only CLI inspection command. Automatic selection is advisory only. A mutation must explicitly select initialization or adoption.

## Initialization

Initialization is used when no conflicting handwritten instruction output exists. It creates the manifest, project-policy scaffold, generated instructions, lock file, and normal-operation skills. Existing non-generated output conflicts continue to stop initialization.

## Adoption

Adoption is used when a repository already contains handwritten instructions or related policy assets. The skill helps interpret those assets and invokes deterministic CLI phases from `main`:

1. inspect repository state;
2. prepare an adoption scaffold and non-conflicting preview;
3. help migrate semantic requirements into shared profiles and project policy;
4. regenerate and review the preview;
5. invoke finalization only after a separate, explicit instruction.

A generic bootstrap `--apply` operation may apply initialization or adoption preparation. It must not finalize adoption automatically.

## Control transfer

After initialization or completed adoption, control transfers to the product repository's committed state:

- `.agent-policy.yml`;
- `.agent-policy.lock`;
- generated agent instructions;
- generated normal-operation skills;
- repository-local tests and CI.

The bootstrap skill is not a runtime dependency of the managed product repository.

## Trust boundary

The bootstrap branch and `main` remain unrelated histories because the onboarding skill is an independently distributed trust seed. The skill contains only the minimum logic needed to validate its manifest, obtain the pinned CLI revision, invoke explicit commands, and report results.

CLI adoption support is merged and tested on `main` before the bootstrap manifest is updated. Changing the pinned SHA, bootstrap safety constraints, or invocation script is a trust-anchor change and is reviewed independently from ordinary policy updates.

Initialization and adoption do not justify a third unrelated branch. They use the same executable toolchain and differ only in the repository state and safe transition selected by the skill.
