# Release execution contract

`lifecycle.release-execution` separates the human-readable authoritative command identity in `contracts/implementation-evidence.json` from the concrete process invocation used by a product-owned release operation.

The contract is artifact-neutral. In product mode, every authoritative implementation-evidence command is bound exactly once to:

- a fixed `argv` array;
- a repository-relative `workingDirectory`;
- the exact repository proof-harness identity declared by the implementation command;
- `harnessArgumentIndex`, whose value is fixed by the inferred invocation form.

Version 2 adds `harnessLocator` and `harnessArgumentIndex`. `harnessLocator` must exactly equal `commands[].execution.harness.locator` on the implementation-evidence command with the same ID. The implementation validator and release-execution validator infer the supported invocation from the exact `commands[].command`/harness-locator pair rather than trusting a separate invocation label.

The accepted invocation forms are deliberately narrow:

- `python <repository-file>` → release argv `['python', <relative-harness>]`, harness index `1`;
- `python -m unittest <python.module>` → release argv `['python', '-m', 'unittest', <relative-module>]`, harness index `3`;
- `./<repository-file>` → release argv `['./<relative-harness>']`, harness index `0`.

For the two Python forms, argv[0] `"python"` is a Composition-managed runtime token. It is part of the portable contract representation and must **not** be resolved through the ambient `PATH`. The managed release-evidence producer resolves that token, after successful release-execution validation, to its own `sys.executable`. Because the producer itself requires Python isolated mode, the validators and the Python proof harness execute under the same selected interpreter/runtime environment without embedding a host-specific absolute executable path in the revision-bound contract. No other argv token is expanded.

`<relative-harness>` is resolved from `workingDirectory` to the same root-relative `harnessLocator` without traversal. For example, these two bindings are equivalent for a `python product/prove.py` implementation command:

```json
{
  "argv": ["python", "product/prove.py"],
  "workingDirectory": ".",
  "harnessLocator": "product/prove.py",
  "harnessArgumentIndex": 1
}
```

```json
{
  "argv": ["python", "prove.py"],
  "workingDirectory": "product",
  "harnessLocator": "product/prove.py",
  "harnessArgumentIndex": 1
}
```

The validator checks the entire argv array, not merely the indexed token. Consequently `['echo', 'product/prove.py']`, `['python', '-c', '...', 'product/prove.py']`, extra arguments, a machine-specific absolute Python executable, or a different interpreter shape cannot satisfy a Python-script harness binding merely because the locator appears somewhere in argv.

The release producer executes only the validated fixed argv after applying the one specified `"python"` runtime-token resolution. `harnessLocator` and `harnessArgumentIndex` are identity constraints, not a second command line. If the real proof needs additional arguments, environment setup, shell behavior, discovery rules, or another opaque launcher, the product should provide a repository-owned wrapper harness and make that wrapper the authoritative implementation command/harness pair.

The contract deliberately does **not** define a shell command language, environment-variable injection, secret lookup, approval policy, or release result. A producer must not parse the human-readable `command` string as shell input and must not perform generic argv or environment expansion. An implementation of this contract that executes a validated Python argv by ordinary PATH lookup instead of resolving the managed `"python"` token to the producer interpreter does not implement the v2 execution semantics.

Template mode is empty. Product mode must exactly cover the command IDs declared by product-mode implementation evidence. `validate_release_execution.py` checks this mode and identity closure, including exact harness-locator equality, supported implementation command/harness inference, invocation-specific exact argv, invocation-specific harness index, working-directory-aware path resolution, and the same absolute/traversal/`.git` path-safety boundary owned structurally by the schema. The semantic mirror is intentional because managed release producers invoke this validator directly before executing fixed argv; unsafe path forms therefore fail closed even when the caller has not independently dispatched JSON Schema validation. Registered-contract schema validation remains the structural authority and additionally constrains document shape and argv values.

## Relationship to proof semantics

`lifecycle.implementation-evidence` owns proof kinds, command execution capabilities, repository harness identity, exact command-to-harness invocation, and negative-path declarations. `lifecycle.release-execution` does not invent or relabel those semantics. It repeats the exact harness identity and binds the invocation inferred from implementation evidence to the only portable fixed argv that release production may execute.

