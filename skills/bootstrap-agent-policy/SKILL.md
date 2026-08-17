---
name: bootstrap-agent-policy
description: Inspect an unmanaged Git repository and adopt one pinned TakashiSasaki/templates policy revision, using a fresh strategy for empty repositories and a migration strategy when handwritten agent instructions already exist.
---

# Bootstrap agent policy

Use this skill when a Git repository does not contain `.agent-policy.yml` and the user asks to adopt the shared policy system maintained in `TakashiSasaki/templates` branch `policy`.

## Procedure

1. Locate the target Git repository root.
2. Run `python scripts/bootstrap.py --repository <root>` without `--apply`.
3. Review the reported repository state, discovered instruction sources, selected adoption strategy, and dry-run plan from the pinned toolchain.
4. For `unmanaged-empty`, the bootstrap uses the fresh-adoption strategy. Apply it only after an explicit request by adding `--apply`. The internal `agent-policy init` primitive is an implementation detail of this strategy, not a separate bootstrap route.
5. For `unmanaged-existing`, select one discovered instruction file as the primary source when discovery is ambiguous:
   `python scripts/bootstrap.py --repository <root> --primary-instructions <path>`.
6. Apply migration adoption preparation only after an explicit request by adding `--apply`. This creates the adoption state and generated preview, then runs `agent-policy adopt preview`; it does not replace the primary instructions.
7. Help move repository-specific semantic requirements into the project policy and review the generated preview. Do not silently translate or discard handwritten requirements.
8. Run `agent-policy adopt finalize --apply` from the exact toolchain repository and full revision in `bootstrap-manifest.yml` only after a separate explicit instruction to finalize a reviewed migration adoption.
9. Require `agent-policy validate` and `agent-policy check` to succeed after fresh adoption or completed migration finalization. Report the pinned toolchain revision, selected adoption strategy, affected files, and unresolved state.

## Safety constraints

- Execute only the repository and full commit SHA in `bootstrap-manifest.yml`; never replace them with `policy`, another branch, a tag, a short SHA, or another mutable reference.
- Treat `--apply` as authorization for the inspected adoption transition. Do not require the user to choose between initialization and adoption routes.
- `scripts/bootstrap.py` may complete fresh adoption or apply migration-adoption preparation only. It must never invoke adoption finalization.
- Do not bypass a handwritten-file conflict or an inconsistent repository state.
- Do not commit, push, create branches, or modify GitHub settings unless separately requested.
- Do not overwrite, delete, or semantically reinterpret existing non-generated agent instructions without explicit review.
- Treat bootstrap-script, manifest, strategy, pinned revision, or safety-constraint updates as trust-anchor changes requiring explicit review.
