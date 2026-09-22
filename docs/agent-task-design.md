# Preparing reliable agent tasks

This is non-normative, provider-maintenance guidance for people and agents that
prepare work for other coding agents. It operationalizes existing Policy; it
does not introduce a second acceptance authority, mandatory planning gate, or
agent-specific operating mode. The method is reusable outside this repository.
Keep the task's applicable Policy, contracts, and authorized completion boundary
in control. See [Repository-change orchestration](agent-work-orchestration.md)
for execution and [Policy authoring](policy-authoring.md) for source ownership.

## Design premise

Design for the agents actually available, without depending on an upgrade to a
stronger model. Do not assume that an agent will spontaneously discover every
unstated requirement, generalize every review example, infer the limits of its
observations, or remember every obligation while repairing another one. Make
those obligations external and inspectable, while leaving implementation choices
inside the agreed constraints to the worker.

This is a workflow design assumption, not a measured ranking of a model or a
claim that review history identifies a general reasoning deficit. Specification
quality, observability, task scope, environment failures, and implementation all
contribute. A longer prompt, more passing tests, or a clean review alone does not
establish that this method improves performance.

## Existing authority, not another rule set

The canonical rules remain in the shared corpus. The paths below are source
locators, not instructions to execute an unpinned checkout.

| Concern | Existing rule / source |
| --- | --- |
| Outcome, scope, preserved behavior | `changes.define-contract` / `policy/core/change-contract.md` |
| No retrospective goal expansion | `changes.preserve-acceptance-baseline` / `policy/core/acceptance-baseline.md` |
| Material unresolved choices | `decisions.escalate-semantic-ambiguity` / `policy/core/semantic-decision-gates.md` |
| Real execution and applicable results | `testing.run-required-checks` / `policy/core/testing.md` |
| Bounded sibling cases | `testing.require-adversarial-invariant-coverage` / `policy/core/adversarial-invariant-testing.md` |
| Effective use and evidence layers | `safety.bind-validated-state-to-operation` / `policy/core/validation-operation-binding.md`; `verification.separate-evidence-layers` / `policy/core/evidence-layers.md` |

Reuse the adopted Work ledger, review-finding procedure, preflight, and review
scope planner. Do not create another ledger, planner, schema, or global checklist
merely to apply this guide. Durable specifications and regression fixtures may
be tracked as design artifacts; changing task progress belongs on the already
adopted operational surface, not in progress-only commits on the candidate.

## Choose preparation proportional to uncertainty

These are examples, not new workflow modes or mandatory numeric risk scores.

| Situation | Minimum useful preparation |
| --- | --- |
| Read-only question, typo, routine local change | Outcome, allowed surface, required check, stop condition; often a few sentences are enough. No separate design document or model. |
| New interface, ambiguous behavior, evaluator, mutable dependency | Compact design packet with obligations, assumptions, evidence, counterexamples, and independently useful work units. |
| Material concurrency, trust, irreversible effects, repeated root-cause findings | Add a small state/transition model and evidence-to-claim mapping where these resolve the concrete uncertainty. Reuse existing primitives and validation. |

Use uncertainty and consequences, not line count or agent prestige, to choose
preparation. Do not require a theorem prover, new reviewer, exhaustive Cartesian
product, or new approval round for routine work. Read authoritative sources that
can resolve a question before asking the requester. Escalate only a material
choice that remains unresolved; independent authorized work can continue.

## Prepare a compact design packet

The requester or specification author prepares the initial packet. The worker
refreshes live facts, identifies contradictions, and implements within it. These
roles may be performed by the same agent, but a second pass in the same context
is not independent review. Preserve the repository's actual review contract.

Use the following sequence before dependent implementation; a short answer in
the task brief is sufficient when the question is already settled.

1. **Fix the outcome and stop boundary.** State observable behavior, allowed
   files/authority, preserved invariants, non-goals, and whether completion means
   implementation, validation, review request, review result, or authorized merge.
   An investigation may legitimately conclude that evidence is insufficient.
2. **List separate acceptance obligations.** Give each material obligation an ID.
   Separate behavior, requested regression, whole-suite success, operational
   authority, and evidence applicability. Avoid one vague item such as "all good".
3. **State environment and trust assumptions.** Identify who can change each
   input, reference, executable, and output; which transitions or failures matter;
   and what the available tools actually observe or enforce. Describe what is
   outside scope. Do not assume a filename, digest, private-directory name, or
   successful subprocess establishes protection it does not provide.