The resulting chain is:

1. a requirement declares a required proof kind;
2. a proof record references an authoritative command;
3. the implementation command declares the required execution capability and repository harness;
4. the exact implementation `command` plus harness locator identifies one supported invocation form;
5. release execution repeats the harness identity and must provide exactly the argv and harness index implied by that invocation from its selected working directory;
6. for Python invocations, the managed producer resolves only the validated argv[0] `"python"` token to its own interpreter; direct harness invocations remain unchanged;
7. release evidence executes that materialized process invocation against one exact candidate revision and records the result.

The declarations cannot prove that a harness implementation is semantically honest. They make label inflation, command/harness contradictions, executable substitutions, and interpreter-environment drift machine-detectable and leave actual execution provenance to the release-evidence layer. The exact candidate revision also binds the release-execution contract itself, so the observed execution result cannot be detached from the fixed argv without changing the candidate revision.

## Candidate verification

The managed helper `.template-composition/release/candidate.py` provides the common exact-candidate boundary used by release producers. It requires a lowercase 40-hex revision that equals repository `HEAD`, rejects replacement refs and staged changes, verifies raw tracked worktree bytes against the candidate blobs without trusting clean/smudge filters, rejects unsupported submodule/Git-link entries, prevents symlink escapes for managed release paths, and rejects untracked non-ignored files.

The same authority is exposed to a materialized consumer as the provider-owned executable action `verify-release-candidate`. Its complete public argv and result schema are declared in `.template-composition/release-execution-actions.json`; the schema fixes that argv so a consumer resolves only `{python}` and `{revision}` and does not reconstruct candidate helper paths or Git arguments. `.template-composition/release/verify_candidate.py` is only a structured adapter around `candidate.py`: it returns `verified` or `failed` while leaving every exact-candidate invariant in the existing helper.

Composition-state may project this action as a `before-release-production` conditional prerequisite only when `lifecycle.release-execution` is selected and implementation evidence is in product mode. This does **not** make Git a prerequisite for Composition inspection, planning, application, ordinary validation, or consumers that did not select revision-bound release execution. A missing or unsuitable Git repository becomes a structured release-candidate failure when the action is applicable; it is not rewritten as a global Composition failure.

Ignored ambient local state is not treated as part of the candidate byte claim. For example, an ignored `.venv/` may exist without changing the asserted Git candidate. The execution contract does not claim a hermetic environment identity; a stronger environment claim requires an explicit future contract rather than implicit dependence on ignored files. The managed Python token identifies the producer interpreter, not a complete environment digest.

## Release lifecycle serialization

The managed helper `.template-composition/release/lifecycle_lock.py` provides one repository-local cooperative lock shared by release-evidence and release-bundle producers. The lock file lives under the repository `.git` directory, not in the candidate worktree. A producer acquires this lock before candidate/evidence snapshot preflight and keeps it through proof or digest work, canonical output validation, and rollback.

On POSIX systems the helper uses an exclusive `flock`; on Windows it uses `msvcrt` byte-range locking behind the same API. The lock file must be a regular non-symbolic file and its opened identity must still match the path identity. OS locks are released when the descriptor closes or the process exits, so a crashed producer does not leave an authoritative stale-lock state.

This lock serializes cooperating Composition release producers. It is not a claim that a hostile process with filesystem or repository-administration privileges cannot alter state; candidate verification and snapshot validation remain the integrity boundary for repository inputs.

Execution results remain the responsibility of `lifecycle.release-evidence`. The release-evidence command digest continues to bind the authoritative command text from implementation evidence; the exact subject revision binds the release-execution document and therefore its fixed argv. The execution contract supplies the portable executable binding that the managed producer can materialize and observe.

Planning implementation evidence has no authoritative proof commands yet, so `release-execution` remains in template mode while implementation evidence is in planning mode. Product implementation evidence requires product release-execution bindings when this lifecycle component is selected.
