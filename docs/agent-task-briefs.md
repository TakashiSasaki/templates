# Agent task, goal, and steering templates

Use these templates with [Preparing reliable agent tasks](agent-task-design.md).
They are authoring aids, not additional Policy, a new Skill, or instructions to
run every stage for every task. Apply the task's actual authority and completion
contract. Replace bracketed placeholders before delegation; remove inapplicable
fields, not applicable obligations. The examples are illustrative, not live work
requests or claims about existing repository fixtures.

## Choose the smallest useful brief

For a routine change, a few sentences containing the outcome, allowed files,
checks, and stop boundary are enough. Use the expanded brief when the worker
would otherwise have to infer material semantics, observation assumptions, or
acceptance evidence. Add a small model only for the concrete risk that needs it.

The specification author fills the obligations and authority fields before
handoff when possible. The worker refreshes live identities and reports material
contradictions before the dependent mutation. Routine implementation choices
within that contract remain the worker's responsibility. No automatic extra
human approval or external review is created by filling in this template.

## Goal template

A goal states an outcome and a stopping boundary, not an unbounded aspiration
such as "keep improving until no reviewer can find anything". It must agree with
the detailed brief. A separate goal field is optional; this is not a dependency
on a particular agent product or command.

<!-- BEGIN GOAL TEMPLATE -->
```text
Deliver [observable outcome] in [repository / authority / allowed surface],
preserving [invariants]. Establish [named acceptance evidence] for the actual
candidate and stop at [explicit completion boundary]. Use [authorized diagnostic
or experiment budget, if any]. Missing evidence must remain unverified; an
inconclusive investigation is a valid outcome, not a successful implementation.
Do not expand scope or perform [merge / adoption / publication / other excluded
operations]. Report residual gaps and the next safe action at handoff.
```
<!-- END GOAL TEMPLATE -->

## Task brief template

Keep the following in one task brief or an existing authoritative design packet.
Do not create a second Work ledger. Link detailed rules and fixtures by the
repository's normal immutable-source convention rather than copying all Policy
into the brief. Source locators are not permission to execute candidate code as
its own acceptance authority.

<!-- BEGIN TASK BRIEF TEMPLATE -->
```text
# [Task title]

## Outcome and completion
Repository / authority: [identity]
Requested observable result: [result]
Completion boundary: [implementation / validation / review request / review
result / authorized merge; select explicitly]

## Authority and scope
Trusted instructions, contracts, and entrypoints: [resolvable source references]
Starting state: [known snapshot; worker must refresh mutable bindings]
Allowed changes: [responsibility / files / same-authority PR topology]
Preserve: [existing behavior and invariants]
Non-goals and excluded operations: [scope / permissions]

## Assumptions and observations
Actors and mutable resources: [who can change what, when relevant]
Available observation/enforcement: [evidence source and limitations]
Unresolved material decisions: [question, alternatives, authority required]
Proceed with independent authorized work; do not guess a dependent safety or
semantic decision and do not repeatedly ask what the sources already establish.

## Acceptance obligations
For each applicable R-ID, provide:
- required behavior or state;
- concrete evidence producer and actual execution boundary;
- required identity, outcome, and applicability;
- negative control and normal positive control;
- invalidation conditions and missing/unknown-evidence decision.
Keep behavior, requested regression, whole-suite success, and action permission
separate. All applicable obligations remain required after each repair.

## Design and implementation
Before dependent editing, summarize [assumptions / evidence mapping / selected
mechanism / remaining gaps] briefly. This is not an extra approval gate when
existing authority already settles the choices. Reuse [canonical mechanisms].
Implement [coherent units] with [selected progression]. Do not add a general
framework, second validator, or speculative hardening to solve an unrelated case.

## Validation and review
Run [focused checks] through [actual entrypoint], then [required preflight/CI].
Demonstrate negative controls fail before the repair where feasible and positive
controls pass after it. Verify actual execution and outcomes, not just file
presence, mock invocation, process exit, or aggregate green state.
Refresh only evidence whose applicability changed. Follow [existing review
scope/acceptance procedure] and avoid duplicate equivalent review requests.
Review completion, merge permission, and merge completion remain separate.

## Budget and stop
Authorized trials / diagnostic attempts / resources: [scope-specific limit]
On a repeated failure, record what changed and switch to a genuinely different
in-scope method or preserve the blocker; do not retry an invalidated path without
new applicability evidence. Stop at the stated completion boundary. Do not turn
review feedback into new scope without explicit authorization.

## Handoff
Report changed artifacts, candidate identities, evidence and limits, known
finding dispositions, CI/review states, excluded operations not performed, and
next safe action. Use the adopted operational checkpoint, not a new transcript.
```
<!-- END TASK BRIEF TEMPLATE -->