4. **Map each claim to sufficient evidence.** Record the producer, observation
   boundary, identity, required outcome, applicability, and invalidators. Ask why
   that evidence implies the obligation under the stated assumptions. If it does
   not, change the mechanism or report the missing evidence; do not assert success.
5. **Compare a small number of design options.** Prefer an existing authoritative
   primitive or a simpler supported path over new generic infrastructure. Record
   the chosen design, why the alternatives do not fit, and the remaining unknowns.
6. **Choose coherent implementation units.** Keep authority, semantic purpose,
   validation, and rollback responsibilities clear. Use stacked PRs when useful,
   without inventing a fixed PR count. Preserve stable unrelated lower layers.
7. **Make the failure criteria executable.** Prepare bounded negative controls
   and a valid positive control before the repair where feasible. Identify the
   real entrypoint that executes them and the required broader validation.

A useful evidence table is:

| ID | Required fact | Evidence and actual execution boundary | Counterexample / invalidator | Decision if missing |
| --- | --- | --- | --- | --- |
| R1 | Requested behavior is repaired | Independent behavior check on identified candidate | Unchanged or wrong implementation | Not established / failed as observed |
| R2 | Requested regression executes and checks that behavior | Obligation-specific test identity and execution outcome | Dead assertion, skip, unrelated failing test | Not established |
| R3 | Required suite remains passing | Discovered suite result on the same candidate | Requested test passes but another required test fails | Failed |
| R4 | Proposed next action is authorized | Current state plus applicable authority/permission | Review completed but merge not authorized | Do not perform that action |

These rows illustrate a code-repair task; omit genuinely inapplicable obligations
rather than manufacture evidence. Do not omit an applicable row just because a
later repair focuses on another one. Keep a single authoritative packet/reference
and derive summaries from it where practical.

## Test claims, not convenient proxies

"An assertion appears in the AST" is not "that assertion ran". "A process exited
zero" is not "the required work occurred". "No forbidden event was detected" is
not "all behavior was observed and compliant". "The archive was verified" is not
"the installed bytes match it". State exactly which claim the evidence supports.

Before accepting a mechanism, supply a counterexample that looks successful to
the proxy while violating the requirement. For each material obligation, also
start from a valid positive case and remove, stale, contradict, or substitute
only that obligation's evidence. Exercise the real decision path, not merely a
helper with a precomputed `False`. This catches obligations that are recorded in
diagnostics but omitted from the final decision.

For a requested regression, preserve evidence of its execution and relevant
failure cause. A defect-specific mutant can help: changing only the requested
behavior must make that check fail, while the repaired version passes. An import
error, unrelated assertion, setup failure, or whole-suite failure is not evidence
that the requested check detected the defect. Define the supported test contract
rather than claiming to analyze arbitrary programs.

Keep uncertainty separate from violation. A missing observation cannot establish
success, but it is not proof that the worker misbehaved. Preserve task outcome,
compliance observation, environment failure, and performance as distinct results.
Do not build a universal shell parser or sandbox merely to avoid reporting an
unobservable property. Do not weaken an agreed requirement without authorization.

## Use formal models where they resolve a concrete design risk

For a small relevant transition system, declare initial states, agent and
environment actions, atomicity assumptions, evidence identities, and required
safety properties. Model failure and cleanup transitions when they matter. Keep
specification and implementation oracles independent enough that they cannot
silently share the same defect.

Distinguish value enumeration, reachable-state exploration, bounded witness
paths, implementation conformance tests, and a proof. Record the explored domain
and unsupported behaviors. A check that merely restates `accepts()` does not
prove that evidence is correctly obtained. An accepted witness shows non-vacuity;
it is not a general liveness proof. Do not hide real multi-step races in a
fictitious atomic model operation.

Map each abstract established fact to its concrete producer and use boundary.
Test that deliberately broken production mappings are detected, not just that a
modified model rejects itself. Start with the smallest relevant model; do not
formalize an entire repository or add tools solely to claim formal verification.

## Write instructions that preserve judgment and reduce memory burden

Keep the short goal about the outcome and stop boundary. Keep the task brief
about scope, obligations, trusted entrypoints, work units, validation, budgets,
and reporting. Reference detailed Policy and design by a resolvable source; do
not paste the entire policy corpus or prior conversation into every worker.

