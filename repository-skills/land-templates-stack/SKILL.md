---
name: land-templates-stack
description: Prepare independent authority changes using local checks.
---

# Maintain templates

Read the target authority's AGENTS.md. Work on a branch descended only from that
authority. Validate its own implementation. Prepare a clear PR with the behavior,
checks and limitations. Integration and Site consume publications asynchronously.
Their states do not gate unrelated source work. Observe ordinary repository merge
permissions; do not create a review planner, source manifest or cross-authority pin.
