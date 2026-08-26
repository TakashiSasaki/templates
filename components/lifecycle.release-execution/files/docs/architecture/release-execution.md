# Release execution contract

`lifecycle.release-execution` separates the human-readable authoritative command identity in `contracts/implementation-evidence.json` from the concrete process invocation used by a product-owned release operation.

The contract is artifact-neutral. In product mode, every authoritative implementation-evidence command is bound exactly once to:

- a fixed `argv` array;
- a repository-relative `workingDirectory`;
- the exact repository proof-harness identity declared by the implementation command;
- `harnessArgumentIndex`, identifying which argv element selects that harness.

Version 2 adds `harnessLocator` and `harnessArgumentIndex`. `harnessLocator` must exactly equal `commands[].execution.harness.locator` on the implementation-evidence command with the same ID. The indexed argv element is resolved from `workingDirectory` without traversal and must resolve to that root-relative locator. This makes the harness identity part of the actual process selection rather than detached metadata while allowing non-root working directories.

For example, both of these bindings select the same repository harness:

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

The release producer still executes only the fixed argv. `harnessLocator` and `harnessArgumentIndex` are identity constraints, not a second command line. The declared harness must lie inside the selected working directory, so no `..` traversal is required to reach it. If a tool normally hides the selected proof file inside opaque configuration or shell text, the product should provide a repository-owned wrapper harness and put that wrapper explicitly at the declared argv index.

The contract deliberately does **not** define a shell command language, environment-variable injection, secret lookup, approval policy, or release result. A producer must execute the declared argv directly rather than parsing the human-readable `command` string as shell input.

Template mode is empty. Product mode must exactly cover the command IDs declared by product-mode implementation evidence. `validate_release_execution.py` checks this mode and identity closure, including exact harness-locator equality, a valid harness argv index, working-directory-aware path resolution, and the same absolute/traversal/`.git` path-safety boundary owned structurally by the schema. The semantic mirror is intentional because managed release producers invoke this validator directly before executing fixed argv; unsafe path forms therefore fail closed even when the caller has not independently dispatched JSON Schema validation. Registered-contract schema validation remains the structural authority and additionally constrains document shape and argv values.

## Relationship to proof semantics

`lifecycle.implementation-evidence` owns proof kinds, command execution capabilities, repository harness identity, and negative-path declarations. `lifecycle.release-execution` does not reinterpret those semantics. It binds that authoritative command/harness identity to the fixed argv that release production can execute.

The resulting chain is:

1. a requirement declares a required proof kind;
2. a proof record references an authoritative command;
3. the implementation command declares the required execution capability and repository harness;
4. release execution repeats the exact harness identity and identifies the argv element that resolves to it from the declared working directory;
5. release evidence executes that argv against one exact candidate revision and records the result.

The declarations cannot prove that a harness implementation is semantically honest. They make contradictions and substitutions machine-detectable and leave actual execution provenance to the release-evidence layer. The exact candidate revision also binds the release-execution contract itself, so the observed execution result cannot be detached from the fixed argv without changing the candidate revision.

## Candidate verification

The managed helper `.template-composition/release/candidate.py` provides the common exact-candidate boundary used by release producers. It requires a lowercase 40-hex revision that equals repository `HEAD`, rejects replacement refs and staged changes, verifies raw tracked worktree bytes against the candidate blobs without trusting clean/smudge filters, rejects unsupported submodule/Git-link entries, prevents symlink escapes for managed release paths, and rejects untracked non-ignored files.

Ignored ambient local state is not treated as part of the candidate byte claim. For example, an ignored `.venv/` may exist without changing the asserted Git candidate. The execution contract does not claim a hermetic environment identity; a stronger environment claim requires an explicit future contract rather than implicit dependence on ignored files.

## Release lifecycle serialization

The managed helper `.template-composition/release/lifecycle_lock.py` provides one repository-local cooperative lock shared by release-evidence and release-bundle producers. The lock file lives under the repository `.git` directory, not in the candidate worktree. A producer acquires this lock before candidate/evidence snapshot preflight and keeps it through proof or digest work, canonical output validation, and rollback.

On POSIX systems the helper uses an exclusive `flock`; on Windows it uses `msvcrt` byte-range locking behind the same API. The lock file must be a regular non-symbolic file and its opened identity must still match the path identity. OS locks are released when the descriptor closes or the process exits, so a crashed producer does not leave an authoritative stale-lock state.

This lock serializes cooperating Composition release producers. It is not a claim that a hostile process with filesystem or repository-administration privileges cannot alter state; candidate verification and snapshot validation remain the integrity boundary for repository inputs.

Execution results remain the responsibility of `lifecycle.release-evidence`. The release-evidence command digest continues to bind the authoritative command text from implementation evidence; the exact subject revision binds the release-execution document and therefore its fixed argv. The execution contract supplies the executable binding that the managed producer can run and observe.

Planning implementation evidence has no authoritative proof commands yet, so `release-execution` remains in template mode while implementation evidence is in planning mode. Product implementation evidence requires product release-execution bindings when this lifecycle component is selected.
