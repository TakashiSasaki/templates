# Maintaining `TakashiSasaki/templates`

This page is for a maintainer or coding agent changing this repository's five
independent authorities. It is not the consumer onboarding guide for installing
Composition or Policy in another repository, and it is not an instruction to
enable publication automation. The authority documents and current workflows
remain normative; this page is a navigation and handoff projection.

## First pass: establish the live task

Work in the authority worktree that owns the requested meaning. Before editing,
use local Git commands plus an authenticated GitHub read surface to retrieve the
live state. A connector/API or `gh` can satisfy the remote read; the command
below is a `gh` example, not a repository-specific tool requirement. Replace no
values with example SHAs:

```sh
pwd
git branch --show-current
git rev-parse HEAD
git status --short --branch
gh pr list --repo TakashiSasaki/templates --state open --head "$(git branch --show-current)"  # example GitHub read
```

The expected output is the authority branch, one full 40-character `HEAD`, an
explicit clean/dirty inventory, and the actual open PR list. A dirty or untracked
worktree, an unexpected branch, a missing GitHub response, or a head that moved
after evidence was collected is a stop for mutation until the state is explained.
Do not use an old conversation, an old PR, or the published Site as a substitute
for this snapshot. If a live API, variable, protection rule, credential, run,
artifact, or deployment cannot be read, record it as `unknown`; do not infer
`false`.

A branch name is useful for discovering the current entry point. A branch name is
not evidence for qualification, review, artifact provenance, or publication:
those records use the exact full SHA captured after the relevant event. These
authorities have independent Git histories. A path such as `../integration` is
not a cross-branch reference: use an explicit repository, authority, branch/SHA,
and path, or a separate checkout. A branch-local `.agents/skills/` directory is
available only in the checkout that contains it.

The live repository currently resolves its default branch to `site`; confirm that
with the read-only remote snapshot before relying on the Site adapter or any
default-branch workflow. The default branch is a dispatch routing fact, not an
authority merge relationship.

## Landing route for maintenance pull requests

After selecting the owning authority, use that checkout's
`.agents/skills/land-templates-stack/SKILL.md` for both a single maintenance PR
and a same-authority stack. Verify its adjacent `source.json` before reading
the procedure. All five authority routes resolve the same immutable canonical
snapshot:

- repository: `TakashiSasaki/templates`;
- revision: `9c2c538d5ee0b866379db40e5c24b29d60e155ba`;
- rule: `repository-policy/stacked-pr-landing.md`, blob
  `9761cdbcd21b0e8ba2f3eb2ffb306725a82f5eef`;
- landing Skill: `repository-skills/land-templates-stack/SKILL.md`, blob
  `06efa38681e374636bcabcbcb984be5ec43b47ee`;
- review-scope planner: `repository-skills/land-templates-stack/scripts/plan_review_scope.py`, blob
  `16c0907a19e3f8d339fe81e29f7b204e791fc781`.

The local shim must resolve the rule and planner from that snapshot, not from a consumer
worktree, mutable `policy` branch, latest ref, or unverified copy. Source
failure is blocked. The separate shared PR gate remains pinned to
`TakashiSasaki/templates@412c525478d23ca889a649daf51b6261f6746ef3` and is
loaded through the authority-local `pr-merge-gate` route. Site acceptance,
review, merge authorization, publication, and deployment remain distinct
states; this onboarding guide does not authorize any of them.

## Choose the owner and first reading