Do not issue only "be careful", "think harder", "cover all siblings", or "make
review clean". Supply concrete falsifiable obligations and bounded examples.
Examples are probes, not an exhaustive specification. Avoid prescribing every
API call or safe implementation detail when alternatives meet the same contract.

Use a brief observable design checkpoint: selected assumptions, obligation table,
chosen mechanism, uncovered evidence, and next action. Do not request private
reasoning transcripts. Where semantics and authority are settled, the checkpoint
is a work product, not an extra human approval gate.

A steering message identifies the unchanged goal, the new evidence, the affected
obligation, the repair unit, what remains frozen, and the stopping rule. A scope
change must be explicit and authorized; do not silently append it to the old goal.
Do not duplicate the entire previous prompt just to add one constraint.

## Respond to reviews without turning review into the specification author

Treat a finding as a hypothesis and classify it against the agreed contract:

| Finding kind | Appropriate action |
| --- | --- |
| Demonstrated violation of an existing obligation | Reproduce, inspect bounded siblings, repair the owning unit, and requalify affected evidence. |
| Missing observation or ambiguous assumption | Establish what can be observed; resolve the material design choice before dependent acceptance. |
| Proposal for a new guarantee | Record impact and request an authorized rebaseline; do not silently grow current scope. |
| Falsified or irrelevant claim | Record concise current evidence and a no-change disposition; no appeasement edit. |

Repeated findings about the same proxy are a signal to reconsider the evidence
mapping or simplify the mechanism, not merely extend a blacklist. Preserve all
known applicable obligations while batching repairs. "Family closed" means the
identified, materially reachable cases have current evidence under the declared
assumptions; it is not proof that no unknown defect exists.

Use the existing review-scope planner and applicability rules. Reuse valid
coverage, reconcile in-flight requests, and acquire additional scope only when
justified. There is no universal review-count limit and no promise that the next
review will be clean. Honor the selected stopping boundary rather than changing
it to "continue until every possible objection disappears". Required safety and
acceptance evidence is never waived to save review cost.

## Budgets, handoff, and gradual improvement

Separate a task's diagnostic/experiment budget from an external dependency's
legitimate pending state. Check a required environment capability with a cheap,
authorized probe before a costly trial batch. A repeated bootstrap failure with
no changed precondition calls for a genuinely different authorized in-scope
strategy while one remains materially available, not more identical trials.
Record a blocker only after materially different suitable strategies are
exhausted, unavailable, unauthorized, or unsafe. Do not invent a new trial budget
implicitly.

At handoff, report changes and exact applicable evidence, residual uncertainty,
known findings, review state, and the next safe action. Implementation, CI,
review, merge permission, merge, adoption, and measured performance are distinct.
No demonstrated optimization benefit is a valid investigation outcome; it is not
permission to claim incomplete correctness work is complete.

For later tasks, retain small reusable regressions and case lessons rather than
transcripts. Compare comparable tasks before claiming reduced time, tokens, or
review rounds. Record method and model/environment identity when observable.
Diagnostic measurements are not new mandatory KPIs or fixed review quotas.

## Historical motivation, not runtime authority

The following 2026 Policy-delivery review examples motivated this procedure.
They identify concrete failure patterns, not the current status of those PRs or
a measured cause attributable to a model. Refresh GitHub before operational use.

| Historical example | General lesson |
| --- | --- |
| [Program-bearing commands treated as local](https://github.com/TakashiSasaki/templates/pull/1000#discussion_r4063065561) | Name-based proxies do not establish arbitrary execution effects. |
| [Uncalled requested assertion](https://github.com/TakashiSasaki/templates/pull/1000#discussion_r4063065567) | Bind the evidence to the required check, not merely its containing method. |
| [Required suite omitted from PASS](https://github.com/TakashiSasaki/templates/pull/1000#discussion_r4063065574) | Test each obligation's necessity in the real acceptance path. |
| [Documented case count diverged](https://github.com/TakashiSasaki/templates/pull/1000#discussion_r4063065584) | Derive repeated evidence summaries from the same source. |

These references are evidence for the motivation only. No procedure, test, or
runtime decision depends on those PR numbers. This page does not modify selected
Policy, generated `AGENTS.md`, distributed Skill behavior, adoption pins, or
publication state. Source documentation being available is not automatic
self-adoption; a future integration must use the canonical generation and
immutable-adoption process.
