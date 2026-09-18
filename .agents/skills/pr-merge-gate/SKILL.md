---
name: pr-merge-gate
description: Load the separately pinned shared PR acceptance gate for a Policy maintenance change.
---

# Policy-local shared gate reference

Validate the adjacent `source.json` before loading the shared
`skills/pr-merge-gate/SKILL.md` source. Require its repository, full immutable
revision, canonical path, and blob identity; stop as blocked on any mismatch
or mutable fallback. This shim contains no acceptance semantics and does not
call the repository-maintainer landing Skill.
