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

`capabilities` declares the execution surfaces the command actually owns. Allowed values are `unit`, `integration`, `end-to-end`, `browser`, `accessibility`, `migration`, `inspection`, and `other`. The harness must be a repository-relative file. `supportsNegativePath` must be true for a command used by `negativeEvidence`.

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

## Migration procedure

1. Change `schemaVersion` from `5` to `6`.
2. For every product command, identify the repository file that actually implements or launches the proof and set it as `execution.harness.locator`.
3. Declare only execution capabilities that the harness actually exercises.
4. Set `supportsNegativePath` to `true` only when the same authoritative command executes the claimed negative path; otherwise use a separate command for negative evidence or do not claim that negative proof.
5. Re-run the selected Composition validators. Missing harness files, proof-kind/capability mismatches, and negative proofs bound to positive-only commands fail closed.

Planning mode remains unchanged because commands do not yet exist there. Template mode remains empty.

## Deferred evidence

`deferred` proofs remain representable when the required environment is unavailable, but the command profile must still describe the intended execution surface correctly. Release readiness continues to reject every deferred proof. Do not weaken the command capability or change a browser proof into static inspection merely to obtain a green structural validation result.
