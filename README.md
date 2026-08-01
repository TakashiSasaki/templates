# Policy toolkit

This orphan branch is the development source for application-type-independent coding-agent operating policy in `TakashiSasaki/templates`. Its history is intentionally unrelated to the repository's `main`, `site`, and `webapp` branches.

The toolkit compiles shared and repository-specific operating rules into reproducible agent instructions. It governs how coding and general-purpose agents investigate, change, validate, and report work; it does not define the architecture or product requirements of Web applications, command-line tools, libraries, services, or other artifact categories.

The existing Python package and command remain named `agent-policy` for compatibility during repository migration.

## Commands

```bash
agent-policy init
agent-policy validate
agent-policy render
agent-policy check
```

A product repository keeps a single semantic configuration entry point, `.agent-policy.yml`. Project-specific policy text remains in files referenced by that manifest. Generated agent instructions and `.agent-policy.lock` are committed so cloud agents and historical checkouts remain self-contained.

## Bootstrap skill

The onboarding trust seed is maintained at `skills/bootstrap-agent-policy/` in this branch. Its manifest pins one reviewed full commit SHA from `TakashiSasaki/templates`; it does not execute the mutable `policy` branch tip.

Install it from a reviewed checkout:

```bash
python skills/bootstrap-agent-policy/scripts/install.py \
  /path/to/agent-skills/bootstrap-agent-policy
```

The bootstrap script may inspect, initialize, or prepare and preview adoption. It deliberately exposes no adoption-finalization route.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
ruff check src tests scripts skills/bootstrap-agent-policy/scripts
pytest
python -m compileall -q src scripts skills/bootstrap-agent-policy/scripts
agent-policy --help
```

## Branch and migration status

The authoritative development location is `TakashiSasaki/templates` branch `policy`. The branch was imported from `TakashiSasaki/agent-policy` while preserving the non-workflow source history; see `docs/migration-from-agent-policy.md` for the exact source revision and import boundary.

Completed migration work includes:

- branch-appropriate policy CI;
- the application-type-independent policy boundary;
- The former built-in `web-application` profile and its application-architecture rules were removed;
- executable toolchain identity migration to `TakashiSasaki/templates`;
- consolidation of the bootstrap trust seed into `skills/bootstrap-agent-policy/`.

Consumer pin updates, documentation deployment, and deprecation and archival of the former repository remain separate follow-up changes.

## Trust model

Mutable branches are not used as executable toolchain references. Product manifests, generated workflows, adoption state, and bootstrap metadata pin the toolchain using a full Git commit SHA. Bootstrap pin, route, script, or safety-constraint changes are reviewed as trust-anchor changes even though the skill now shares the `policy` history.
