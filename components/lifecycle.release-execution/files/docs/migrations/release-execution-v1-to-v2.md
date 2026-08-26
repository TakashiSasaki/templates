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

In the two Python forms, argv[0] `"python"` is a Composition-managed runtime token. Keep that literal portable token in the contract; do not replace it with `/usr/bin/python`, a virtual-environment absolute path, `sys.executable`, `py`, or another host-specific executable. After successful validation, the managed release-evidence producer resolves only this validated argv[0] token to its own `sys.executable`, so the Python proof runs under the same selected interpreter/runtime used by the producer and its validators rather than an unrelated PATH-resolved interpreter.

The entire argv must match. Merely placing the harness locator at an indexed position is insufficient. For example, `['echo', 'tests/test_browser.py']` and `['python', '-c', '...', 'tests/test_browser.py']` are rejected even though the declared locator appears in argv. An absolute Python executable is also rejected because the portable v2 contract records the managed `"python"` token instead. This closes both the harness-substitution gap and host-specific interpreter binding.

The harness must resolve from `workingDirectory` without traversal. A root-relative locator `product/prove.py` may therefore use either `workingDirectory: "."` with `argv: ["python", "product/prove.py"]` or `workingDirectory: "product"` with `argv: ["python", "prove.py"]` when the implementation command establishes the `python-script` form.

`argv` remains the only process invocation authority used by the release producer; the managed Python token has the single defined resolution above. The harness fields are identity constraints, not a second command line. If the real command requires additional arguments, environment setup, shell behavior, discovery rules, or another opaque launcher, add a repository-owned wrapper harness and use that wrapper as the implementation command/harness authority before creating the release binding.

Migration procedure:

1. Change `schemaVersion` from `1` to `2`.
2. Ensure the corresponding `implementation-evidence` command has already migrated to v6 with a safe repository harness and one supported exact command/harness invocation.
3. Copy the exact `execution.harness.locator` into `harnessLocator`.
4. Choose a safe repository-relative `workingDirectory` that contains the harness without `..` traversal.
5. Set `argv` to the exact invocation implied by the implementation command/harness pair from that working directory. For either Python form, use the literal `"python"` managed token at argv[0], never a host-specific executable path.
6. Set `harnessArgumentIndex` to the invocation-defined index: `1` for Python script, `3` for Python unittest module, or `0` for direct execution.
7. Re-run Composition validation and release acceptance. Unsafe or mismatched paths, unsupported implementation command/harness pairs, stale harness identities, altered/extra argv elements, wrong invocation shape, host-specific Python executable substitutions, or wrong harness indexes fail closed.

Template mode remains empty. Planning implementation evidence continues to pair with template release execution because planning has no executable proof commands yet.
