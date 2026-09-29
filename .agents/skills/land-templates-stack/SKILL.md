---
name: land-templates-stack
description: Prepare or land a modeling change using local validation and GitHub repository settings.
---

# Modeling PR maintenance

Use this procedure only for a PR belonging to this authority. Read `AGENTS.md` and
run the affected local validation. Open one PR for a coherent change; create a stack
only if it makes review easier. All bases and commits remain in this authority's history.

Describe the problem, behavior, checks and remaining limitations. Check current PR
state before creating another PR or review request. Review only the changed behavior
and its actual dependencies. Existing hosting protections apply; there is no pinned
external procedure, mandatory review planner, Work-ledger format or cross-authority gate.

Respect the user's merge/deployment authorization. If landing is authorized, use the
current proposed SHA as the merge precondition and verify the result. Otherwise hand
off the implementation and validation result. A provider change never requires a Site
adoption PR. An Integration artifact is consumed asynchronously by Site.