## Additional steering template

This is a delta to an active brief. If the goal or acceptance baseline must
change, state the authorized change and its impact explicitly; do not call it
mere clarification. Reuse unaffected evidence and do not resend the entire brief.

<!-- BEGIN STEERING TEMPLATE -->
```text
This supplements [active brief / goal reference]. The outcome, allowed authority,
and stop condition remain unchanged unless an explicit authorized change follows.
New evidence: [reproduction / review locator / observation].
Affected obligation: [R-ID and violated invariant, not only the reported line].
Repair unit: [bounded change and materially reachable siblings to check].
Keep unchanged: [unaffected responsibilities / PR heads / permissions].
Qualification: [negative/positive evidence and affected canonical checks].
No new external review during known remediation; use the existing scope planner
once the candidate is qualified. Stop at [original completion boundary], or report
[concrete blocker and resume condition]. New guarantees require rebaselining.
```
<!-- END STEERING TEMPLATE -->

## Example: a routine documentation correction

**Goal:** Correct the identified terminology error in the named source document,
verify the changed references, and hand off the diff without merge or publication.

**Brief:** Confirm the document is authored rather than generated. Correct the
specified term and directly affected links only. Preserve meaning and unrelated
text. Run the repository's required documentation checks and report their actual
results. No model, new threat analysis, extra review round, or approval checkpoint
is needed merely for this template; existing repository requirements still apply.

## Example: a bounded evaluator repair

**Goal:** Make the specified local evaluator reject insufficient evidence and
accept a valid result under its stated fixture contract. Stop after required
validation and the explicitly authorized final review request. Do not run new
model experiments or change adoption/defaults. Unobservable compliance stays
unknown; no performance benefit is required.

**Packet:** The worker can change the test fixture's implementation and tests.
The retained reference and evidence collector are trusted only under the stated
isolation assumptions. R1 requires correct behavior; R2 requires the requested
regression's actual execution and relevant defect detection; R3 requires the
entire required suite to pass; R4 requires applicable reference and observation
evidence. Fixing R2 does not remove R3. A copied assertion in dead code, an unrelated
failing test, a missing reference, and an unknown observation are negative
controls. A fully valid repair is the positive control. Reuse the existing grader
and preflight; do not build a universal program-effect analyzer or new sandbox.

**Steering:** A review shows the requested regression passes while another
required test fails. This violates R3; it is not a new goal. Repair the common
acceptance composition and test each required evidence item's necessity through
the real grader. Keep unrelated lower PRs stable. Requalify the affected candidate,
request only the justified review scope, then hand off at the original boundary.

## Before delegating and after completion

Check that the goal and brief select the same outcome, scope, budget, and stop
boundary; source references are available; known facts are not replaced by
placeholders; and every material requirement has an evidence plan. Do not fill
unobserved facts with plausible values. Use links for detail and load them before
the dependent operation, not after a failure. Avoid replaying the whole history
into each worker's initial context.

Record design decisions and reusable fixtures in their normal source locations.
Record progress, invalidations, findings, and resume state on the adopted Work
ledger/review surfaces. Keep hypotheses about agent capability distinct from
measured results. A successful task with this template is not by itself proof of
lower token use or fewer future review findings.

These source-only templates are discoverable from the Policy authority root.
They do not change generated `AGENTS.md`, Skill distribution, or publication pins.
A future automated integration is a separate canonical generation/adoption task.
