# Implementation evidence v5 → v6

Version 6 makes executable proof semantics machine-checkable instead of relying on `evidenceProof.kind` labels alone.

## Breaking change

Every product-mode entry in `commands` now requires an `execution` object:

```json
{
  "id": "verify-browser",
  "command": "python tests/test_browser.py",
  "purpose": "Exercise the browser product path.",
  "execution": {
    "capabilities": ["end-to-end", "browser"],
    "harness": {
      "kind": "repository-file",
      "locator": "tests/test_browser.py"
    },
    "supportsNegativePath": true
  }
}
```

`capabilities` declares the execution surfaces the command actually owns. Allowed values are `unit`, `integration`, `end-to-end`, `browser`, `accessibility`, `migration`, `inspection`, and `other`. The harness must be a safe repository-relative regular non-symlink file. A symbolic link is rejected even when tracked by Git because its execution target can resolve outside the repository-owned harness path. `supportsNegativePath` must be true for a command used by `negativeEvidence`.

Proof kinds now require a corresponding command capability:

| Proof kind | Required command capability |
| --- | --- |
| `unit-test` | `unit` |
| `integration-test` | `integration` |
| `end-to-end-test` | `end-to-end` |
| `accessibility-test` | `accessibility` |
| `migration-test` | `migration` |
| `inspection` | `inspection` |
| `other` | `other` |

A proof may therefore no longer be upgraded merely by changing its `kind` string. For example, an integration/static command cannot satisfy an `end-to-end-test` proof unless its authoritative command profile also declares the `end-to-end` capability.

Artifact validators may impose stronger requirements. In particular, browser-sensitive Webapp targets require the proof command to declare `browser` in addition to an accepted proof kind. Thus `end-to-end-test` remains a proof scope, not a synonym for browser execution.

## Command-to-harness invocation is derived

The harness locator is not descriptive metadata. The semantic validator derives the executable invocation from the exact pair of `commands[].command` and `commands[].execution.harness.locator`. There is deliberately no separate invocation label to assert.

Exactly these command forms are accepted:

- `python <repository-file>`;
- `python -m unittest <python.module>` when `<python.module>` is the module form of the declared `.py` harness locator;
- `./<repository-file>`.

For example, a harness locator `tests/test_browser.py` may be paired with either `python tests/test_browser.py` or `python -m unittest tests.test_browser`, depending on which invocation the harness actually owns. `echo tests/test_browser.py`, `python -c ... tests/test_browser.py`, or an opaque shell command that merely mentions the locator is rejected because it does not prove that the declared harness is the executable authority.

If the real proof needs arguments, environment setup, discovery rules, shell behavior, or another opaque launcher, add a small repository-owned wrapper harness and make the wrapper itself the exact `command`/`harness.locator` authority. This keeps invocation identity machine-checkable instead of trusting prose or free-form metadata.

## Migration procedure

1. Change `schemaVersion` from `5` to `6`.
2. For every product command, identify the repository-owned regular file that actually implements or launches the proof and set it as `execution.harness.locator`; do not use a symlink, absolute path, traversal, `.git` path, drive-prefixed path, or backslash form.
3. Rewrite `commands[].command` if necessary so it exactly matches one supported invocation form for that locator. Use a repository wrapper harness when the existing command is otherwise opaque.
4. Declare only execution capabilities that the harness actually exercises.
5. Set `supportsNegativePath` to `true` only when the same authoritative command executes the claimed negative path; otherwise use a separate command for negative evidence or do not claim that negative proof.
6. If `lifecycle.release-execution` is selected, migrate it to v2 and bind its fixed argv to the invocation inferred from this exact command/harness pair.
7. Re-run the selected Composition validators. Unsafe or missing harnesses, unsupported command/harness pairs, proof-kind/capability mismatches, negative proofs bound to positive-only commands, and release argv substitutions fail closed.

Planning mode remains unchanged because commands do not yet exist there. Template mode remains empty.

## Deferred evidence

`deferred` proofs remain representable when the required environment is unavailable, but the command profile must still describe the intended execution surface and exact repository harness truthfully. Release readiness continues to reject every deferred proof. Do not weaken the command capability, change a browser proof into static inspection, or substitute a non-executing command merely to obtain a green structural validation result.
