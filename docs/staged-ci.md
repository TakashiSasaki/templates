# Staged CI and CI preflight

This page explains the execution model behind the canonical `pull-request.use-staged-ci-with-preflight` rule. It is explanatory guidance, not a second semantic authority. Repository-local workflows, canonical Policy rules, and explicit task requirements remain authoritative.

## Why stage CI

A repository often mixes very cheap checks with much more expensive integration, browser, compatibility, publication, or platform-matrix verification. Running every expensive check for every transient construction head increases feedback latency and consumes qualification work on identities already expected to move. The opposite optimization—skipping validation merely because it is expensive—weakens acceptance.

Staged CI separates **early falsification** from **final qualification**. Cheap deterministic checks reject obviously invalid candidates first; broadly applicable correctness checks establish the normal baseline; applicability-aware integration checks run where their affected surface requires them; and broad full qualification is reserved for authority-defined boundaries that actually need it.

## Canonical stage roles

| Stage | Role | Typical examples |
| --- | --- | --- |
| Stage 0 — CI preflight | Cheap deterministic rejection of obviously invalid candidates | parsing, manifest/config validation, formatting or structural rules, inexpensive schema shape checks, generated-state consistency, dependency metadata checks |
| Stage 1 — Core validation | Baseline correctness that is broadly applicable | unit tests, static analysis, canonical schema or contract tests |
| Stage 2 — Conditional integration | More expensive checks whose applicability depends on affected surfaces | browser/PWA, cross-authority, integration, materialization, compatibility subsets |
| Stage 3 — Full qualification | Broad authority-defined acceptance at a qualification boundary | complete compatibility matrices, full browser suites, release or publication qualification |

Repositories do not need four physical workflows or jobs. A simple repository may collapse roles. Conversely, one stage may contain several jobs. The taxonomy describes evidence role and execution intent, not a mandatory GitHub Actions topology.

## CI preflight

A useful CI preflight is substantially cheaper than the dependent work it protects and is deterministic enough to provide fast negative feedback. Prefer checks that can establish that continuing an expensive dependent path would be wasted work—for example, an invalid manifest, malformed configuration, broken generated-state invariant, or structural policy error.

When the workflow can express dependencies efficiently, expensive jobs should depend on the preflight outcome. A failing preflight therefore prevents avoidable dependent work. This is not a requirement to serialize unrelated work: an independent job that is itself cheap or that provides useful orthogonal evidence may run concurrently. The optimization target is expected feedback and resource cost, not a visually linear pipeline.

A successful preflight proves only what the preflight owns. It does not prove core correctness, integration behavior, exact-head qualification, review completion, merge readiness, release readiness, or publication readiness.

## Applicability is separate from stage

Stage answers **what role does this verification play?** Applicability answers **does this verification apply to this candidate?** Result answers **what happened when an applicable verification ran?** Keep these dimensions separate.

For example:

```text
stage = conditional-integration
applicability = not-applicable
result = not-run
```

is meaningful. It is not equivalent to `result = passed`.

When applicability depends on changed paths, dependency maps, classifiers, or other repository-controlled logic, use the canonical exact-head CI applicability requirements: bind the decision to the relevant candidate and inputs, fail closed on ambiguity, and do not allow a changing classifier to silently self-exempt. An explicit full-verification checkpoint may override selective execution when repository authority requires broader evidence.

## Construction and qualification

Staged CI aligns with the revision-bound qualification lifecycle.

```text
construction / provisional candidate
    ├── CI preflight
    ├── core validation
    └── applicable focused or conditional integration
                 │
                 ▼
        stabilize prerequisites
                 │
                 ▼
          freeze qualification head
                 │
                 ▼
      all authority-required applicable
        exact-head qualification evidence
      including full qualification if required
```

Naturally triggered CI on a provisional head is useful diagnostic evidence. It does not itself turn that head into a qualification identity. Conversely, once a merge, review, release, publication, or other authority boundary requires exact-revision evidence, delaying full applicable qualification is no longer justified by the staging model.

## Superseded candidates

When a new candidate head makes an in-flight expensive run incapable of satisfying any current evidence requirement, cancel or supersede that work when the CI platform safely permits it. Preserve reusable evidence whose bindings remain valid; invalidate only evidence affected by the head or input change. This complements candidate stabilization and mutation batching rather than replacing them.

## Anti-patterns

Avoid:

- treating `preflight passed` as shorthand for `CI passed`;
- calling a high-cost core or integration suite a preflight merely because it runs first;
- using stage labels as severity or importance rankings;
- skipping an applicable required check because a cheaper stage passed;
- treating `not-applicable` as a passing test result;
- allowing ambiguous applicability to skip work;
- forcing all independent jobs into a serial chain when concurrency gives faster or cheaper feedback;
- repeatedly launching full qualification for provisional heads already expected to move; and
- continuing expensive work for a superseded candidate when its result cannot be reused.

## Repository implementation guidance

A repository implementing this model should make the stage and applicability decisions observable in workflow names, job summaries, or equivalent operational evidence. Prefer stable terminology such as `preflight`, `core`, `conditional integration`, and `full qualification` only when the jobs actually own those roles. If an existing job combines preflight checks with substantial core validation, rename it rather than implying that the whole job is a cheap preflight gate.
