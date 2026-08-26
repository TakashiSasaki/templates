# Release execution v1 → v2

Version 2 closes the identity gap between the repository proof harness declared by `implementation-evidence` v6 and the fixed argv binding executed by the release lifecycle.

Each product command now requires `harnessLocator`:

```json
{
  "commandId": "verify-browser",
  "argv": ["python", "tests/test_browser.py"],
  "workingDirectory": ".",
  "harnessLocator": "tests/test_browser.py"
}
```

The validator requires `harnessLocator` to equal the corresponding implementation-evidence command's `execution.harness.locator` exactly. It also requires the fixed `argv` array to contain that locator as one exact argument. This prevents a binding from citing the correct harness in metadata while executing an unrelated file. `argv` remains the only process invocation used by the release producer; `harnessLocator` is an identity constraint, not a second command line.

If the existing command invokes a framework in a way that does not expose the repository harness path as an argv token, add a small repository-owned wrapper harness and invoke that wrapper explicitly. Do not hide the selected harness in shell text or opaque configuration solely to satisfy the migration.

Migration procedure:

1. Change `schemaVersion` from `1` to `2`.
2. For each release-execution command, copy the exact `execution.harness.locator` from the implementation-evidence command with the same ID into `harnessLocator`.
3. Ensure the same locator appears verbatim as one element of `argv` while preserving a repository-relative `workingDirectory`.
4. If necessary, introduce a repository-owned wrapper so the harness identity can be an explicit argv token.
5. Re-run Composition validation. Missing, stale, mismatched, or argv-detached harness identities fail closed.

Template mode remains empty. Planning implementation evidence continues to pair with template release execution because planning has no executable proof commands yet.
