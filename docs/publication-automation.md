# Contract-gated publication automation

This document is the Site-side handoff for the three publication modes. It is
an operational contract, not an instruction to enable automation while the
implementation stack is under review.

## Boundaries

The flow is deliberately split into two gates:

1. Integration qualifies one exact producer/configuration/provider tuple and
   publishes an immutable Bundle artifact.
2. Site validates that exact Bundle, renders it, runs the existing static and
   browser acceptance suites, and uploads the bytes that passed the final gate.

The Site consumes only the public Bundle contract. It does not check out a
provider, read a provider catalog, or infer capability from a provider's
self-description. `integration-source.json` is the committed consumer
selection; its four selected identity fields are the only normal adoption
mutation.

The default `site` branch also contains a thin `repository_dispatch` adapter
for provider qualification events. It validates the immutable provider facts,
resolves the current `integration` authority head to one exact producer SHA,
and forwards those facts to the pinned Integration controller; it does not
perform Integration semantics itself. A producer-head race is handled by the
controller's expected-base check rather than by trusting the event payload.

Integration's candidate report is not a Site or adoption authorization. The
upstream controller must provide a trusted receipt bound to the exact Bundle
artifact, run attempt, and controller/Policy pins; missing or self-claimed
qualification evidence stops the downstream flow.

## Modes

`shadow` is the repository default. Candidate discovery, structured reports,
read-only qualification, and summaries are allowed; lock PRs and Pages writes
are not. A successful qualification in this mode is evidence, not adoption.

`adoption-only` permits a trusted controller to create or reconcile an
idempotent Site lock PR after the Integration and Site gates pass. Pages remains
unchanged. Branch protection and required CI still decide whether the PR may
merge; the controller does not bypass either.

`auto-publish` adds the final Pages path. The deployment job is still gated by
the exact artifact ID/digest emitted by the producer, a successful final
artifact gate, current Site/Integration identities, and the `github-pages`
environment. Its build must locate the unexpired promoted Integration Bundle
and re-verify the trusted promotion receipt; an absent or expired release does
not trigger read-only regeneration. No timestamp or provenance file may be
rewritten after that gate.

Manual publication remains available in every non-kill-switched mode. An explicit
`workflow_dispatch` on `site` uses `automatic=false` by default, binds the requested
exact Site SHA, runs the same Site qualification and immutable artifact checks, and
deploys only that artifact through `github-pages`. The manual dispatch is the human
authorization; it does not require `PUBLICATION_AUTOMATION_MODE=auto-publish` or
`PUBLICATION_AUTOMATION_AUTHORIZED=true`. Its `manual_kill_switch_context` input is
an explicit workflow-evaluated boolean, defaulting to `false`, and is passed to the
final verifier without normalization. The existing repository kill-switch gate
still prevents the job from starting when the repository variable is `true`.
The automatic dispatch sets `automatic=true` and requires all of the stricter
activation variables.

The deployment verifier reads `PUBLICATION_AUTOMATION_KILL_SWITCH` through the
authenticated GitHub API immediately before deployment. A confirmed HTTP 404 for
that variable, followed by a successful authenticated repository metadata read,
means the variable is absent and applies the documented default `false`. On an
explicit manual dispatch only, the workflow also passes the raw evaluated
`manual_kill_switch_context` to the verifier. If the Actions token receives HTTP
403 for the repository-variable endpoint, the verifier may use that exact context
when it is `false` (and still rejects `true`); an empty or malformed context
remains a failure. Automatic publication never uses this exception. Any
authentication, permission, rate-limit, transport, malformed-response, or server
error outside that narrowly scoped manual variable request stops deployment; it is
never treated as an inactive switch.

## One-time activation checklist

After all authority PRs have been reviewed and landed, an authorized operator
must verify each item once:

- Install the least-privileged GitHub App credential required by the guarded
  controller. Store it as the repository secret `PUBLICATION_APP_TOKEN`; this
  implementation does not create the secret.
- Protect `integration` and `site` with the required status checks and retain
  the required human review/merge-queue policy. Confirm that the controller
  may request auto-merge but cannot bypass protection.
- Configure the `github-pages` environment to permit only the intended Site
  deployment job and verify Pages uses the `site` authority branch. The live
  repository setting must be checked because a stale `main` Pages source is a
  stop condition, not an implementation success.
- Set repository variables only after the previous checks pass:
  `PUBLICATION_AUTOMATION_MODE=adoption-only` (then later
  `auto-publish`), `PUBLICATION_AUTOMATION_AUTHORIZED=true`,
  `PUBLICATION_POLICY_REVISION=<active full SHA>`, and
  `PUBLICATION_CONTROLLER_REVISION=<trusted full SHA>`.
- Leave `PUBLICATION_AUTOMATION_KILL_SWITCH=false` and record the activation
  operator, time, exact heads, and checked settings in the PR/issue ledger.

The implementation PRs do not set these secrets, variables, protections, or
environment rules and therefore do not claim that unattended operation is
enabled.

## Inspect, stop, and recover

In Shadow, inspect the qualification report, exact provider tuple, Bundle
identity/content digest, controller/policy identities, and `next_action` in the
Actions summary. A missing, skipped, cancelled, stale, or unknown report is a
stop—not a successful empty result.

To stop new work, set the kill switch to `true`. The switch prevents new
adoption and deployment and leaves the last successful Pages release intact.
It is not a rollback.

For recovery, first verify the actual GitHub branch, PR, run attempt, artifact,
and deployment state. Then select a previously qualified immutable lock and
artifact, run the guarded updater with its expected-current digest, and obtain
the required review/merge. Do not regenerate a corrupt or stale artifact merely
to make its digest appear current. A consumer adaptation is a new Site commit;
the stopped input must be requalified against that new consumer identity.

