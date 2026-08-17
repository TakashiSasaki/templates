# Contributing

Canonical repository-maintainer operating policy is declared by `.agent-policy.yml` and the files under `repository-policy/`; generated `AGENTS.md` and `.github/REVIEW_GUIDELINES.md` are projections of that authority.

For architecture-sensitive changes, follow `repository-policy/architecture-decisions.md`. In particular, that canonical rule governs changes to the policy schema, rule merge or override semantics, lock-file format, and the repository-facing skill/runtime trust model.

For validation requirements, follow `repository-policy/maintainer-validation.md` and the maintained development sequence in `README.md`. Typical focused local checks include:

```bash
python -m pytest
python -m compileall -q src scripts skills/agent-policy/scripts
```

Generated fixtures are expected to remain reproducible from committed inputs; generated-output synchronization itself is governed by the shared policy selected in `.agent-policy.yml`.
