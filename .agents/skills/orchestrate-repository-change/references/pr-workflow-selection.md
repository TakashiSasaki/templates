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

The selected progression controls how implementation members are constructed. The selected completion controls where the agent stops and what evidence it may report. Implementation completion, validation completion, review completion, merge authorization, and merged state remain distinct.
