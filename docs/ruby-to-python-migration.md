# Ruby-to-Python migration

## Scope

This migration removes Ruby from the active heads of the major `site`, `webapp`, `policy`, and `skill` branches without rewriting Git history. The major branches have unrelated histories; cross-branch publication integration remains a separate `site` change after the final reviewed `skill` merge.

The copyable downstream Skill artifact under `template/` is already Python-only. At the current stacked `skill` migration stage, the portable core, packaged CLI, browser-interface, and headless-service runtime paths have also been converted to Python. Remaining Ruby ownership is limited to source-maintainer validation/parity shims and MCP-related harnesses scheduled for the final purge PR.

## Completed work

1. **PR #115 — publication catalog validation**: replaced the isolated Ruby publication validator with Python.
2. **PR #116 — copyable-validator foundation**: introduced the shared Python parser and initial Python validator ports with parity evidence.
3. **PR #119 — copyable-validator cutover**: made the downstream validator suite and aggregate entry points Python-only and switched `template/.github/workflows/validate-skill.yml` to Python.
4. **PR #155 — canonical template ownership**: made `template/` the sole canonical source tree for downstream-distributed Skill content and removed root Python validator projections.
5. **PR #166 — source-maintainer structure validation**: cut the structure-validation workflow over to Python source-maintainer tooling.
6. **PR #167 — portable core and helper fixtures**: converted reduced helper fixtures and portable adoption/vendoring/non-mutation/path-safety harnesses to Python and removed Ruby from the portable matrix.
7. **PR #168 — packaged CLI fixture**: replaced Ruby gem/Bundler packaging with a CPython package and `text-stat` console script while retaining the public CLI contract and offline wheel-installation evidence.
8. **PR #169 — browser-interface fixture**: replaced the WEBrick/Bundler browser fixture with a CPython standard-library loopback server while retaining Host/Origin, request-size, security-header, PID, and shutdown evidence.
9. **PR #170 — headless-service fixture**: replaced the WEBrick/Bundler headless service with a CPython standard-library implementation while retaining token/PID descriptor safety, atomic PID publication, bounded HTTP input, health, concurrency, timeout, and shutdown evidence.

The canonical downstream validator authority remains `template/.github/scripts/`; source-root copies must not be introduced.

## Remaining Ruby ownership

### Source-maintainer validation and historical migration oracles

Any Ruby still under `.github/scripts/` after the fixture cutovers is source-only maintainer tooling or a temporary migration/parity oracle. It is not copied into `template/`. The final purge stage must either port the retained invariant to Python or delete the obsolete oracle after equivalent Python evidence exists.

### MCP-related source harnesses

The representative MCP `2026-07-28` and MCP Apps fixture implementations are already Node.js/ESM code. Their remaining Ruby is source-maintainer harness or historical shim code; the implementation itself is not being translated to Python. The final migration PR replaces those harnesses with Python orchestration around the existing Node fixtures.

## Remaining pull-request plan

1. **Final Skill Ruby purge and prevention gate** — port or delete the remaining source-maintainer Ruby harnesses and obsolete parity shims; remove Ruby/Bundler setup from every active workflow and ignore/dependency surface; synchronize generated repository policy; and add a repository-wide gate rejecting active `.rb`, Ruby shebangs, Gemfiles, gemspecs, `ruby/setup-ruby`, and Ruby/Bundler execution.
2. **Site publication integration** — after the final Skill merge, update the unrelated `site` provider lock to the final reviewed Skill full SHA and verify complete-tree rendering, copyable-tree rendering, provenance, links, and the strict site build.

## Migration method

For each remaining Ruby surface, classify it before editing:

- **obsolete migration oracle or thin shim**: delete it once equivalent Python evidence is established;
- **source-maintainer regression harness**: port the observable positive and negative invariants to Python;
- **documentation or CI reference**: update it only after the replacement execution path exists.

Fixture runtime migration is no longer remaining work for portable core, packaged CLI, browser-interface, or headless-service. Later changes to those fixtures should be ordinary contract-preserving maintenance rather than Ruby-to-Python migration work.

## Acceptance criteria

The migration is complete when:

- no active major-branch file has a `.rb` extension or Ruby shebang;
- no active major-branch file is named `Gemfile`, `Gemfile.lock`, or `*.gemspec`;
- no workflow uses `ruby/setup-ruby`, `ruby`, `gem`, `bundle`, or Bundler caches;
- the copyable `template/` continues to validate with its canonical Python-only validator suite;
- every retained source-maintainer positive and negative invariant has Python evidence;
- portable core consumption passes on Ubuntu, macOS, and Windows;
- CLI, browser, service, MCP, and lifecycle fixture claims remain executable at their documented boundaries;
- the final no-Ruby prevention gate passes; and
- `site/publication-sources.json` locks the final reviewed Skill SHA and the strict site build succeeds.
