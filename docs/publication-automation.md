# Asynchronous publication operations

[Publishing](../PUBLISHING.md) is the current runbook. The previous controller, Shadow
mode, promotion/adoption PRs, trusted-policy/controller pins, callbacks and receipt gates
are retired. Do not restore them to process a new provider document or a Site change.

`Refresh publication` -> successful Integration artifact -> `Deploy documentation from site`.
Integration pushes can also produce artifacts; Site pushes can rebuild an existing artifact.
Each stage reports its own failure. There is no reciprocal source edit or release barrier.

Use GitHub Actions run IDs and each artifact's `bundle.json` / Site `build-provenance.json`
for diagnostics. Failed refresh: fix Integration/provider input and refresh. Failed Site
build: fix Site against the same Bundle. Failed Pages deployment: rerun deployment using
the available successful publication. Do not change another authority to manufacture a pin.