## Evidence applicability

Evidence binds the Integration producer SHA, every provider SHA, Bundle schema,
Bundle identity/content digest, Site SHA, qualification suite/environment,
workflow run/attempt, and artifact ID/digest. A candidate result made with a
different producer or merged Site SHA is not silently reused. Content equality
alone is not a `NO_CHANGE`; identity equality is the no-op criterion.

## Current event and PR chain

The source-controlled path is the following. It is a read-only map for
maintainers; it does not authorize a dispatch or a setting change.

| Event | Current code | Result and next boundary |
|---|---|---|
| Provider push qualification | `modeling-ci.yml`, `reference-consumer-publication.yml`, and `integration-compatibility.yml` | The provider qualifies its exact pushed SHA, then sends `publication.provider-qualified` with run/attempt/workflow identity. A provider check or added file is not publication. |
| Provider event received | Site default-branch `provider-publication-dispatch.yml` | Site validates the exact payload, resolves the live `integration` ref to one producer SHA, and calls `integration-reconcile.yml` pinned at `a92006b95ef67abaa52d59e7a583c1f59656e7a7`. The adapter does not adopt Site or execute provider code. |
| Integration candidate | `integration-reconcile.yml` | Exact producer/provider qualification, trusted-controller rebuild, artifact binding, and receipt verification produce a report. The source fallback is `shadow`; live repository variables and credentials are external. Only separately authorized `adoption-only` or `auto-publish` can reach the deterministic `automation/publication-*` lock PR job. |
| Integration merge | `integration-promotion-notify.yml` | A merged `automation/publication-*` PR is requalified and its trusted receipt is checked before `publication.integration-promoted` is sent to Site. The notification is a candidate handoff, not Site adoption or deployment. |
| Site candidate | `publication-reconcile.yml` | Site acquires the exact Bundle/receipt and runs Site qualification. Only an externally authorized automatic mode can create an idempotent `automation/site-publication-*` lock PR; Site qualification and protected merge remain independent. |
| Site merge | `site-publication-notify.yml` | Only a merged `automation/site-publication-*` PR in `auto-publish` with authorization, exact pins, and kill switch clear may invoke `deploy-pages.yml` with `automatic=true`. A normal Site UI PR does not take this automatic post-merge route. |
| Deployment | `deploy-pages.yml` and `build-pages.yml` | The workflow qualifies the exact `site_revision`, gates the exact Pages artifact/digest and current branch head, and uses the `github-pages` environment. `automatic=false` is a separate human `workflow_dispatch` path. |

The provider workflows use the workflow's `github.token` to submit the
`repository_dispatch` transport. GitHub evaluates that event on the repository's
default branch, which is why the Site adapter is the entry point; the adapter
then resolves, rather than trusts, the Integration branch. The guarded lock-PR
jobs use `secrets.PUBLICATION_APP_TOKEN` for Git/PR writes and guarded merge
requests, and the notification jobs use that App token for subsequent dispatch or
workflow dispatch. These credentials are not present in this implementation
worktree and their live permissions are not asserted here.

This distinction matters for GitHub's workflow-event rules: activity performed
with `GITHUB_TOKEN` is generally prevented from recursively starting workflows,
with the documented `workflow_dispatch` and `repository_dispatch` exceptions.
The repository explicitly uses those event types and an App token at the
privileged PR/notification boundaries. The YAML's presence is not proof that the
credential, permission, branch protection, or downstream delivery succeeded;
verify each run and exact identity read-only before treating it as evidence.
The applicable platform behavior is documented in [GitHub's workflow event
reference](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows).

## State distinctions and stop rules

Keep these states separate:

- A notification carries a candidate fact, not adoption authorization or a success
  receipt.
- A controller-created PR is an allowlisted lock update. It does not generate
  semantic code, merge foreign history, or bypass required review/CI/branch
  protection. Requested auto-merge, CI success, review satisfaction, actual
  merge, and deployment success are separate facts.
- Integration's current Bundle-v4 capability, Site's selected
  `integration-source.json`, and the last deployed Site/Pages artifact are
  different identities. Historical Bundle v3 is compatibility/fixture material,
  not a reason to replace the current v4 selection wholesale.
- The initial committed mode/default fallback is `shadow`; actual repository
  variables, App credentials, protection rules, trusted pins, and Pages
  environment are external live state. An unreadable value is `unknown`.
- A mode change does not replay an earlier run. Reuse requires checking the latest base,
  exact candidate, existing idempotency PR, run attempt, artifact/receipt expiry,
  and current authorization. Do not resend notifications or rerun a stale run in
  this maintenance task.
- The kill switch stops new automatic adoption/deployment; it is not rollback.
  A lock may already have advanced while the last successful deployment remains
  older. Recovery selects a prior qualified immutable lock/artifact through its
  own guarded procedure.

## Read-only diagnosis versus future mutation

For diagnosis, read current branch refs, PRs, workflow runs, artifacts, and
deployments with authenticated read access. Record the exact URL, SHA,
run/attempt, artifact/receipt digest, and first failed or unknown boundary. Do
not call `repository_dispatch`, `workflow_dispatch`, a rerun endpoint, `gh pr
merge`, a notification, a variable/secret API, or Pages deployment here.

Only a separately authorized future operator may perform the mutation sequence:
verify external authorization and protections, bind an exact candidate and fresh
receipt, allow the guarded controller to create/reconcile the existing idempotent
lock PR, wait for its real CI/review/merge outcome, and then apply the distinct
Site/deployment gates. Do not use manual publication as an unapproved bypass for
an automatic path that stopped on an expired artifact, kill switch, or unknown
authorization.
