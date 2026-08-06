# Ruby-to-Python migration

## Scope

This migration removes Ruby from the active heads of the major `site`, `webapp`, `policy`, and `skill` branches. Git history is immutable for this work and is not rewritten. The `site` branch may continue to render older locked Skill trees until its publication lock is updated in a separate pull request because `site` and `skill` have unrelated histories.

The live audit at Skill commit `267eae033bd411c70209d098f11c3e0fdcdc6b23` found executable Ruby only on the `skill` branch. `site`, `webapp`, and `policy` do not use Ruby in their own build or validation toolchains.

## Complete active Ruby inventory

### Maintainer validation toolchain

All Ruby files below `.github/scripts/` are active maintainer validators, regression tests, or their shared library:

- `.github/scripts/lib/profile_contracts.rb`;
- `.github/scripts/validate-*.rb`;
- `.github/scripts/test-*.rb`.

This includes the profile-contract validators, distribution and adoption checks, publication checks, interface checks, MCP checks, Pages-boundary checks, and fixture test drivers.

### Copyable template validation toolchain

Ruby is copied into downstream Skill repositories through:

- `template/.github/scripts/lib/profile_contracts.rb`;
- `template/.github/scripts/validate-*.rb`;
- `template/.github/scripts/test-template-baseline.rb`;
- `template/.github/workflows/validate-skill.yml`.

These files create a Ruby 3.1 runtime requirement even when a generated Skill is implemented in another language.

### Ruby fixture implementations

Ruby source, tests, launchers, or packaging metadata occur in these fixture families:

- `.github/fixtures/profiles/browser-interface/`;
- `.github/fixtures/profiles/cli-mcp-combined/`;
- `.github/fixtures/profiles/combined-resources/scripts/normalize.rb`;
- `.github/fixtures/profiles/headless-service/`;
- `.github/fixtures/profiles/mcp-enabled/`;
- `.github/fixtures/profiles/mcp-systemd-service/`;
- `.github/fixtures/profiles/packaged-cli/`;
- `.github/fixtures/profiles/script-assisted/scripts/normalize.rb`;
- `.github/fixtures/profiles/script-assisted-runtime/`.

The fixture dependency and package surfaces include `Gemfile`, `Gemfile.lock`, `*.gemspec`, Bundler commands, Ruby shebangs, and extensionless Ruby launchers such as `bin/text-stat`.

### CI runtime and dependency setup

Ruby is installed or invoked by:

- `.github/workflows/validate-structure.yml`;
- `.github/workflows/validate-extended-profile-contracts.yml`;
- `.github/workflows/validate-portable-consumption.yml`;
- `template/.github/workflows/validate-skill.yml`.

The workflows use `ruby/setup-ruby`, `ruby`, `gem install bundler`, `bundle install`, and `bundle exec`.

### Contracts, manifests, and documentation

Ruby paths or commands are encoded in:

- `distribution-manifest.json`, which mirrors Ruby validators into `template/`;
- `.gitignore`, for Bundler and Ruby-generated state;
- `docs/publication-maintenance.md` and other root maintenance guidance;
- profile-specific `SKILL.md`, `RUNTIME.md`, interface documents, MCP documents, and fixture READMEs;
- tests that assert exact `.rb`, Gemfile, gemspec, Bundler, or `ruby` command surfaces.

The `site` branch can display these files and commands in generated repository-tree pages and inline previews. Those are publication mirrors rather than Ruby execution, but they must be refreshed after the final `skill` merge by updating `site/publication-sources.json` to the reviewed full SHA.

## Python feasibility

The migration is feasible without changing the contracts that the repository validates.

