---
id: webapp-source.preserve-unrelated-history
severity: mandatory
overridable: false
order: 1010
---
# Preserve the webapp branch history boundary

Template-development changes must be based on `webapp`. The `webapp`, `skill`, `site`, and `policy` histories are unrelated.

Do not merge, rebase, or cherry-pick another major branch into `webapp` merely to share files or policy. Cross-branch reuse must occur through reviewed immutable references or independent reimplementation at the appropriate ownership boundary.
