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
