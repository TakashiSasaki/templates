# Release execution contract

`lifecycle.release-execution` separates the human-readable authoritative command identity in `contracts/implementation-evidence.json` from the concrete process invocation used by a product-owned release operation.

The contract is artifact-neutral. In product mode, every authoritative implementation-evidence command is bound exactly once to:

- a fixed `argv` array;
- a repository-relative `workingDirectory`.

The contract deliberately does **not** define a shell command language, environment-variable injection, secret lookup, approval policy, or release result. A producer must execute the declared argv directly rather than parsing the human-readable `command` string as shell input.

Template mode is empty. Product mode must exactly cover the command IDs declared by product-mode implementation evidence. `validate_release_execution.py` checks this mode and identity closure. Schema validation additionally constrains argv values and rejects unsafe working-directory forms such as absolute paths, traversal segments, and `.git` paths.

Execution results remain the responsibility of `lifecycle.release-evidence`. The release-evidence command digest continues to bind the authoritative command text from implementation evidence; the execution contract supplies the separate executable binding that a later producer can run and observe.
