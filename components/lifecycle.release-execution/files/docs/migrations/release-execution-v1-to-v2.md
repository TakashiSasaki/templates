# Release execution v1 → v2

Version 2 closes the identity gap between the repository proof harness declared by `implementation-evidence` v6 and the fixed argv binding executed by the release lifecycle.

Each product command now requires `harnessLocator` and `harnessArgumentIndex`:

```json
{
  "commandId": "verify-browser",
  "argv": ["python", "tests/test_browser.py"],
  "workingDirectory": ".",
  "harnessLocator": "tests/test_browser.py",
  "harnessArgumentIndex": 1
}
```

The validator first requires `harnessLocator` to equal the corresponding implementation-evidence command's `execution.harness.locator` exactly. It then infers the executable invocation from the exact implementation `command` text plus that locator. There is no independent invocation label to trust.

Supported implementation command forms are:

- `python <repository-file>`;
- `python -m unittest <python.module>` for the module form of the declared `.py` harness;
- `./<repository-file>`.

For the selected `workingDirectory`, the release binding must use the complete argv and `harnessArgumentIndex` implied by that inferred invocation:

- Python script: `['python', <relative-harness>]`, index `1`;
- Python unittest: `['python', '-m', 'unittest', <relative-module>]`, index `3`;
- direct repository harness: `['./<relative-harness>']`, index `0`.

The entire argv must match. Merely placing the harness locator at an indexed position is insufficient. For example, `['echo', 'tests/test_browser.py']` and `['python', '-c', '...', 'tests/test_browser.py']` are rejected even though the declared locator appears in argv. This closes the substitution gap where a release binding could name the intended harness without actually executing it.

The harness must resolve from `workingDirectory` without traversal. A root-relative locator `product/prove.py` may therefore use either `workingDirectory: "."` with `argv: ["python", "product/prove.py"]` or `workingDirectory: "product"` with `argv: ["python", "prove.py"]` when the implementation command establishes the `python-script` form.

`argv` remains the only process invocation used by the release producer; the harness fields are identity constraints, not a second command line. If the real command requires additional arguments, environment setup, shell behavior, discovery rules, or another opaque launcher, add a repository-owned wrapper harness and use that wrapper as the implementation command/harness authority before creating the release binding.

Migration procedure:

1. Change `schemaVersion` from `1` to `2`.
2. Ensure the corresponding `implementation-evidence` command has already migrated to v6 with a safe repository harness and one supported exact command/harness invocation.
3. Copy the exact `execution.harness.locator` into `harnessLocator`.
4. Choose a safe repository-relative `workingDirectory` that contains the harness without `..` traversal.
5. Set `argv` to the exact invocation implied by the implementation command/harness pair from that working directory.
6. Set `harnessArgumentIndex` to the invocation-defined index: `1` for Python script, `3` for Python unittest module, or `0` for direct execution.
7. Re-run Composition validation. Unsafe or mismatched paths, unsupported implementation command/harness pairs, stale harness identities, altered/extra argv elements, wrong invocation shape, or wrong harness indexes fail closed.

Template mode remains empty. Planning implementation evidence continues to pair with template release execution because planning has no executable proof commands yet.
