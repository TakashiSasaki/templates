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
for provider qualification events. It forwards exact revisions to the pinned
Integration controller; it does not perform Integration semantics itself.

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
environment. No timestamp or provenance file may be rewritten after that gate.

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
