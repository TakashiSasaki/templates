# Release execution contract

`lifecycle.release-execution` separates the human-readable authoritative command identity in `contracts/implementation-evidence.json` from the concrete process invocation used by a product-owned release operation.

The contract is artifact-neutral. In product mode, every authoritative implementation-evidence command is bound exactly once to:

- a fixed `argv` array;
- a repository-relative `workingDirectory`.

The contract deliberately does **not** define a shell command language, environment-variable injection, secret lookup, approval policy, or release result. A producer must execute the declared argv directly rather than parsing the human-readable `command` string as shell input.

Template mode is empty. Product mode must exactly cover the command IDs declared by product-mode implementation evidence. `validate_release_execution.py` checks this mode and identity closure. Schema validation additionally constrains argv values and rejects unsafe working-directory forms such as absolute paths, traversal segments, and `.git` paths.

## Candidate verification

The managed helper `.template-composition/release/candidate.py` provides the common exact-candidate boundary used by release producers. It requires a lowercase 40-hex revision that equals repository `HEAD`, rejects replacement refs and staged changes, verifies raw tracked worktree bytes against the candidate blobs without trusting clean/smudge filters, rejects unsupported submodule/Git-link entries, prevents symlink escapes for managed release paths, and rejects untracked non-ignored files.

Ignored ambient local state is not treated as part of the candidate byte claim. For example, an ignored `.venv/` may exist without changing the asserted Git candidate. The v1 execution contract also does not claim a hermetic environment identity; a stronger environment claim requires an explicit future contract rather than implicit dependence on ignored files.

Execution results remain the responsibility of `lifecycle.release-evidence`. The release-evidence command digest continues to bind the authoritative command text from implementation evidence; the execution contract supplies the separate executable binding that the managed producer can run and observe.
