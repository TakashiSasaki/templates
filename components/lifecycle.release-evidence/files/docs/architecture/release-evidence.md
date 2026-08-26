# Release evidence lifecycle

`lifecycle.release-evidence` binds one exact product revision to authoritative command and release-gate definitions in `implementation_evidence`.

Template mode carries no product claims. Product mode records execution provenance, command-definition SHA-256 digests, command outcomes, gate outcomes, and an approved/rejected release decision.

Product validation requires an explicit immutable expected revision and verifies exact gated-command/gate coverage, command-definition digest equality, successful outcomes, and chronology from command execution through approval and evidence generation.

## Managed producer

The managed producer is `.template-composition/release/produce_release_evidence.py`. Invoke it in Python isolated mode and name the exact candidate revision explicitly:

```sh
python -I .template-composition/release/produce_release_evidence.py --revision <40-hex-revision>
```

Before snapshotting or validating release state, the producer acquires the repository-local shared release lifecycle lock from `.template-composition/release/lifecycle_lock.py`. It holds that lock through candidate verification, proof execution, canonical evidence validation, and any rollback. Bundle production uses the same lock, so a cooperating bundle producer cannot observe or digest a partially replaced evidence lifecycle output.

The standalone producer verifies that repository `HEAD` and all tracked candidate inputs other than the release-evidence lifecycle output match the named revision. This deliberate output exclusion makes the operation safely rerunnable before bundle publication: a previously generated release-evidence document may be replaced by a fresh execution without requiring the user to restore the template seed first.

The locked producer primitive also accepts an explicit set of additional lifecycle outputs owned by a surrounding transaction. The normal one-command release orchestrator uses that internal boundary to exclude the downstream `contracts/release-bundle.json` while it reruns evidence for an already released candidate. This does not weaken the standalone CLI: only the outer transaction that snapshots and can restore both outputs supplies the additional exclusion, and the bundle is regenerated and revision-bound before that transaction commits.

Once locked, the producer snapshots the exact existing `contracts/release-evidence.json` bytes. It validates product-mode implementation evidence and release-execution bindings, then executes the product-owned fixed argv directly without parsing the human-readable authoritative command as shell input. Each proof is bracketed by candidate verification, and proof commands are not permitted to modify the snapshotted canonical release-evidence document themselves.

For the Python invocation forms owned by `lifecycle.release-execution`, the first fixed-argv element `"python"` is a Composition-managed runtime token, not a request to search the ambient `PATH`. After the release-execution validator has proved that the binding is one of the supported exact Python harness invocations, the producer replaces only that validated argv[0] token with its own `sys.executable`. The producer itself must already be running in Python isolated mode, so validators and Python proof harnesses execute under the same explicitly selected interpreter/runtime environment. No other argv token, shell expression, environment variable, or executable name is expanded. Direct repository-harness invocations such as `./scripts/verify.sh` are executed unchanged.

This token rule keeps the revision-bound release contract portable across virtual environments and hosts without embedding a machine-specific absolute interpreter path. It also prevents the opposite failure mode where a literal `python` process lookup silently selects a different interpreter than the managed producer and loses the validated dependency environment. External implementations of the release-execution contract must implement the same managed-token semantics rather than treating `"python"` as an ordinary PATH-resolved executable.

Machine-derived release facts are produced by the tool rather than entered manually: command-definition digests, execution timestamps, command results, release-gate results, approval chronology, and the candidate revision binding. If a proof command fails, the candidate changes during execution, a proof touches canonical evidence, the operation is interrupted, or produced evidence fails revision-bound validation, the exact release-evidence bytes present at operation start are restored while the shared lifecycle lock remains held.

Ignored local state such as a normal ignored virtual environment is not itself asserted to be part of the candidate revision. The producer's candidate claim is about the exact tracked candidate inputs plus the explicit execution bindings, with explicitly owned lifecycle outputs treated separately. Repositories that require hermetic environment identity need a separately reviewed contract for that stronger claim rather than an implicit dependency on ambient ignored files.

This lifecycle does not choose a CI provider, package manager, deployment system, secret source, or external approval mechanism.

Release approval is downstream of implementation evidence. The release evidence producer runs the implementation-evidence release-readiness gate before executing release commands. A product with structurally valid but `deferred` evidence cannot receive an approved release decision; the diagnostic preserves the distinction between an unavailable proof and a malformed contract.
