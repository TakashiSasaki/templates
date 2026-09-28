# Repository test worker-budget contract

This contract bounds local test and preflight concurrency across the five
independent authority worktrees. It governs process orchestration only. Each
authority retains its test definitions, discovery rules, validation meaning,
and native runtime.

## Runner-local budgets

Where a canonical runner accepts `--jobs N`, `N` is an integer of at least one
and caps the maximum simultaneously active test workers owned by that runner.
`--jobs 1` is the serial baseline: the runner must not start xdist workers,
parallel unittest shards, Node test-file workers, or concurrent check tasks.
Runners pass explicit limits to nested schedulers and never infer a worker count
from the machine or use an unbounded `auto` setting. They report both requested
and effective worker counts, including when safety or available work reduces
the effective count.

The global coordinator's `--jobs` value is shared across all selected authority
runners. It allocates child budgets whose active sum does not exceed that global
limit; it must not forward the same global value to every authority. A direct
authority invocation treats `--jobs` as that runner's local limit.

The Policy cross-authority coordinator builds a fixed, ordered batch plan before
starting children. Each child receives its allocated local `--jobs` value, and
the allocation sum for every concurrently active batch is at most the requested
global budget. When there are more authorities than worker slots, later batches
wait for earlier ones to finish. The result records the allocation per authority
and batch; authority-process count is reported separately from worker count.
There is no runtime rebalancing.

Environment variables and project configuration must not silently increase a
requested limit. A runner that owns nested parallelism clears or explicitly
overrides inherited worker options before launching its test runtime.

## Execution boundaries

The common contract does not unify test runners:

- Policy uses pytest and pytest-xdist.
- Composition uses Python `unittest` and its deterministic test-ID sharding.
- Site keeps Python `unittest` and Node's built-in `node --test` in separate
  execution domains. Node tests load the shipped Composition Playground
  JavaScript directly, so URL handling, rendering, events, fetch, clipboard,
  and asynchronous behavior remain tested in a JavaScript runtime.
- Integration uses Python `unittest` discovery.
- Modeling uses Python `unittest` discovery.

Each authority's qualification entrypoint remains responsible for its own
inventory and results. The coordinator may start, bound, log, and aggregate
those commands, but it cannot redefine their test semantics.

## Timeout cleanup

On POSIX, each authority command starts in its own session and process group.
On timeout, the coordinator sends `SIGTERM` to that group while draining both
captured output streams for at most one second, then sends `SIGKILL` and drains
the direct authority process. The result remains `TIMEOUT`; successful runs do
not enter the termination path.

On Linux, each authority supervisor temporarily uses
`PR_SET_CHILD_SUBREAPER`. It locates adopted descendants through their parent
PIDs in standard `/proc/<pid>/stat` records, so cleanup does not depend on the
optional `/proc/<pid>/task/<pid>/children` interface. The supervisor signals
and reaps adopted descendants, including children that detached from the
authority process group. If Linux subreaper support or readable process records
are unavailable, it fails before launching the authority command. Process
records are scanned only to discover and finalize that supervisor's children;
the coordinator does not inspect process command lines or use timing sleeps.

Other POSIX systems do not expose a portable subreaper API through Python. The
coordinator signals their authority process group and reaps the direct child;
the operating system's init process owns orphaned grandchildren. On those
systems, descendants that create a new session or process group are outside
the process-group cleanup contract. The termination grace is bounded at one
second; after `SIGKILL`, final process exit and reaping depend on the operating
system scheduling the killed processes.

## Parallel-safety classes

- `parallel/process`: read-only source, process-local environment or monkeypatch
  state, and test-local temporary data. Process separation is sufficient.
- `isolated-workspace`: generated output, Git worktrees, or other filesystem
  state that is safe only in an independent temporary workspace or clone.
- `exclusive`: canonical worktree writes, shared output paths, shared Git state,
  or temporary edits to files another test reads. These tests run alone until
  their writes are isolated.

Putting an `exclusive` test in an xdist group does not serialize it against
other groups. The scheduler must place it in a separate execution phase or
otherwise provide real exclusion. Unclassified full-suite tests default to the
serial/exclusive lane until their isolation is reviewed.

## Qualification evidence

For performance or equivalence claims, record the exact full Git SHA, requested
and effective workers, discovered test inventory, result counts and skips, and
wall-clock time for both `--jobs 1` and the selected parallel budget. Compare
the same intended test IDs and preserve the clean worktree and unchanged HEAD.
Use `--jobs 1` to reproduce the deterministic serial baseline when debugging.
