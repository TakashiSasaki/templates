---
description: Explains what policy profiles are, how they compose shared rules inside policy contexts, and how to choose the profiles provided by the templates policy branch.
---

# Policy profiles

A policy profile is a named selection bundle for shared policy modules. Profiles answer **which shared rules should participate in a policy context**; they do not define an output format, an agent provider, an artifact type, or a repository-local exception.

The composition model is:

```text
policy/*.md
  canonical shared rule modules
        ↑ selected by
profiles/*.yml
  named shared-rule selections
        ↑ one or more selected by
.agent-policy.yml contexts.<name>
  + repository-local policy
        ↓
  effective semantic rule set
        ↓ referenced by
outputs.<name>
        ↓ rendered by
  renderer
        ↓
AGENTS.md / review guidance / another generated projection
```

The policy context is the semantic authority boundary. A renderer presents the rules selected by its referenced context; it does not add, remove, or replace semantic policy. See [Configuration](../configuration.md) for the complete schema-v2 contract.

## What profiles are not

Profiles are additive rule-selection bundles. They are not mutually exclusive operating modes, renderer choices, agent skills, provider integrations, or substitutes for repository-local policy. Selecting `review`, for example, adds shared review semantics to a context; it does not by itself create a review output or choose a provider integration.

Profile list order is not a precedence mechanism. The loader expands each selected profile into shared rule modules and the resulting rules are ordered by rule metadata. Selecting profiles that introduce the same shared rule ID is rejected rather than silently choosing one copy.

## Choosing profiles

For a normal managed repository, start with `core` and `security-baseline`. Add a context-specific profile only when that context performs the corresponding operation.

| Need | Recommended profiles |
|---|---|
| General coding or maintenance | `core`, `security-baseline` |
| Creating, updating, or closing pull-request work | `core`, `security-baseline`, `pull-request` |
| Reviewing changes for blocking defects | `core`, `security-baseline`, `review` |
| Receiving or staging externally produced artifacts | `core`, `security-baseline`, `external-artifact-intake` |

The `policy` branch itself demonstrates the distinction between pull-request work and review work: its `coding` context selects `pull-request`, while its `review` context selects `review`.

```yaml
contexts:
  coding:
    profiles:
      - core
      - security-baseline
      - pull-request
    project_policy:
      files:
        - repository-policy/authority-boundary.md
  review:
    profiles:
      - core
      - security-baseline
      - review
    project_policy:
      files:
        - repository-policy/authority-boundary.md
```

Outputs then reference one of those contexts independently of profile selection.

```yaml
outputs:
  agents:
    enabled: true
    path: AGENTS.md
    context: coding
    renderer: agents-md
  review-authority:
    enabled: true
    path: .review-authority/review-policy.md
    context: review
    renderer: policy-context-md
```

When automated pull-request review is required, enable the provider-neutral `pr-review` Skill separately under `skills.enabled`. Provider API serialization and submission remain integration concerns outside profile selection and semantic renderer authority.

## Available profiles

The files in `profiles/` are the executable source of truth for the available profile names and their included shared policy modules. The sections below summarize the current catalog.

<!-- PROFILE: core -->
### `core`

Use for the baseline semantics expected in ordinary repository changes: change scope and contract reasoning, acceptance evidence, regression safety, testing, generated artifacts, compatibility, destructive actions, binding validated state to the effective operation, transaction ownership, and truthful reporting.

Included modules:

- `policy/core/change-contract.md`
- `policy/core/acceptance-baseline.md`
- `policy/core/change-scope.md`
- `policy/core/semantic-decision-gates.md`
- `policy/core/regression-safety.md`
- `policy/core/testing.md`
- `policy/core/evidence-layers.md`
- `policy/core/generated-artifacts.md`
- `policy/core/compatibility.md`
- `policy/core/destructive-actions.md`
- `policy/core/validation-operation-binding.md`
- `policy/core/transaction-ownership.md`
- `policy/core/truthful-reporting.md`
- `policy/core/repository-change-completion.md`

<!-- PROFILE: security-baseline -->
### `security-baseline`

