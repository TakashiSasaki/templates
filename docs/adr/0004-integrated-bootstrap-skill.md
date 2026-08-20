# ADR-0004: Integrate the bootstrap trust seed into the policy branch

> Historical record. This decision is superseded by ADR-0007 and must not be used as the current Policy architecture.

- Status: Superseded by ADR-0007
- Date: 2026-08-01

## Context

Repository onboarding required a small, independently reviewable trust seed that could select a safe initialization or adoption route without executing a mutable branch tip or granting generic mutation authority.

At the time of this decision, the bootstrap trust boundary was implemented as a separately installed skill under the same `policy` history. That architecture has since been replaced by ADR-0007, which preserves the immutable trust boundary while using one `agent-policy` skill and a persistent runtime cache before and after adoption.

## Historical decision

The original decision stored the bootstrap package at `skills/bootstrap-agent-policy/` in the `policy` branch and used `bootstrap-manifest.yml` to pin a reviewed full commit SHA. The manifest deliberately omitted adoption finalization and treated pin, route, script, installer, and test changes as trust-anchor changes.

The Python package and executable remained named `agent-policy`, and generated product state used immutable `TakashiSasaki/templates` full-SHA references.

## Supersession

ADR-0007 removes the separately installed bootstrap package and replaces its manifest with `skills/agent-policy/runtime-manifest.json`. The replacement keeps the important invariants of this ADR:

- immutable full-SHA execution;
- a separately reviewable repository-facing trust surface;
- state-derived onboarding rather than mutable branch execution;
- no migration-finalize route in generic bootstrap; and
- explicit review of trust-anchor changes.

The current architecture and distribution model are defined by ADR-0007. This ADR remains as historical rationale for why onboarding trust is isolated from mutable branch tips.
