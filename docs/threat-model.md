# Threat model

Primary risks include mutable executable references, path traversal, symbolic-link escape, accidental overwrite of handwritten instructions, stale generated files, and privileged cross-repository tokens. The design pins executable commits, constrains paths, marks generated files, defaults initialization to dry-run, and performs repository-local synchronization through reviewable changes.
