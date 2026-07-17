# agent-policy

`agent-policy` is a policy compiler and repository bootstrap tool for sharing agent rules across multiple products and multiple coding or general-purpose agents.

The repository has two unrelated long-lived branches:

- `main`: policy sources, compiler, schemas, renderers, normal-operation skills, tests, and GitHub Action integration.
- `bootstrap-agent-policy`: a directly cloneable agent skill whose root contains `SKILL.md`; it invokes a pinned commit from `main` to initialize an unmanaged repository.

## Initial scope

The first implementation provides four commands:

```bash
agent-policy init
agent-policy validate
agent-policy render
agent-policy check
```

A product repository keeps a single semantic configuration entry point, `.agent-policy.yml`. Project-specific policy text remains in files referenced by that manifest. Generated agent instructions and `.agent-policy.lock` are committed so cloud agents and historical checkouts remain self-contained.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
pytest
agent-policy --help
```

## Trust model

Mutable branches are not used as executable toolchain references. Product manifests, generated workflows, and the bootstrap manifest pin the toolchain using a full Git commit SHA. Bootstrap updates and ordinary policy updates are reviewed independently.
