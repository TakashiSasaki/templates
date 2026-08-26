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

The validator requires `harnessLocator` to equal the corresponding implementation-evidence command's `execution.harness.locator` exactly. This field is an identity binding, not a second command line and not an instruction to execute the harness separately. `argv` remains the only process invocation used by the release producer.

Migration procedure:

1. Change `schemaVersion` from `1` to `2`.
2. For each release-execution command, copy the exact `execution.harness.locator` from the implementation-evidence command with the same ID into `harnessLocator`.
3. Keep the existing fixed argv and repository-relative working directory.
4. Re-run Composition validation. Missing, stale, or mismatched harness identities fail closed.

Template mode remains empty. Planning implementation evidence continues to pair with template release execution because planning has no executable proof commands yet.
