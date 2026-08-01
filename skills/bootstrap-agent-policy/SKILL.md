---
name: bootstrap-agent-policy
description: Inspect an unmanaged Git repository and use one pinned TakashiSasaki/templates policy revision to initialize an empty repository or prepare a reviewable adoption of existing handwritten agent instructions.
---

# Bootstrap agent policy

Use this skill when a Git repository does not contain `.agent-policy.yml` and the user asks to adopt the shared policy system maintained in `TakashiSasaki/templates` branch `policy`.

## Procedure

1. Locate the target Git repository root.
2. Run `python scripts/bootstrap.py --repository <root>` without `--apply`.
3. Review the reported repository state, discovered instruction sources, recommended route, and the dry-run plan from the pinned toolchain.
4. For `unmanaged-empty`, apply initialization only after an explicit request:
   `python scripts/bootstrap.py --repository <root> --route init --apply`.
5. For `unmanaged-existing`, select one discovered instruction file as the primary source and review adoption preparation:
   `python scripts/bootstrap.py --repository <root> --route adopt --primary-instructions <path>`.
6. Apply adoption preparation only after an explicit request by adding `--apply`. This creates the adoption state and generated preview, then runs `agent-policy adopt preview`; it does not replace the primary instructions.
7. Help move repository-specific semantic requirements into the project policy and review the generated preview. Do not silently translate or discard handwritten requirements.
8. Run `agent-policy adopt finalize --apply` from the exact toolchain repository and full revision in `bootstrap-manifest.yml` only after a separate explicit instruction to finalize the reviewed adoption.
9. Require `agent-policy validate` and `agent-policy check` to succeed after initialization or completed finalization. Report the pinned toolchain revision, selected route, affected files, and unresolved state.

## Safety constraints

- Execute only the repository and full commit SHA in `bootstrap-manifest.yml`; never replace them with `policy`, another branch, a tag, a short SHA, or another mutable reference.
- Treat automatic route selection as dry-run advice only. Any mutation requires explicit `--route init` or `--route adopt`.
- `scripts/bootstrap.py` may apply initialization or adoption preparation only. It must never invoke adoption finalization.
- Do not bypass a handwritten-file conflict or an inconsistent repository state.
- Do not commit, push, create branches, or modify GitHub settings unless separately requested.
- Do not overwrite, delete, or semantically reinterpret existing non-generated agent instructions without explicit review.
- Treat bootstrap-script, manifest, route, pinned revision, or safety-constraint updates as trust-anchor changes requiring explicit review.
