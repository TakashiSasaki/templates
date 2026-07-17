# ADR-0001: Separate bootstrap history

## Decision

Keep `bootstrap-agent-policy` as an orphan branch unrelated to `main`.

## Rationale

The bootstrap skill is an independently distributed trust seed. Its review, release cadence, and direct-clone directory layout differ from the policy compiler. Sharing a history would blur the boundary and make branch-level distribution less explicit.
