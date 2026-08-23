# Release evidence lifecycle

`lifecycle.release-evidence` binds one exact product revision to authoritative command and release-gate definitions in `implementation_evidence`.

Template mode carries no product claims. Product mode records execution provenance, command-definition SHA-256 digests, command outcomes, gate outcomes, and an approved/rejected release decision.

Product validation requires an explicit immutable expected revision and verifies exact gated-command/gate coverage, command-definition digest equality, successful outcomes, and chronology from command execution through approval and evidence generation.

## Managed producer

The managed producer is `.template-composition/release/produce_release_evidence.py`. Invoke it in Python isolated mode and name the exact candidate revision explicitly:

```sh
python -I .template-composition/release/produce_release_evidence.py --revision <40-hex-revision>
```

The producer first verifies that the repository HEAD and raw tracked bytes still match the named candidate. It validates product-mode implementation evidence and release-execution bindings, then executes the product-owned fixed `argv` directly without parsing the human-readable authoritative command as shell input.

Machine-derived release facts are produced by the tool rather than entered manually: command-definition digests, execution timestamps, command results, release-gate results, approval chronology, and the candidate revision binding. If a proof command fails, the candidate changes during execution, or produced evidence fails revision-bound validation, the canonical `contracts/release-evidence.json` is not left partially updated.

Ignored local state such as a normal ignored virtual environment is not itself asserted to be part of the candidate revision. The producer's candidate claim is about the exact tracked candidate bytes and the explicit execution bindings. Repositories that require hermetic environment identity need a separately reviewed contract for that stronger claim rather than an implicit dependency on ambient ignored files.

This lifecycle does not choose a CI provider, package manager, deployment system, secret source, or external approval mechanism.
