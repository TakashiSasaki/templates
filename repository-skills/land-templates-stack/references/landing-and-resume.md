# Landing Boundaries, Resumption, and Handoff

This reference contains detailed procedures for landing stack members under separate authorization, handling stops and resumptions, and completing handoffs. Consult this file only when performing authorized landing, stopping, resuming, or handing off.

## 1. Landing Boundary and Guarded Progression

This Skill does not authorize a merge. Human authorization and the shared gate's guarded execution boundary are separate from implementation, CI, and review completion. In the current maintenance task, never invoke a merge, auto-merge, publication, deployment, or branch-protection mutation.

When a separately authorized future operation lands a member:
1. **Merge Method & Guard**: Use a merge commit and an immutable exact-head guard.
2. **Post-Merge Verification**: Verify merged state, merge method, merge SHA, target ancestry, and intended content before progressing.
3. **Base Retargeting**: Retarget the next member's base to its target authority only when required. Do not rewrite or synchronize its head merely because the base moved. If a provider already retargeted it, inspect the current state and do not repeat the operation.
4. **Repair Discipline**: If a repair is necessary, stop, add a normal commit, identify invalidated evidence, and requalify only the affected scope. Never amend, force-push, or make an appeasement edit to preserve an old evidence binding.

## 2. Stop, Resume, and Handoff Mechanics

### At a Stop
- Preserve the exact reason, affected member, invalidated binding, and next safe action in the provider PR state or adopted Work-ledger surface.

### On Resumption
- Re-read current PR, head, base, target, CI, review, and thread facts live from the provider.
- Restore the ordered stack.
- Do not repeat a merge, review request, or valid evidence acquisition that already happened.
- If a live fact or binding is unknown, fail closed and reacquire the affected evidence.

### Completion States
The completion states remain strictly distinct:
- `implementation complete`
- `validation complete`
- `independent review complete`
- `merge authorized`
- `merged`

A human handoff or review-request event is not acceptance or merge authorization. The final report must state which state was reached and must not claim a final authority merge SHA before an actual authorized merge has taken place.

### Recursion Prohibition
This Skill must not call itself, and the local shim must not call the local shim. The only semantic call from this procedure is to the separately pinned `pr-merge-gate`; that gate does not delegate back here.