| Task | Semantic owner and discovery branch | Read first | Editable source and local proof | Normal stop boundary |
|---|---|---|---|---|
| Add or revise an information-model record | Modeling / `modeling` | [`AUTHORITY.md`](https://github.com/TakashiSasaki/templates/blob/modeling/AUTHORITY.md), [`AGENTS.md`](https://github.com/TakashiSasaki/templates/blob/modeling/AGENTS.md), [`docs/intake.md`](https://github.com/TakashiSasaki/templates/blob/modeling/docs/intake.md), [`register-information-model`](https://github.com/TakashiSasaki/templates/blob/modeling/.agents/skills/register-information-model/SKILL.md) | `records/`; run `python3 tools/catalog.py generate`, then `python3 tools/qualify.py`; generated catalogs/docs are outputs | Registration/revision evidence; no Integration adoption or Site publication |
| Change a Composition component, recipe, contract, or Composer | Composition / `composition` | [`AGENTS.md`](https://github.com/TakashiSasaki/templates/blob/composition/AGENTS.md), [`README.md`](https://github.com/TakashiSasaki/templates/blob/composition/README.md), the owning component contract | `components/`, `recipes/`, schemas, and Composer source; `generated/` and materialized manifests are regenerated; run `python3 scripts/run_composition_preflight.py fast` and the applicable committed `full` profile | Composition contract/qualification; no provider lock or Site adoption |
| Change a generic policy, review, or maintenance procedure | Policy / `policy` | [`AGENTS.md`](https://github.com/TakashiSasaki/templates/blob/policy/AGENTS.md), [`README.md`](https://github.com/TakashiSasaki/templates/blob/policy/README.md), [`orchestrate-repository-change`](https://github.com/TakashiSasaki/templates/blob/policy/skills/orchestrate-repository-change/SKILL.md), applicable `repository-policy/` file | `.agent-policy.yml` and `repository-policy/`; regenerate `AGENTS.md`, review policy, lock, and generated skills with the exact selected toolchain; run the maintainer-validation sequence | Generic policy evidence; no product, Integration, or Pages change |
| Change provider selection, Bundle, publication mapping, or promotion | Integration / `integration` | [`AUTHORITY.md`](https://github.com/TakashiSasaki/templates/blob/integration/AUTHORITY.md), [`README.md`](https://github.com/TakashiSasaki/templates/blob/integration/README.md), [`RELEASE.md`](https://github.com/TakashiSasaki/templates/blob/integration/RELEASE.md), [`integration-publication-maintenance`](https://github.com/TakashiSasaki/templates/blob/integration/.agents/skills/integration-publication-maintenance/SKILL.md) | `publication-sources.json`, Integration contracts and producer; reports, receipts, candidate locks, and Bundle artifacts are generated; run `python3 scripts/run_integration_preflight.py fast --expected-head "$(git rev-parse HEAD)"`, then `ready`/`providers` as applicable | Integration qualification/promotion evidence; no Site lock, mode, or deployment mutation |
| Change Site CSS, runtime, accessibility, PWA, or presentation only | Site / `site` | [`MAINTENANCE.md`](../MAINTENANCE.md), [`PUBLISHING.md`](../PUBLISHING.md), [`AGENTS.md`](../AGENTS.md), the applicable Site skill | Site source and tests; keep `integration-source.json` unchanged; run `python scripts/run_site_preflight.py fast`, then clean `source-ready` and relevant acceptance | Site PR/acceptance; no provider adoption unless explicitly requested |
| Diagnose why a provider change is not on the Web | Cross-authority read-only investigation, starting at Site's [publication automation runbook](publication-automation.md) | Current provider workflows, Integration workflows, Site workflows, exact PR/run/artifact/deployment state | Do not edit first. Bind every event to immutable identities; stop on unknown or stale evidence | Explain the first failed/unauthorized boundary; no rerun, dispatch, or lock edit |
| Resume interrupted work | The authority named by the existing PR/Issue checkpoint | Policy Work-ledger guidance plus the authority's current `AGENTS.md` and skill | Restore live base/head/PR/run/artifact/review/auth state; reuse valid evidence only | One next safe action or a recorded stop; no duplicate PR/review/run |

The first three rows deliberately distinguish this repository's maintenance from
consumer onboarding. A consumer repository should follow its installed product
skill; it should not use this page to mutate a provider branch.

The route matrix below is a clean-room maintenance walkthrough, not a second
policy. It names the owner, first reading, editable source, validation boundary,
and safe stop for each common task. If the default `site` branch does not yet
link to this page, treat that as an onboarding-stack dependency rather than
reconstructing the route from old pull requests.

## Source, projection, and generated material

Edit the source that owns the meaning and regenerate its projections:

| Authority | Source of meaning | Do not hand-edit |
|---|---|---|
| Modeling | `records/` and the local record schemas | `CATALOG.md`, `catalog.json`, `docs/resources/` |
| Composition | Components, recipes, schemas, Composer source | `generated/` and materialized consumer/contract outputs |
| Policy | `.agent-policy.yml`, `repository-policy/`, and the selected toolchain | `AGENTS.md`, `.review-authority/review-policy.md`, `.agent-policy.lock`, generated skills |
| Integration | `publication-sources.json`, Bundle contracts, producer declarations and implementation | candidate locks, qualification reports, receipts, Bundle archives, and workflow artifacts |
| Site | Site source, `policy/project.md`, renderer inputs and tests | generated `AGENTS.md`, build/provenance artifacts, rendered Site output, and Pages artifacts |

The Site `AGENTS.md` is generated from Site's `.agent-policy.yml`,
`policy/project.md`, and selected toolchain revision
`349df5037756d78837e1fff83cf3791c81778047`; update the source and run that
exact generator. Do not replace it with an unreviewed Policy checkout. The
Policy authority's own generated outputs follow its separate pinned toolchain
`33a7ab809225c2a8b8dd2598ef04d0a39cf076a7`. A toolchain adoption pin and a
publication selection pin are different trust decisions.

## Validation, CI, and review order

Use the authority's existing cheap construction check while editing. Before a
remote or expensive lane, create a clean committed frontier and bind the command
to its exact `HEAD`. Cheap local success means only that the selected local
contract passed; it is not merge approval, publication qualification, adoption,
or deployment. Provider checkouts, exact pins, package/network needs, artifact
acquisition, browser use, and side effects must be stated in the authority's
instructions rather than guessed from a command name.

Remote CI is an independent evidence layer. It must run against the proposed
head and the CI lane that actually classifies the changed files; optional
diagnostics are not new merge gates. Review findings, exact-head acceptance,
required checks, branch protection, merge, and deployment are separate states.
Under human-handoff, do not merge or enable auto-merge; report pending CI/review
as pending.

Use the pinned review-scope planner after the Site source-ready and
authority-owned checks. A fixed Bundle with a bounded presentation change may
use an exact-head delta review; renderer meaning, Bundle protocol, PWA/cache,
trust boundary, Integration adoption, or final-artifact/deployment binding
changes expand the related Site scope. Reuse only explicit complete coverage,
and keep independent review separate from local tests and generated receipts.

## PR topology and handoff

Stack PRs only within one authority: a later `modeling` PR may base on an earlier
`modeling` PR, but a Site PR must not use an Integration PR as its Git base. A
cross-authority dependency is recorded in both PR descriptions and the existing
Policy Work ledger with the authority, repository, base/head SHA, dependency
reason, and next safe action. Independent histories remain independent; do not
merge, rebase, cherry-pick, copy another authority's canonical source, or create
a worktree topology that the repository has not declared.

The PR checkpoint is the default Work-ledger backend. Do not create a new session
schema or parallel finding ledger. On resume, check scope and stop boundary,
each authority's base/head, dependency PRs, success of prior external operations,
reusable CI/review evidence, pending runs/artifacts/deployments, and current
authorization. Check for an existing candidate PR before opening one, do not treat
a stale run as current, and do not poll an external service indefinitely.

## Publication chain: event, PR, and boundary

The following is a current-code map. A notification carries a candidate fact; it
does not by itself authorize adoption or prove success. The exact run/attempt,
artifact/receipt, workflow path, producer/provider SHA, policy/controller pins,
and consumer base must remain bound at every handoff.

| Start event | Executing authority and workflow | Immutable input and result | Next event / authorization / stop |
|---|---|---|---|
| Provider `modeling` push or PR qualification | Modeling `.github/workflows/modeling-ci.yml`; Composition `.github/workflows/reference-consumer-publication.yml`; Policy `.github/workflows/integration-compatibility.yml` | Provider checkout at the PR head or pushed full SHA; local/provider qualification and, on a successful provider push, a `publication.provider-qualified` dispatch sent with run/attempt/workflow identity | The dispatch is only a candidate notification. Provider file addition or a green provider check does not publish it; stop if declaration/allowlist or qualification evidence is absent |
| `publication.provider-qualified` received on default `site` | Site `.github/workflows/provider-publication-dispatch.yml` | Payload is checked for exact provider SHA and workflow facts; Site resolves the current `integration` branch to one producer SHA and calls the pinned reusable Integration controller at the reviewed Integration revision | Adapter does not do Integration semantics or Site adoption. Stop on invalid payload, unresolved/moved producer head, or unavailable controller |
| Candidate reconciliation | Integration `.github/workflows/integration-reconcile.yml` | Exact producer/provider tuple, Bundle artifact, candidate qualification, trusted-controller regeneration, and trusted receipt; default code fallback is `shadow`, but live repository variables are external | `shadow` reports only. Only separately authorized `adoption-only`/`auto-publish` with positive authorization, exact policy/controller pins, kill switch off, fresh receipt, expected base, and protected branch may create an idempotent `automation/publication-*` allowlisted lock PR. It changes lock JSON only; it is not LLM code generation or authority-history merge |
| Integration automation PR merged | Integration `.github/workflows/integration-promotion-notify.yml` | Merged exact Integration SHA, requalification, Bundle and trusted-promotion receipt | Sends `publication.integration-promoted` to Site only after the workflow's notification conditions. Notification is not Site adoption; stop if merged head, artifact, receipt, or pins no longer match |
| `publication.integration-promoted` received | Site `.github/workflows/publication-reconcile.yml` | Exact Integration revision, Bundle schema/identity/content digest, Bundle artifact and trusted receipt; Site qualification renders with provider checkouts absent | In `shadow`, report only. In an externally activated authorized mode, only an idempotent `automation/site-publication-*` lock PR with the four allowlisted `integration-source.json` fields may be prepared; Site qualification and branch protection still decide merge |
| Site automation PR merged | Site `.github/workflows/site-publication-notify.yml` | Merged Site SHA must be the current `site` head and must have passed the guarded automation path | Only the `auto-publish` conditions dispatch `deploy-pages.yml` with `automatic=true` and exact `site_revision`. A normal Site UI PR does not use this post-merge trigger |
| Pages deployment | Site `.github/workflows/deploy-pages.yml` and reusable `build-pages.yml` | Exact Site SHA, selected Bundle identity, trusted receipt for automatic mode, Pages artifact ID/digest, final artifact gate, `github-pages` environment | Deploys only after qualification, freshness, artifact binding, current-head check, and environment authorization. `automatic=false` workflow dispatch is a separate explicit human path; kill switch stops new work and is not rollback |

`PUBLICATION_AUTOMATION_MODE`, `PUBLICATION_AUTOMATION_AUTHORIZED`,
`PUBLICATION_POLICY_REVISION`, `PUBLICATION_CONTROLLER_REVISION`,
`PUBLICATION_AUTOMATION_KILL_SWITCH`, App credentials, branch protection, and
Pages environment settings are live authorization inputs outside these source
files. This implementation does not read or change them. A mode change does not
replay an earlier run; an authorized operator must re-check current base, exact
candidate, existing PR, run attempt, artifact expiry, receipt, and pins. Auto-
merge requested by a controller, successful CI, satisfied required review,
actual merge, and successful deployment are independent states.

For a read-only diagnosis, inspect current branches, PRs, workflow runs, artifacts,
and deployments with authenticated read access and record URLs/SHAs; never send a
dispatch, rerun, notification, variable update, or deployment. A future mutation
requires its separately authorized operator, exact inputs, protected PR, and
owning boundary. A kill switch leaves the last known successful deployment in
place; it does not repair a lock that already advanced or select a rollback.

## Human-first walkthroughs

These are document-only walkthroughs unless a human reviewer independently
performs the route; no independent agent or external write is implied.

| Scenario | Semantic owner and authority branch | First document and skill | Editable source versus generated material | Cheapest useful validation, PR base, and cross-authority dependency | Stop, next safe action, and authorization |
|---|---|---|---|---|---|
| Register or revise an information-model record | Modeling / `modeling` | `AUTHORITY.md`, `AGENTS.md`, `docs/intake.md`, then `register-information-model` | Edit `records/`; generated catalogs and resource docs are outputs | `python3 tools/catalog.py generate`, then `python3 tools/qualify.py`; stack only on a Modeling PR; Integration is informational until a separately authorized publication path | Stop at registration/qualification evidence. Do not adopt in Integration, change mode, merge, dispatch, rerun, or deploy. |
| Change a Composition schema, component, or recipe | Composition / `composition` | `AGENTS.md`, `README.md`, and the owning component contract | Edit components, recipes, schemas, and Composer source; regenerate `generated/` and materialized manifests | `python3 scripts/run_composition_preflight.py fast`, then the applicable committed `full` profile; stack on Composition only; provider declarations are cross-authority information, not Git ancestry | Stop at Composition contract and qualification. Do not move the change to Modeling or edit a Site lock without separate authorization. |
| Change a generic Policy maintenance or review procedure | Policy / `policy` | `AGENTS.md`, `README.md`, `orchestrate-repository-change`, and the applicable `repository-policy/` source | Edit `.agent-policy.yml` and `repository-policy/`; regenerate `AGENTS.md`, review policy, lock, and skills | Use the exact selected toolchain and the documented Policy validation sequence; stack on Policy only; Site references are informational | Stop after Policy evidence. Do not promote the toolchain pin, merge, adopt, publish, or deploy under this task. |
| Make a Site-only CSS or presentation fix | Site / `site` | `MAINTENANCE.md`, `PUBLISHING.md`, `AGENTS.md`, and the applicable Site skill | Edit Site source and tests; do not hand-edit generated `AGENTS.md`, build output, Pages artifacts, or `integration-source.json` | Run `python scripts/run_site_preflight.py fast`, then clean `source-ready` and relevant acceptance; stack on Site; retain the current Integration selection | Stop at Site PR/acceptance. A presentation change does not authorize provider adoption, lock updates, mode changes, merge, or deployment. |
| Diagnose a provider change that merged but is not visible on the published Web site | Read-only investigation across the named authority boundary | Start with `docs/publication-automation.md`, then the current provider, Integration, and Site workflows | Edit nothing while diagnosing; retain provider SHA, Integration SHA, Site SHA, run/attempt, artifact, receipt, PR, and deployment identities | Walk declaration → qualification → dispatch → mode/auth → Integration lock PR/merge → receipt → Site lock PR/gate → deployment; each authority is an informational dependency, never a Git base | Stop at the first failed, stale, unauthorized, or unreadable boundary. Next safe action is a report or authorized handoff; do not dispatch, rerun, edit locks, or deploy. |
| Diagnose a successful shadow qualification | Integration / `integration` | `RELEASE.md`, `integration-publication-maintenance`, and the publication runbook | Inspect candidate evidence, receipt, and mode; do not edit source or fabricate an adoption PR | Bind the shadow run, exact candidate, controller/policy pins, receipt, and artifact expiry; no PR base is created | Shadow success is evidence only. Stop and report; do not change mode, resend, rerun, or request adoption from this conversation. |
| Handle an auto-publication lock PR waiting for review | Site or Integration controller boundary named by the PR | Publication runbook, `PUBLISHING.md`, and the Site cutover/acceptance skill | The controller may write only its allowlisted lock fields; do not hand-edit generated candidates or source semantics | Check exact base/head, controller receipt, CI, required review, branch protection, and current authorization; stack only within the owning authority | Waiting for required review is normal. Next safe action is the authorized review/merge decision; do not bypass protection, claim publication, or deploy. |
| Resume interrupted work from an existing PR or checkpoint | The authority named by the existing PR/Issue checkpoint | Policy Work-ledger guidance, current authority `AGENTS.md`, and its skill | Restore live PR/head/base, run/attempt, artifact/receipt, review, and authorization state; reuse only current evidence | Check for an existing same-authority PR and exact-head evidence before creating anything; cross-authority references remain informational | Take one safe next action or record a stop. Do not create a duplicate PR/review/run, treat stale evidence as current, or poll indefinitely. |
| Handle an expired artifact or active publication kill switch | Integration/Site publication boundary | Publication runbook and the current reconciliation/deploy workflows | Edit nothing; an expired artifact or kill switch invalidates the automatic candidate path, not the last successful deployment | Verify expiry, kill-switch state, current head, receipt, and existing PR read-only; no new PR base or rerun is inferred | Stop automatic processing. Next safe action is an authorized operator decision; do not use manual publication as an unapproved bypass, change mode, dispatch, rerun, or deploy. |
| Explain why Site may still select an older Integration Bundle while Integration has newer capability | Site selection plus Integration capability, with both authorities kept independent | `docs/authority-model.md`, the publication runbook, and `integration-source.json` contract | Current capability is owned by Integration; Site's selected lock and generated/deployed projections are separate; edit the Site lock only through an authorized adoption path | Inspect exact Bundle identity, selected input, Site revision, and deployed artifact; an adoption PR, if authorized, is a Site PR based on Site | Stop with the distinction documented. A newer capability or notification does not change selection or deployment; no pin update, merge, or deployment is implied. |

The completion record must name the semantic owner, branch and exact head,
source/projection changes, local and remote validation, review state, PR
dependencies, and the stop boundary. “Documented” or “PR created” does not mean
deployed or unattended operation enabled.

In this guide, “selected input” means the exact committed
`integration-source.json` identity, while “actually deployed” means the Site
revision and immutable Pages artifact that passed the final deployment gate.
Neither a current capability nor a notification changes the selected input, and
neither a selected lock nor a created PR proves that it is deployed.
