---
id: policy-repo.preserve-history-boundary
severity: mandatory
overridable: false
order: 1010
---
# Preserve unrelated branch histories

The `policy`, `skill`, `site`, and `webapp` branches have unrelated histories. Do not merge, rebase, or cherry-pick across those branch histories to distribute policy. Consumers adopt reviewed shared policy through immutable full commit SHAs and generated projections instead.
