# Managed repository operation

After `agent-policy` has been adopted, the generated `AGENTS.md` in a product repository becomes the normal instruction entry point for general coding agents. The installed `agent-policy` skill remains the execution entry point for policy-toolchain commands and follows the repository's `.agent-policy.lock` full-SHA pin through the persistent runtime cache.

## Initial discovery order

Before changing a product repository, inspect it in this order:

1. Read the root `AGENTS.md` to identify applicable shared policy, product-specific policy, and required verification commands.
2. Read `.agent-policy.yml` to identify semantic configuration, project-policy inputs, generated outputs, and generated skills.
3. Read `.agent-policy.lock` to identify the immutable toolchain repository/revision and generated-state hashes.
4. If a repository-local skill catalog such as `.agents/skills/manifest.json` exists, read it and identify skills relevant to the change surface.
5. Read the generated skills listed under `Policy system` in `AGENTS.md`.
6. Edit project-policy files referenced by `.agent-policy.yml` only when changing product-specific semantics.

Do not edit generated `AGENTS.md` directly. Rule sources originating from shared profiles are shown as `repository@revision:path` using the pinned toolchain revision. Repository-local policy is shown as a path in the current product repository.

## Verifying policy-related changes

Use `.agents/skills/validate-agent-policy/SKILL.md` for changes involving `.agent-policy.yml`, project policy, generated instructions, generated skills, or the lock file.

For direct toolchain execution, use the installed single skill:

```bash
python /path/to/agent-skills/agent-policy/scripts/run.py \
  --repository . \
  validate --config .agent-policy.yml
python /path/to/agent-skills/agent-policy/scripts/run.py \
  --repository . \
  check --config .agent-policy.yml
```

`scripts/run.py` reads `.agent-policy.lock`, requires `TakashiSasaki/templates` and a full lowercase commit SHA, and selects a validated persistent runtime for that revision. A malformed or mutable lock fails closed rather than falling back to the skill's stable default.

A valid runtime cache entry is reused without network access. If the repository pins another full SHA and no compatible cache entry exists, the skill fetches that revision's runtime lock, derives the cache identity, builds the runtime in a staging directory, verifies it, and only then makes it active.

Do not bypass this path by invoking the mutable `policy` branch, an unpinned release, or a globally installed toolchain of unknown provenance.

When semantic inputs change and generated outputs become stale, run `render` through the same repository-pinned runtime as an explicit synchronization operation, then rerun `validate` and `check`.

## Consumer CI

A product repository should have an agent-policy consistency gate in addition to product-specific tests. The baseline template is `templates/workflows/check-agent-policy.yml.j2` in the toolchain repository.

The workflow must use the complete commit SHA pinned by `.agent-policy.yml` in `uses:`. Do not use mutable or ambiguous references such as `main`, a tag, or an abbreviated SHA.

Because agent-output, project-policy, and generated-skill paths are configurable, limiting CI with `pull_request.paths` to fixed paths can miss relevant changes. The standard workflow runs `agent-policy check` for every pull request. Product-required verification commands run in a separate job or existing product CI.

## Adoption backup

When an existing repository is finalized, the original primary instructions are stored at the `backup_path` recorded in `.agent-policy/adoption.json`. This is cutover evidence and a recovery backup; it is not the current instruction source.

Treat the generated root `AGENTS.md` and current project policy as authoritative. Tools that recursively discover every `AGENTS.md` must not compose the adoption backup as if it were current policy.
