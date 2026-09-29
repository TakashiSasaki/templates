---
name: site-publication-cutover
description: Use local site validation and the asynchronous publication route.
---

# Site maintenance route

Read `AGENTS.md` and [PUBLISHING.md](../../../PUBLISHING.md). Follow the current implementation
and local tests. The former pinned controller/adoption procedure is retired.

For a defect, reproduce it at its owning layer using the same input artifact. Fix the
source and run focused regression checks, then the applicable local suite. Reuse the
artifact when upstream source branches move. Do not add upstream qualification, lock PRs,
review planners or whole-stack gates to a local change. Report actual validation results.

For deployment or PR landing, use the user's authorization and current GitHub settings.
Do not infer that an artifact upload is a deployment. Never merge authority histories.
