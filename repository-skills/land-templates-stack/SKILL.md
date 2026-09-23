---
name: land-templates-stack
description: Execute the repository-maintainer landing procedure for a single or stacked templates authority change with immutable source binding, selective evidence reuse, and human-controlled merge boundaries.
---

# Land the templates maintenance stack

Use this Skill only for maintaining the `TakashiSasaki/templates` repository. It is not a product-repository adoption or deployment procedure.

## Authority Boundaries

- Repository-specific landing rules are canonical in `repository-policy/stacked-pr-landing.md`.
- The shared acceptance contract is canonical in `skills/pr-merge-gate/SKILL.md`.
- Review scope selection is canonical in `repository-skills/land-templates-stack/scripts/plan_review_scope.py`.
- In consumer repositories (e.g. `site`, `composition`), inspect the revision snapshot with `git show <revision>:repository-policy/stacked-pr-landing.md` or the consumer's same-named `repository-policy/` file.
- This Skill orchestrates those authorities, does not copy their acceptance semantics, and does not duplicate or alter their acceptance semantics.

## Non-Negotiable Invariants

1. **Immutable Source Requirement**: Every consumer entrypoint must provide a version-2 `source.json` for this Skill and a separate `source.json` for `pr-merge-gate`. Verify each reference against local Git object storage before reading instructions or executing code. Never execute unverified mutable local files.
2. **Prohibition on Cross-Authority History Mixing**: Authority histories must remain independent. Never introduce cross-authority Git merges, rebases, or cherry-picks.
3. **Observation Before Mutation**: Observe read-only live PR and Git state using `repository-skills/land-templates-stack/scripts/observe_pr_state.py` before routing or planning. Never turn an unchanged or unknown result into approval.
4. **Planner and Shared Gate Ownership**: Review routing belongs to the pinned scope planner (`scripts/plan_review_scope.py`) as the canonical **adaptive scope selection** guard; invoke the pinned shared `pr-merge-gate` for each member rather than reimplementing CI, review, evidence-applicability, or guarded-merge rules. The observer, orchestrator, and this Skill cannot manufacture acceptance.
5. **Explicit Human Merge Boundary**: This Skill does not authorize a merge. Merge authorization and Policy self-host adoption require separate, authenticated human authorization.
6. **Stop and Fail-Closed Resumption**: Stop immediately on missing evidence, unknown bindings, or contradictory states. Record exact reasons in durable PR or Work-ledger state. On resume, re-read live state rather than guessing.
7. **No Circular Landing Calls**: This Skill must not call itself, and the local shim must not call the local shim. The only semantic call from this procedure is to the separately pinned `pr-merge-gate`; that gate does not delegate back here.

## What a Maintainer Must Never Infer or Authorize

An executing maintainer or automated agent must **never**:
- Infer merge authorization, auto-merge, or branch-protection mutation from test passes or review approval.
- Infer that passing CI or unchanged code constitutes review acceptance.
- Synthesize missing acceptance identities from provider display names.
- Infer Policy self-host adoption (`B1`) or cross-authority adoption without an explicit authority input.
- Make appeasement edits or rewrite history to preserve invalid or stale evidence bindings.
- Load all detailed procedures eagerly when only a specific operational phase is being performed.

## High-Level Workflow Phases

```
Phase 1: Source Trust & Verification
   ↓
Phase 2: Finding-Family Audit & Review Readiness
   ↓
Phase 3: Stack Observation & Member Qualification
   ↓
Phase 4: Authorized Landing, Resumption & Handoff
   ↓
Phase 5: Maintainer CLI & Isolated Execution
```

## Progressive Disclosure Reference Routing

Detailed operational procedures are conditionally factored into focused references. **Do not load all references into context.** Consult only the reference matching your current phase:

| Phase / Operational Context | When to Consult | Canonical Reference File |
|---|---|---|
| **Phase 1: Source Trust & Verification** | When verifying immutable source manifests, resolving Git blobs, or operating the pre-request scope planner guard | [`references/source-trust.md`](repository-skills/land-templates-stack/references/source-trust.md) |
| **Phase 2: Finding-Family Closure** | When closing a material review finding family in `work.closure_audit` or auditing review readiness before requesting expensive review | [`references/finding-family-closure.md`](repository-skills/land-templates-stack/references/finding-family-closure.md) |
| **Phase 3: Observation & Qualification** | When invoking `scripts/observe_pr_state.py`, qualifying members bottom-up through `pr-merge-gate`, or evaluating evidence applicability | [`references/qualification-and-evidence.md`](repository-skills/land-templates-stack/references/qualification-and-evidence.md) |
| **Phase 4: Landing & Resumption** | When landing an authorized member under exact-head guards, stopping, resuming, or reporting final handoff state | [`references/landing-and-resume.md`](repository-skills/land-templates-stack/references/landing-and-resume.md) |
| **Phase 5: Maintainer CLI Execution** | When executing the maintainer workflow via `scripts/run_maintainer_workflow.py` or configuring `live_review_adapter.py` | [`references/maintainer-entrypoint.md`](repository-skills/land-templates-stack/references/maintainer-entrypoint.md) |

## Stop, Resume, and Cumulative Evidence Summary

- **At a Stop**: Record the exact reason, affected PR member, invalidated binding, and next safe action in provider PR state or the Work ledger.
- **On Resume**: Re-read live PR, base, head, target, CI, and thread facts. Restore the ordered stack without repeating already-completed merges, review requests, or valid evidence acquisitions.
- **Cumulative Evidence Distinctions**:
  - A runtime-changing lower member followed by a docs-only member must retain runtime coverage in the cumulative final state.
  - A tip-only approval does not establish cumulative coverage across lower stack members.
  - The final tip's success does not prove every lower prefix was valid.
  - A newly started workflow run does not inherit the scope of a cancelled run; distinguish runs started and completed from elapsed waiting.
- **Completion States**: Keep distinct: `implementation complete`, `validation complete`, `independent review complete`, `merge authorized`, and `merged`. Never report a merged state without an actual authorized merge commit.
