# Ruby-to-Python migration

## Scope

This migration removes Ruby from the active heads of the major `site`, `webapp`, `policy`, and `skill` branches without rewriting Git history. The major branches have unrelated histories; cross-branch publication integration remains a separate `site` change after the final reviewed `skill` merge.

The copyable downstream Skill artifact under `template/` is Python-only. The portable core, packaged CLI, browser-interface, headless-service runtime paths, source-maintainer validation path, and MCP source harnesses have now also been converted to Python or retired where they existed only as migration oracles. No active Ruby runtime/tooling remains in the final Skill migration head.

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
10. **PR #171 — final Skill Ruby purge and prevention gate**: replaced the remaining MCP source harnesses with Python orchestration, retired obsolete Ruby/Python parity oracles, removed all remaining tracked Ruby maintainer files, synchronized generated repository policy, and enabled a repository-wide no-Ruby prevention gate.

The canonical downstream validator authority remains `template/.github/scripts/`; source-root copies must not be introduced.

## Final Skill migration state

The final Skill migration head contains no tracked `.rb` files, Gemfiles, gemspecs, or Ruby/Bundler execution path. Historical Ruby/Python parity scripts that depended on the retired Ruby validators have been removed rather than retained as dead tooling. The representative MCP `2026-07-28` and MCP Apps implementations remain Node.js/ESM by design; their source-maintainer orchestration is Python and does not require Ruby.

The repository-wide prevention gate rejects reintroduction of active Ruby artifacts or workflow/runtime dependencies. Historical discussion of the migration in documentation is not itself prohibited.

## Remaining work

Only cross-branch publication integration remains:

1. **Site publication integration** — after PR #171 merges to `skill`, update the unrelated `site` provider lock to the final reviewed Skill full SHA and verify complete-tree rendering, copyable-tree rendering, provenance, links, and the strict site build.

Because `site` and `skill` have unrelated histories, this work remains a separate reviewed `site` pull request and must not be folded into PR #171.

## Migration method retained as maintenance guidance

The migration used the following classification before editing each Ruby surface:

- **obsolete migration oracle or thin shim**: delete it once equivalent Python evidence is established;
- **source-maintainer regression harness**: port the observable positive and negative invariants to Python;
- **documentation or CI reference**: update it only after the replacement execution path exists.

Future changes to the portable core, packaged CLI, browser-interface, headless-service, and MCP fixtures are ordinary contract-preserving maintenance rather than Ruby-to-Python migration work.

## Acceptance criteria

The Skill-side migration is complete when:

- no active `skill` file has a `.rb` extension or Ruby shebang;
- no active `skill` file is named `Gemfile`, `Gemfile.lock`, or `*.gemspec`;
- no `skill` workflow uses `ruby/setup-ruby`, `ruby`, `gem`, `bundle`, or Bundler caches;
- the copyable `template/` continues to validate with its canonical Python-only validator suite;
- every retained source-maintainer positive and negative invariant has Python evidence;
- portable core consumption passes on Ubuntu, macOS, and Windows;
- CLI, browser, service, MCP, and lifecycle fixture claims remain executable at their documented boundaries; and
- the final no-Ruby prevention gate passes.

The overall cross-branch migration closes when `site/publication-sources.json` locks the final reviewed Skill SHA and the strict site build succeeds.
