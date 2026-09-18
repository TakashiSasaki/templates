---
name: integration-publication-maintenance
description: Route maintenance of Integration provider selection, deterministic Bundles, and publication-chain evidence.
---

# Integration publication maintenance

Use this thin route to classify a `templates` maintenance task whose semantic
owner is Integration: provider selection, publication declarations, Bundle
qualification, promotion evidence, or diagnosis of the handoff to Site. It
connects existing authority documents and workflows; it does not define a new
publication policy.

## Purpose

Keep provider capability, selected input, and deployed input distinct while
following the exact-identity and trusted-receipt boundaries already owned by
Integration and Site.

## Use when

- changing or reviewing `publication-sources.json`, Bundle contracts, or provider
  publication declarations;
- qualifying an exact Integration candidate or checking a promotion receipt; or
- tracing a provider-qualified or Integration-promoted event through the current
  workflows without changing Site.

## Do not use when

- registering or revising an information-model record (use Modeling's
  `register-information-model` skill);
- changing Composition or Policy semantics; or
- adopting a Bundle in Site, changing Site locks, dispatching Pages, changing
  repository variables/secrets/protection, rerunning a stale event, or merging.
  Those actions need their owning authority and explicit authorization.

## Canonical authorities

Read `AGENTS.md`, `AUTHORITY.md`, `README.md`, `RELEASE.md`,
`publication-sources.json`, and the relevant `.github/workflows/` definitions.
For the downstream boundary read Site's
`https://github.com/TakashiSasaki/templates/blob/site/docs/publication-automation.md`
and Site `PUBLISHING.md` by explicit remote reference or a separate Site
checkout. Policy's `orchestrate-repository-change` skill supplies generic
stacking, evidence, and Work-ledger rules; do not copy it here.

## Inputs

Capture the actual `integration` branch, full current `HEAD`, dirty/untracked
state, relevant PRs, exact producer/provider SHAs, Bundle schema/identity/digest,
workflow run and attempt, artifact/receipt names and digests, and the externally
reported mode, authorization, pins, and kill-switch state. Unreadable external
settings are `unknown`, not `false`. Branch names discover; full SHAs bind
qualification and evidence.

## Stop conditions

Stop on a moving or stale head, missing or expired artifact/receipt, mismatched
workflow identity, unknown authorization, unsupported Bundle, failed qualification,
duplicate automation PR, active kill switch, missing trusted pins, or any request
to cross the Site adoption/deployment boundary. Shadow success is evidence only.

## Evidence to report

Report the owner, exact base/head and dependencies, local `fast`/`ready`/`providers`
result, remote workflow and review state, candidate/selected/deployed distinction,
next safe action, and the stop boundary. Keep the checkpoint in the existing PR or
Issue Work ledger. On resume, restore live state and reuse valid evidence; do not
create a new ledger, empty commit, duplicate PR, or unbounded polling loop.
