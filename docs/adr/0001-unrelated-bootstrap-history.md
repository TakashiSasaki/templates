# ADR-0001: Separate bootstrap history

- Status: Superseded
- Superseded by: ADR-0004

## Original decision

Keep `bootstrap-agent-policy` as an orphan branch unrelated to the policy compiler branch so that the branch root can be cloned directly as an onboarding skill.

## Supersession

The repository migration showed that the required trust boundary is provided by an immutable manifest, a restricted orchestration script, explicit safety constraints, and independent review of trust-anchor changes. It does not require an unrelated Git history.

ADR-0004 integrates the bootstrap package under `skills/bootstrap-agent-policy/` in `TakashiSasaki/templates:policy` while preserving the full-SHA pin and non-finalizing route boundary.
