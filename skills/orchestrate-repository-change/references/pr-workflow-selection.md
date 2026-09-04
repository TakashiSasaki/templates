<!-- agent-policy-generated: true -->
# Workflow selection

This reference is provider-neutral guidance for the strategy-neutral repository-change dispatcher. It does not create a policy profile, alter acceptance requirements, select an agent provider, or authorize a merge.

Choose progression and completion as independent dimensions:

| Dimension | Values |
| --- | --- |
| Progression | serial-pr or stacked-pr |
| Completion | agent-review-and-merge or human-handoff |

Resolve each value by the following precedence:

1. explicit task instruction;
2. applicable repository-local policy;
3. repository-declared default;
4. agent choice only when explicitly permitted.

A profile is a shared normative rule-selection bundle. It is not a workflow mode. Do not create one profile for every combination of progression, completion, provider, or Skill selection.

The selected progression controls how implementation members are constructed. The selected completion controls where the agent stops and what evidence it may report. Completion takes precedence over progression when deciding whether the agent initiates merge-acceptance review acquisition or performs a merge. Creating the pull-request artifact required by a progression path is not itself authorization to initiate review; use a non-review-triggering pull-request state when the provider or repository would otherwise invoke review automatically. Implementation completion, validation completion, review completion, merge authorization, and merged state remain distinct.

## Strategy matrix

| Progression | Completion | Construction | Review acquisition | Merge boundary |
| --- | --- | --- | --- | --- |
| serial-pr | agent-review-and-merge | implement and validate one member, then open its pull request without review acquisition | establish completed independent exact-head review for the member | guarded merge, then begin the next member |
| serial-pr | human-handoff | implement and validate the current member, then open its pull request without merge-acceptance review acquisition | no merge-acceptance review by default; an explicit task may authorize one final diagnostic whole-stack audit when a stack exists | stop at HANDOFF_READY; leave the member open and unmerged |
| stacked-pr | agent-review-and-merge | construct and validate dependent members without review latency blocking construction | establish individual independent exact-head review per member, or explicit cumulative stack coverage satisfying canonical bindings | guarded bottom-up merge after applicability evaluation |
| stacked-pr | human-handoff | construct and validate the ordered stack | no merge-acceptance review by default; an explicit task may authorize one final diagnostic whole-stack audit after the complete stack is stable | stop at HANDOFF_READY; leave the whole stack open and unmerged |

An explicitly authorized final whole-stack audit under human-handoff is diagnostic. It is not ordinary per-member merge-acceptance evidence, does not authorize merge, does not waive later exact-head review requirements, and must not create a review-retry loop. The workflow-specific stacked procedure may impose exact-head CI sequencing before that audit is requested.

Cumulative review is an optional evidence-coverage mechanism for a stack, not a property of stacked progression. A stacked member may instead rely on its own completed independent exact-head review. A tip-only review or approval event is not cumulative coverage for lower members.
