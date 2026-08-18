# Release evidence lifecycle

`lifecycle.release-evidence` binds one exact product revision to authoritative command and release-gate definitions in `implementation_evidence`.

Template mode carries no product claims. Product mode records execution provenance, command-definition SHA-256 digests, command outcomes, gate outcomes, and an approved/rejected release decision.

Product validation requires an explicit immutable expected revision and verifies exact gated-command/gate coverage, command-definition digest equality, successful outcomes, and chronology from command execution through approval and evidence generation.

This lifecycle does not choose a CI provider, package manager, deployment system, or approval mechanism.
