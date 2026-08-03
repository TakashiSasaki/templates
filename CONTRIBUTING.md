# Contributing

Changes to the policy schema, rule merge semantics, lock-file format, stable-release descriptor, or bootstrap trust model require an architecture decision record.

Before committing, create and verify the clean candidate environment documented in `README.md`, then run the complete branch-maintainer checks from that environment:

```bash
python scripts/verify_ci_environment.py
python -m pip check
python scripts/verify-release-state.py
python -m ruff check src tests scripts skills/bootstrap-agent-policy/scripts
python -m pytest
python -m compileall -q src scripts skills/bootstrap-agent-policy/scripts
agent-policy --help
```

Documentation changes must also use the separate clean environment backed by `requirements-docs.lock`, pass `scripts/verify_docs_environment.py` and `pip check`, regenerate the committed previews and assets, verify the documented tree, and complete `python -m mkdocs build --strict --clean`.

Dependency changes must update the applicable reviewed direct input, complete arbitrary-exact lock, installed-set or release-verifier expectations, workflow, and documentation together. Do not copy candidate-CI dependencies into the documentation or stable-probe locks unless those independent environments actually require them.

Generated fixtures and documentation assets must be reproducible from committed inputs. Changes to `release/verifier-requirements.lock` that support a new stable executable belong to the separate promotion lifecycle described in `docs/release-lifecycle.md`.
