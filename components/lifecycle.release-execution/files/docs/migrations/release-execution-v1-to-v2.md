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

The validator requires `harnessLocator` to equal the corresponding implementation-evidence command's `execution.harness.locator` exactly. `harnessArgumentIndex` identifies the argv element that selects the harness. That argument is resolved from `workingDirectory` without traversal and must resolve to the root-relative `harnessLocator`. This prevents a binding from citing the correct harness in metadata while executing an unrelated file, while still supporting a binding such as `workingDirectory: "product"`, `argv: ["python", "prove.py"]`, `harnessLocator: "product/prove.py"`, and `harnessArgumentIndex: 1`.

`argv` remains the only process invocation used by the release producer; the harness fields are identity constraints, not a second command line. The harness must be inside the selected working directory. If the existing command hides the repository proof file inside opaque configuration or shell text, add a small repository-owned wrapper harness and invoke that wrapper at an explicit argv index.

Migration procedure:

1. Change `schemaVersion` from `1` to `2`.
2. For each release-execution command, copy the exact `execution.harness.locator` from the implementation-evidence command with the same ID into `harnessLocator`.
3. Set `harnessArgumentIndex` to the argv position that selects the harness.
4. Ensure that argv element resolves from `workingDirectory` to `harnessLocator` without `..` traversal. If necessary, introduce a repository-owned wrapper under the selected working directory.
5. Re-run Composition validation. Missing, stale, mismatched, out-of-range, or argv-detached harness identities fail closed.

Template mode remains empty. Planning implementation evidence continues to pair with template release execution because planning has no executable proof commands yet.
