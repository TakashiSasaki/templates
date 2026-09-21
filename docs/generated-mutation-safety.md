# Generated-output mutation safety

`agent-policy render` treats generated outputs, obsolete outputs, the generated
lock, and transaction rollback as one ownership-bound mutation family. The
renderer prepares complete files in an operation-private namespace and routes
all public writes, replacement, retirement, rollback, and lock updates through
`agent_policy.generated_mutation.apply_generated_mutations`.

Each binding includes the repository-root identity and the device/inode identity
of every public parent component. Before and after a public rename/detach or
install, the implementation reopens that chain without following links and
checks that the public path still reaches the bound directories. This covers
nested outputs, parents created by the invocation, rollback, obsolete cleanup,
and a lock in a nested path; an open descriptor by itself is not treated as
proof that the public pathname still names the same containment chain.

The approved mutation boundary is descriptor-relative and uses Linux
`renameat2(RENAME_NOREPLACE)` to bind the public name at the destructive
operation. Existing generated files are detached and checked by device/inode,
bytes, and generated ownership before replacement or removal. A concurrent
authored or externally replaced object is preserved; the operation fails closed
and does not retry against the new object. Rollback uses the same no-clobber
binding rule and may change only state still owned by the current invocation.

The structured `MUTATION_INVENTORY` in `src/agent_policy/generated_mutation.py`
is the source for the renderer boundary test. The structural qualification
gate rejects direct `os`, `shutil`, and path-method destructive calls in the
renderer/orchestration layer, including representative `Path(...).replace()`
and `target.unlink()` forms; only the approved mutation module may issue those
operations. Negative self-tests keep that gate from silently becoming a
pathname-shape heuristic. The adversarial tests inject changes immediately
before the real rename/unlink boundaries for create, replace, obsolete
deletion, rollback, and lock updates. They also cover same-inode content
takeover, remove-and-recreate, ancestor/parent replacement, invocation-created
parents, and operation-private cleanup siblings.

The supported render mutation environment must provide descriptor-relative
file operations, no-follow opens, and atomic no-replace rename. There is no
unsafe path-based fallback. If those operations are unavailable, render
returns a diagnostic and leaves the repository unchanged. Existing
repository-internal output symlinks remain a supported compatibility case only
when the lexical link is still bound to the exact validated regular target;
obsolete output paths and lock paths do not follow symlinks.

The lock is part of this contract. A successful render therefore means that
the output mutations and lock replacement were all completed while their
validated bindings remained owned by the invocation. Retained operation-private
state or an unprovable rollback is reported as an authority-needed failure,
not as successful synchronization.
