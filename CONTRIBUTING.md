# Contributing

This is the contribution entry point for the Policy provider and shared corpus
in `TakashiSasaki/templates`. Applying Policy or maintaining local configuration
in another repository starts with [Consumer application](docs/consumer/index.md).
For shared-source changes, consult [Policy authoring](docs/policy-authoring.md)
and [Repository structure](docs/repository-structure.md) to locate the owner.

[Maintainer workflow](docs/policy-maintainer-workflow.md) explains trusted-base
operation, self-hosting, and separate promotion. [Documentation publication](docs/documentation-publication.md)
covers the local build; [Publication catalog](docs/publication-catalog.md#deferred-maintainer-publications)
records the four canonical maintainer sources as active Policy publication entries,
while Integration owns their staged-to-active reader promotion and integrated exposure.

Canonical repository-maintainer operating policy is declared by `.agent-policy.yml` and the files under `repository-policy/`; generated `AGENTS.md` and `.review-authority/review-policy.md` are context projections of that authority, and `.agents/skills/pr-review/` is the generated provider-neutral review procedure.

For architecture-sensitive changes, follow `repository-policy/architecture-decisions.md`. In particular, that canonical rule governs changes to the policy schema, rule merge or override semantics, lock-file format, and the repository-facing skill/runtime trust model.

For validation requirements, follow `repository-policy/maintainer-validation.md` and the maintained development sequence in `README.md`. Typical focused local checks include:

```bash
python -m pytest
python -m compileall -q src scripts skills/agent-policy/scripts
```

Generated fixtures are expected to remain reproducible from committed inputs; generated-output synchronization itself is governed by the shared policy selected in `.agent-policy.yml`.