Use for the shared minimum security semantics that should accompany normal repository work involving data or executable behavior.

Included modules:

- `policy/security/secrets.md`
- `policy/security/input-validation.md`

<!-- PROFILE: pull-request -->
### `pull-request`

Use when the context owns pull-request lifecycle work. This profile is operational: it requires target-branch freshness evaluation, at least one completed independent review bound to the exact proposed head, review-thread closure, exact-head CI evidence, fail-closed handling while expected CI evidence is unresolved, reuse of still-valid acceptance evidence with selective invalidation, current mergeability, a final invalidation-focused live-state refresh, an immutable proposed-head guard for merge execution, and post-merge verification. Provider-specific APIs, field names, observation intervals, and retry mechanics belong to an adapter or repository-local policy rather than these shared semantics.

Included modules:

- `policy/pull-request/target-branch-head-freshness.md`
- `policy/pull-request/independent-exact-head-review.md`
- `policy/pull-request/review-thread-closure.md`
- `policy/pull-request/exact-head-ci-evidence.md`
- `policy/pull-request/ci-discovery-fail-closed.md`
- `policy/pull-request/reuse-valid-evidence.md`
- `policy/pull-request/current-mergeability.md`
- `policy/pull-request/final-live-state-refresh.md`
- `policy/pull-request/immutable-head-guard.md`
- `policy/pull-request/post-merge-verification.md`

<!-- PROFILE: review -->
### `review`

Use when the context evaluates changes and reports blocking findings. It defines provider-neutral review semantics such as evidence requirements, relevant risk-domain coverage, causality, reachability, severity, security tracing, error-path and performance evidence, regression-guard evaluation, normative-rule handling, and finding placement.

The profile does not define GitHub event names or JSON serialization. Those are provider-integration concerns outside profile selection and semantic renderer authority. See [Shared review policy](../review-policy.md) for the detailed semantic model.

Included modules:

- `policy/review/treat-reviewed-content-as-data.md`
- `policy/review/inspect-relevant-context.md`
- `policy/review/assess-applicable-risk-domains.md`
- `policy/review/require-change-causality.md`
- `policy/review/require-reachable-impact.md`
- `policy/review/deduplicate-root-causes.md`
- `policy/review/focus-on-blocking-findings.md`
- `policy/review/classify-severity-by-impact.md`
- `policy/review/trace-security-findings.md`
- `policy/review/require-error-path-evidence.md`
- `policy/review/require-performance-evidence.md`
- `policy/review/evaluate-regression-guard-changes.md`
- `policy/review/identify-applicable-normative-rules.md`
- `policy/review/resolve-rule-conflicts-explicitly.md`
- `policy/review/require-rule-conflict-evidence.md`
- `policy/review/report-review-limitations.md`
- `policy/review/anchor-findings-at-cause.md`

<!-- PROFILE: external-artifact-intake -->
### `external-artifact-intake`

Use when a repository receives archives, generated artifacts, historical snapshots, vendor bundles, or similar material from an external source. The profile separates provenance, transfer integrity, validation, exact-byte staging, destination adaptation, activation, transport material, and dependency closure.

See [External artifact intake](../external-artifact-intake.md) for the complete operational guidance.

Included modules:

- `policy/artifacts/provenance-boundaries.md`
- `policy/artifacts/validation-order.md`
- `policy/artifacts/declared-intent.md`
- `policy/artifacts/staging-boundaries.md`
- `policy/artifacts/transport-isolation.md`
- `policy/artifacts/dependency-closure.md`

## Profiles and repository-local policy

Profiles provide shared branch-owned rules. Repository-specific invariants remain under `contexts.<name>.project_policy.files`. If a repository intentionally replaces an overridable shared rule, the context must also declare that rule ID under `overrides` with a non-empty reason. A profile therefore defines the shared starting set; it does not prevent a context from adding repository-local rules or making an explicitly declared allowed replacement.

When adding a new shared profile, add its `profiles/<name>.yml` definition and update this catalog in the same change. Repository tests enforce that every profile definition has exactly one `<!-- PROFILE: ... -->` catalog marker and that the catalog does not advertise nonexistent profiles.