| Ruby responsibility | Python replacement | Feasibility |
| --- | --- | --- |
| JSON validation, safe paths, UTF-8 checks | `json`, `pathlib`, `stat` | Direct |
| Markdown and profile parsing | Python parser preserving current line and table semantics | Direct, parity tests required |
| YAML frontmatter | `PyYAML` with safe loading and aliases disabled | Direct with one pinned dependency |
| Filesystem snapshots and symlink rejection | `pathlib`, `os`, `stat` | Direct |
| Subprocess, temporary Git index, lifecycle tests | `subprocess`, `tempfile`, `os.environ` | Direct |
| HTTP server/client fixtures | `http.server`, `urllib`, or a small pinned framework | Direct; preserve protocol boundaries |
| MCP JSON-RPC fixtures | Python JSON/HTTP/stdio implementation | Direct; protocol parity tests required |
| systemd unit rendering and smoke tests | Python renderer and client | Direct |
| Ruby gem package fixture | Python package with `pyproject.toml` and console script | Semantic replacement, not a mechanical port |
| Bundler and Gemfile surfaces | `venv`/pip with locked requirements or standard-library-only fixtures | Direct |

The principal risk is behavioral drift in the shared profile parser and in MCP/service lifecycle fixtures. Each replacement therefore requires positive and negative parity tests before deleting its Ruby predecessor.

## Pull-request plan

The migration is now estimated at nine reviewable pull requests. The original eight-PR estimate remains within its stated eight-to-ten range, but implementation of the copyable validator layer showed that its shared parser, parallel parity harness, and full validator cutover should not be reviewed as one oversized change.

1. **Python publication catalog validation — merged as PR #115** — replace the isolated catalog validator and its regression tests; establish the migration record. Merge commit: `8583a735a044c7618d695a0b8cd1923bbdfd3bc1`.
2. **Python copyable-validator foundation — PR #116** — add and mirror the shared Python parser, safe YAML policy, Python template-baseline audit, initial validator ports, and Ruby/Python parity harnesses while retaining the Ruby implementations.
3. **Python copyable-validator cutover** — port the remaining validators shipped under `template/.github/scripts/`, complete positive and negative parity coverage, switch the downstream workflow to Python, replace Ruby projections in `distribution-manifest.json`, and remove the superseded distributed Ruby implementations.
4. **Python maintainer validators** — port root contract, distribution, adoption, publication, and interface test drivers; remove duplicated Ruby validator sources.
5. **Python script and packaged-CLI fixtures** — replace normalize scripts, Ruby gems, gemspecs, Bundler files, launchers, and CLI/MCP combined fixtures with Python packages and tests.
6. **Python browser and headless-service fixtures** — replace HTTP servers, PID lifecycle implementations, tests, and runtime contracts.
7. **Python MCP and systemd fixtures** — replace MCP client/server/service-manager code, HTTP transports, unit rendering, smoke clients, and dependency setup.
8. **Skill Ruby purge and prevention gate** — remove remaining Ruby files, Ruby/Bundler references and ignore rules; remove `ruby/setup-ruby`; add a Python regression check rejecting active `.rb`, Gemfile, gemspec, `ruby`, `bundle`, and `ruby/setup-ruby` surfaces outside an explicitly empty allowlist.
9. **Site publication integration** — after the final Skill merge, update the unrelated `site` branch lock to the final full SHA and verify complete-tree, copyable-tree, preview, build, provenance, and link validation.

Large fixture findings may still justify splitting items 6 or 7, so the realistic range remains nine to ten pull requests. PR boundaries must remain within one unrelated branch history; no merge, rebase, or cherry-pick is permitted between `skill` and `site`.

## Acceptance criteria

The migration is complete when:

- no active major-branch file has a `.rb` extension or Ruby shebang;
- no active major-branch file is named `Gemfile`, `Gemfile.lock`, or `*.gemspec`;
- no workflow uses `ruby/setup-ruby`, `ruby`, `gem`, `bundle`, or Bundler caches;
- the copyable `template/` validates with Python only;
- all existing positive and negative contract cases have Python equivalents;
- service, MCP, CLI, browser, and systemd fixture behavior remains covered;
- the final no-Ruby prevention gate passes; and
- `site/publication-sources.json` locks the final reviewed Skill SHA and the strict site build succeeds.
