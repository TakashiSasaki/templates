# Standard Maintainer Workflow Entrypoint and Live Review Adapter

This reference contains detailed operational specifications and CLI commands for the candidate bootstrap runner, maintainer entrypoint, and live adapter. Consult this file only when executing or configuring the maintainer workflow tools.

## 1. Architecture Components

Maintainers execute the review artifacts workflow via the standard CLI entrypoint and live adapter rather than hand-writing transient scripts:

- **Bootstrap Runner**: `scripts/run_maintainer_workflow.py`
  - Verifies the immutable source manifest against local Git object storage.
  - Materializes the verified closure in an isolated execution environment.
  - Executes the maintainer entrypoint within the closure lifetime while ignoring any mutable worktree modifications.
- **Entrypoint**: `repository-skills/land-templates-stack/scripts/maintain_review_stack.py`
  - Orchestrates state observation, candidate and revision binding validation.
  - Executes the scope planner from immutable source references.
  - Renders artifacts via `render_review_artifacts.py`.
  - Publishes artifacts via `publish_review_artifacts.py`.
  - Supports offline preview and safe live revalidation via `live_review_adapter.py`.
- **Live Adapter**: `repository-skills/land-templates-stack/scripts/live_review_adapter.py`
  - Provides standard `resolve(context, payload, provider)` callback and configured `GitHubLiveRevalidationAdapter` instances for `publish_review_artifacts.py`.

## 2. Safety Boundaries and Operational Modes

- **Preview Mode**: Writes normalized artifacts and manifests locally without any external mutations.
- **Remote Publication**: Strictly fails closed: requires explicit `--apply`, `--authorize`, and `--serialized-writer` flags alongside valid credentials.

## 3. Standard CLI Usage

```bash
# Trusted isolated execution via bootstrap runner (preview mode):
python scripts/run_maintainer_workflow.py \
  --trusted-base-sha <TRUSTED_BASE_SHA> \
  --pr <PR_NUMBER> --head-sha <HEAD_SHA> --base-sha <BASE_SHA> \
  --output-dir /path/to/artifacts
```

```bash
# Authorized remote publication (requires explicit authorization flags):
python repository-skills/land-templates-stack/scripts/maintain_review_stack.py \
  --pr <PR_NUMBER> --head-sha <HEAD_SHA> --base-sha <BASE_SHA> \
  --apply --authorize --serialized-writer
```
