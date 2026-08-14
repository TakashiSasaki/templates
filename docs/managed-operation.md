# Managed repository operation

After `agent-policy` has been adopted, the generated `AGENTS.md` in a product repository becomes the normal entry point for general coding agents. This page defines an operating sequence that both an agent opening the repository for the first time and a human maintaining policy can follow consistently.

## Initial discovery order

Before changing a product repository, inspect it in this order:

1. Read the root `AGENTS.md` to identify applicable shared policy, product-specific policy, and required verification commands.
2. Read `.agent-policy.yml` to identify the pinned toolchain repository and full commit SHA, project-policy inputs, generated outputs, and generated skills.
3. If a repository-local skill catalog such as `.agents/skills/manifest.json` exists, read it and identify skills relevant to the change surface.
4. Read the generated skills listed under `Policy system` in `AGENTS.md`.
5. Edit project-policy files referenced by `.agent-policy.yml` only when changing product-specific semantics.

Do not edit generated `AGENTS.md` directly. Rule sources originating from shared profiles are shown as `repository@revision:path` using the pinned toolchain revision. Repository-local policy is shown as a path in the current product repository.

## Verifying policy-related changes

Use `.agents/skills/validate-agent-policy/SKILL.md` for changes involving `.agent-policy.yml`, project policy, generated instructions, generated skills, or the lock file.

Even when no installed `agent-policy` command is available, do not switch to a mutable branch or an unpinned release. Use the `toolchain.repository` and `toolchain.revision` from `.agent-policy.yml` and run that pinned revision in a temporary environment.

```bash
uvx --from "git+https://github.com/<repository>.git@<revision>" \
  agent-policy --repository . validate --config .agent-policy.yml
uvx --from "git+https://github.com/<repository>.git@<revision>" \
  agent-policy --repository . check --config .agent-policy.yml
```

If `uvx` is unavailable, install the same full-SHA Git reference into a temporary virtual environment. Do not install an unversioned toolchain into a global environment.

When semantic inputs change and generated outputs become stale, run `render` through the pinned toolchain as an explicit synchronization operation, then rerun `validate` and `check`.

## Consumer CI

A product repository should have an agent-policy consistency gate in addition to product-specific tests. The baseline template is `templates/workflows/check-agent-policy.yml.j2` in the toolchain repository.

The workflow must use the complete commit SHA pinned by `.agent-policy.yml` in `uses:`. Do not use mutable or ambiguous references such as `main`, a tag, or an abbreviated SHA.

Because agent-output, project-policy, and generated-skill paths are configurable, limiting CI with `pull_request.paths` to fixed paths can miss relevant changes. The standard workflow runs `agent-policy check` for every pull request. Product-required verification commands run in a separate job or existing product CI.

## Adoption backup

When an existing repository is finalized, the original primary instructions are stored at the `backup_path` recorded in `.agent-policy/adoption.json`. This is cutover evidence and a recovery backup; it is not the current instruction source.

Treat the generated root `AGENTS.md` and current project policy as authoritative. Tools that recursively discover every `AGENTS.md` must not compose the adoption backup as if it were current policy.
