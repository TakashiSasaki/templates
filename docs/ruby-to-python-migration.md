# Ruby-to-Python migration

## Scope

This migration removes Ruby from the active heads of the major `site`, `webapp`, `policy`, and `skill` branches without rewriting Git history. The major branches have unrelated histories; cross-branch publication integration therefore remains a separate `site` change after the final reviewed `skill` merge.

A current audit shows executable Ruby only on `skill`. The copyable downstream Skill artifact under `template/` is already Python-only for validation; the remaining Ruby is source-maintainer tooling and selected source-only executable fixtures.

## Completed work

The original validator migration has advanced beyond the initial plan:

1. **PR #115 — publication catalog validation**: replaced the isolated Ruby publication validator with Python.
2. **PR #116 — copyable-validator foundation**: introduced the shared Python parser and initial Python validator ports with parity evidence.
3. **PR #119 — copyable-validator cutover**: merged the downstream validator suite and aggregate entry points as Python-only implementations and switched `template/.github/workflows/validate-skill.yml` to Python.
4. **PR #155 — canonical template ownership**: made `template/` the sole canonical source tree for downstream-distributed Skill content and removed root Python validator projections.

The canonical downstream validation path is therefore no longer part of the remaining Ruby migration. Re-porting those validators would create duplicate authorities and is prohibited by the current source/distribution architecture.

## Remaining Ruby ownership

### Source-maintainer validation and regression harnesses

Ruby remains under `.github/scripts/` for source/distribution checks, clean-room consumption, profile regressions, lifecycle tests, and historical Ruby/Python migration parity. These files are source-only; they are not copied into `template/`.

The structure workflow is the first remaining CI boundary to cut over. During its preparation step, Python counterparts replace the active workflow calls while the Ruby counterparts remain temporarily available as review/parity oracles. They are removed only after the Python path is proven and repository guidance is synchronized.

### Portable core and helper fixtures

Ruby remains in the portable-consumption harnesses and in helper fixtures such as `script-assisted`, `script-assisted-runtime`, and `combined-resources`. These must move to Python while preserving exact byte behavior, path alias rejection, non-mutation, vendoring, archive, and cross-platform evidence.

### Packaged CLI fixture

The packaged CLI fixture still uses Ruby packaging surfaces. Its migration is semantic rather than mechanical: gem/Bundler metadata must be replaced by an equivalent Python package and console-script contract while preserving caller-visible CLI behavior, structured output, exit codes, installation evidence, and failure handling.

### Browser and headless-service fixtures

The browser and headless-service fixtures still contain Ruby implementations and Bundler dependencies. Their migration must preserve the existing network, request-boundary, process-lifecycle, PID-record, file-permission, shutdown, and negative-path invariants rather than matching Ruby implementation details.

### Remaining MCP-related source harnesses

The representative MCP `2026-07-28` and MCP Apps fixture implementations are already Node.js/TypeScript-family code. Remaining Ruby in that area is source-maintainer harness or historical shim code and should be ported or deleted rather than translating the current MCP implementation into Python.

## Revised remaining pull-request plan

The remaining work is organized by ownership and observable behavior rather than by a one-to-one Ruby file translation.

1. **Python source-maintainer structure validation** — port the source/distribution, restructuring, and Pages-boundary checks used by `validate-structure.yml`; switch that workflow to Python-only execution; retain Ruby counterparts temporarily as migration oracles until the cutover is reviewed.
2. **Portable core and helper-fixture cutover** — port reduced helper implementations and the portable consumption/adoption/vendoring/non-mutation/path-safety harnesses; remove Ruby setup from the Ubuntu/macOS/Windows portable-consumption matrix.
3. **Packaged CLI fixture cutover** — replace the Ruby gem/Bundler fixture with a Python package and console script while preserving the existing CLI contracts and executable regression coverage.
4. **Browser-interface fixture cutover** — replace the Ruby Web fixture and its harness with Python while preserving loopback, Host/Origin, request-size, security-header, PID, and shutdown evidence.
5. **Headless-service fixture cutover** — replace the service implementation and lifecycle harness with Python while preserving token/PID descriptor safety, permission, atomic publication, health, concurrency, timeout, and shutdown invariants.
6. **Final Skill Ruby purge and prevention gate** — port or delete remaining Ruby source harnesses and obsolete migration shims; remove Ruby/Bundler setup from all workflows and ignore/dependency surfaces; delete superseded Ruby counterparts; add a repository-wide gate rejecting active `.rb`, Ruby shebangs, Gemfiles, gemspecs, `ruby/setup-ruby`, and Ruby/Bundler execution.
7. **Site publication integration** — after the final Skill merge, update the unrelated `site` provider lock to the final reviewed Skill full SHA and verify complete-tree rendering, copyable-tree rendering, provenance, links, and strict site build.

The browser and headless-service items remain separate because their security and lifecycle invariants are materially different. A split is also permitted if a fixture conversion becomes too large for reliable review.

## Migration method

For each remaining Ruby surface, classify it before editing:

- **obsolete migration oracle or thin shim**: delete it once its evidence is no longer needed;
- **source-maintainer regression harness**: port the behavior to Python and preserve positive and negative cases;
- **fixture implementation**: replace it according to the fixture's runtime/interface contract, not by line-for-line translation;
- **documentation or CI reference**: update it only after the replacement execution path exists.

Do not create source-root copies of canonical validators under `template/.github/scripts/`. The canonical downstream validator authority remains `template/` throughout this migration.

## Acceptance criteria

The migration is complete when:

- no active major-branch file has a `.rb` extension or Ruby shebang;
- no active major-branch file is named `Gemfile`, `Gemfile.lock`, or `*.gemspec`;
- no workflow uses `ruby/setup-ruby`, `ruby`, `gem`, `bundle`, or Bundler caches;
- the copyable `template/` continues to validate with its canonical Python-only validator suite;
- every retained source-maintainer positive and negative invariant has Python evidence;
- portable core consumption still passes on Ubuntu, macOS, and Windows;
- CLI, browser, service, MCP, and lifecycle fixture claims remain executable at their documented boundaries;
- the final no-Ruby prevention gate passes; and
- `site/publication-sources.json` locks the final reviewed Skill SHA and the strict site build succeeds.
