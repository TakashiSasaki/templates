# Repository agent instructions

This file is a routing index for repository-local Agent Skills on the `composition` authority. It does not replace current code, tests, workflows, schemas, component contracts, or canonical documentation.

## Mandatory merge routing

Before declaring any pull request merge-ready, merging a pull request, or completing a task whose final action is a merge, load and follow `.agents/skills/pr-merge-gate/SKILL.md`.

Task-specific implementation, validation, release, or publication work may establish evidence consumed by the merge gate, but it does not authorize merge by itself. In particular, green CI and `reviews = 0` must never be interpreted as a clean review state.

## Loading discipline

1. Read the smallest task-specific current repository sources needed for the implementation.
2. When the task reaches PR completion or merge readiness, hand control to `pr-merge-gate`.
3. Treat current branch state, PR metadata, current workflows, current checks, reviews, and review threads as live authority for acceptance; historical PR summaries are evidence only.
4. If the PR head changes, discard final acceptance for the previous head and run the merge gate again.
5. If the target branch advances, evaluate base drift before relying on earlier CI or review evidence.

## Authority boundary

`composition` owns Composition semantics, reusable capability/artifact/lifecycle contracts, recipes, schemas, deterministic Composer behavior, validation, examples, and its own release/distribution machinery. Repository-local Agent Skills orchestrate maintenance work; they must not become a second semantic authority for product contracts.
