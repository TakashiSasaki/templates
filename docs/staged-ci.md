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

## Risk/applicability classifier contract

To safely use lightweight construction CI without weakening qualification, a repository classifier must satisfy the canonical **classifier contract**:

| Property | Requirement | Rational |
| --- | --- | --- |
| **Base-authoritative** | Classifier logic resolves from target base (e.g. `origin/main` / `$BASE_SHA`), not proposed head | Prevents untrusted changes from altering their own qualification rules |
| **Deterministic** | Computed purely from exact repository-relative changed paths | Ensures consistent, reproducible decisions across environments |
| **Fail-closed** | Unknown paths, missing diff, malformed input, or base lookup errors require full verification | Prevents silent verification bypass on anomalous conditions |
| **Self-exemption prohibited** | Modifications to the classifier or CI control files force full/conservative verification | Prevents circular justification or weakened governance |
| **CI workflow sensitive** | Modifications to `.github/workflows/**` require full/conservative verification | Ensures workflow mutations undergo comprehensive validation |
| **Explicit escalation** | Manual triggers (`ci/full-*-verification` label, `workflow_dispatch`) force full verification | Allows maintainers to run complete suites on demand |

### Standard risk classes

Policy defines standard semantic risk classes. A repository maps its internal path tables to these categories:

```text
documentation-only        (L0/L1 only: formatting, link/nav validation)
tests-only                (L0/L1 + focused test suite)
content                   (L0/L1 + content assembly)
runtime-sensitive         (L0/L1 + runtime unit & compatibility tests)
browser-sensitive         (L0/L1 + browser & visual acceptance)
publication-sensitive     (L0/L1 + publication materialization & schema checks)
cross-authority-sensitive (L0/L1 + multi-authority integration tests)
distribution-sensitive    (L0/L1 + packaging, installer, release matrix)
ci-authority-sensitive    (Full qualification: workflow or classifier changed)
unknown                   (Fail-closed: full qualification)
```

Policy governs the **semantic contract and guarantees** of the classifier; each individual repository remains authoritative for its concrete **path-to-class mappings**.


## Construction candidate vs qualification candidate

Staged CI defines two distinct candidate roles across the revision lifecycle:

| Candidate role | Description | Validation requirement | Decision boundary |
| --- | --- | --- | --- |
| **Construction candidate** | Active development revision, iterative mutation, or stacked ancestor/intermediate head | CI preflight (L0), core validation (L1), and applicable conditional integration (L2) | Verifies development continuity; does **not** confer merge or release readiness |
| **Qualification candidate** | Deliberately stabilized candidate revision frozen for decision-making | Full exact-head qualification (L3) plus all applicable lower stages | Authority-defined: pull-request merge, release, publication, deployment, or final whole-stack review |

```text
construction candidate (intermediate / active revision)
    ├── L0 CI preflight
    ├── L1 core validation
    └── L2 applicable conditional integration
                 │
                 │ (continue dependency-safe work without waiting on heavy CI)
                 ▼
        stabilize prerequisites & stack
                 │
                 ▼
       freeze qualification candidate (final stack tip / head)
                 │
                 ▼
       L3 full qualification (exact-head evidence)
         + all applicable lower stages
                 │
                 ▼
      authority decision (merge / release / publication)
```

### Operational rules for candidate staging

1. **L0/L1 green ≠ merge-ready**: A passing preflight or core validation proves only that the construction candidate does not possess obvious static or baseline defects. It never constitutes merge or release evidence.
2. **L1/L2 evidence ≠ L3 evidence**: Intermediate or conditional verification results can never substitute for authority-required full qualification.
3. **Revision mutation invalidates qualification evidence**: If a qualification candidate changes or is superseded, prior revision-bound evidence becomes stale and cannot qualify the successor revision.
4. **Do not block construction on heavy CI**: Expensive CI completion on an intermediate construction candidate must not delay dependency-safe downstream implementation or stacked progression.
5. **Stack-tip qualification**: In a stacked change series, intermediate heads do not each require full qualification; stabilize the final stack tip as a qualification candidate and acquire full qualification there before human handoff or merge.

## Stacked PR and CI lifecycle integration

Staged CI integrates directly with stacked pull requests:

```text
Member 1 (P1)
  │ lightweight construction CI (L0/L1)
  ▼
Member 2 (P2)
  │ lightweight construction CI (L0/L1)
  ▼
Member 3 (P3 - Stack Tip)
  │
  ├─ move to stability frontier
  ├─ freeze qualification head
  ├─ applicable full qualification (L3)
  ├─ whole-stack architecture review
  ▼
human handoff / bottom-up merge
```

### Key lifecycle rules

- **Non-blocking intermediate progression**: Constructing descendant PRs does not wait for expensive CI on intermediate members. Intermediate heads use lightweight validation to ensure development integrity while keeping velocity high.
- **Cancellation of obsolete head runs**: When a member receives a new commit SHA, any expensive in-flight CI runs on the obsolete predecessor head may be cancelled or superseded immediately.
- **Review request on qualification candidate**: The formal review request (whether individual exact-head review or whole-stack audit) is issued only against the stabilized qualification head after all applicable required CI passes.
- **Post-movement re-evaluation**: Any movement of a candidate head (e.g. rebase, repair, or base advance) invalidates previous revision-bound evidence and triggers fail-closed re-evaluation of CI applicability and review requirements.

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

## Dogfooding in this repository

The Policy authority uses the same model for its own maintenance CI rather than treating the rule as consumer-only guidance.

`Policy CI` has an explicit **CI preflight** job that binds the candidate/base inputs, performs the fail-closed Policy CI applicability classification, records the applicability decision, and compiles Python sources before dependency installation or the main test suite. Its dependent **core validation** job establishes the locked environment and runs installer synchronization, translation validation, static rules, and the full pytest suite. Stable-release synchronization and trusted-review candidate verification are conditional verification probes selected from the preflight applicability outputs; a skipped probe is therefore an applicability outcome, not a passing test.

The independent `Policy runtime distribution` workflow retains its own classifier and compatibility matrix. It remains parallel to normal Policy CI rather than being serialized behind it, and `ci/full-compatibility` provides the repository-defined explicit broad compatibility checkpoint. This separation demonstrates that staged CI is a dependency and evidence model, not a requirement to place every repository check in one linear workflow.

Both workflows use provider concurrency cancellation so that a superseded candidate does not continue consuming expensive validation when its result can no longer qualify the current head.
