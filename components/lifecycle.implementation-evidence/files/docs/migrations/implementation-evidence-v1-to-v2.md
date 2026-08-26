# implementation-evidence v1 → v2

Version 2 makes explicit product requirements mandatory and separates evidence execution medium from test/inspection kind. It also allows incomplete product evidence to be represented without misreporting it as release-ready.

## Breaking changes

- `schemaVersion` is `2`.
- `requirements` is required at the root. Template mode uses an empty array; product mode requires at least one explicit requirement.
- Requirement IDs may use stable upper- or lower-case identifiers such as `REQ-BROWSER-FILTER`.
- Every proof requires `kind` and `executionClass`.
- `executionClass` is one of `static-inspection`, `process-integration`, `browser-interaction`, or `manual-observation`.
- Proof `status` additionally supports `deferred`.
- `verified` proofs require `locator`, `commandId`, and `expectedResult`.
- `deferred` proofs require `deferredReason`.
- Product documents may contain `required` or `deferred` evidence while remaining structurally valid. Release readiness is a stricter semantic check and rejects every non-verified mandatory boundary or proof.

## Migration

For template mode, set `schemaVersion` to `2` and add `"requirements": []`.

For product mode:

1. enumerate every explicit product requirement in `requirements` and link it to implementation-evidence records with `recordIds`;
2. add `executionClass` to every positive and negative proof based on what actually executed, not what the proof is named;
3. use `static-inspection` for source/markup/JSON inspection, `process-integration` for executable process/HTTP integration, and `browser-interaction` only when a real browser interaction actually ran;
4. mark unavailable mandatory evidence `deferred` with a reason rather than substituting weaker evidence and calling it verified;
5. keep missing planned evidence `required` until it has been executed;
6. run structural validation while implementing, then run the release-readiness check before release production.

Changing `kind` to `end-to-end-test` does not turn static inspection into browser interaction. The two fields describe different dimensions and are validated independently.
