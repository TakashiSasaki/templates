# ADR-0012: Digest-bound Policy build backend closure

## Status

Accepted for implementation.

## Context

The trusted Policy runtime builder installs the selected toolchain from an exact
Git commit, but pip builds that Git source with PEP 517 isolation enabled. The
selected commit `aa6f9ac4822cbbb9b7bb6940525d54ad690d76d3` has
`pyproject.toml` blob `0fe1e7498c9c7746defcac6cd40c830701a90ba0` and declares
`build-backend = "hatchling.build"` and `requires = ["hatchling>=1.25"]`.
`requirements-runtime.lock` omits Hatchling because it contains only final
runtime distributions. pip therefore creates a separate build environment and
may select backend bytes from a package index. The trusted-review workflow
currently exposes GitHub, OIDC, attestation, and package-write capabilities to
the job before this build and before runtime freeze.

The current Policy runtime CI lock selects Hatchling 1.31.0, but its exact
version is not consumed by this Git-source build and does not bind the wheel
bytes. A version constraint alone cannot identify the code that executes.

## Decision drivers

The invariant is that every build backend and executable transitive build
dependency used for the selected Policy toolchain is identified by reviewed
artifact bytes before execution. A selected toolchain's own build-system table
must match the supported reviewed contract. No package-index resolver may run
during the project build, and build-only distributions must stay out of the
final runtime environment. The runtime/cache identity must include the closure
that produced the Policy wheel.

## Options considered

### A. Keep isolated PEP 517 index resolution — rejected

The exact Git SHA pins project source, but does not constrain pip's separate
build environment. An index can supply compatible backend bytes that are not in
the runtime lock and that execute before freeze and attestation.

### B. Pin only the backend version — rejected

An exact `hatchling==1.31.0` requirement still allows a different wheel with
the same package metadata and version. It leaves the executable artifact bytes
unbound and does not close transitive build dependencies.

### C. Reviewed artifact closure and deterministic builder — selected

Policy owns a strict build-closure document containing the exact supported
build-system declaration and direct wheel URLs, filenames, versions, and
SHA-256 digests for Hatchling and every active transitive build dependency.
Downloads are data until every digest and wheel identity verifies. A separate
builder environment receives only those verified wheels; the exact Git source
is checked out and its `pyproject.toml` is validated before the backend is
imported. Dynamic build requirements must match the reviewed closure. The
project wheel is built with isolation and index resolution disabled, then
installed into a separate runtime environment that contains only the runtime
lock plus the Policy project wheel.

Trusted-review construction stages and verifies the wheel closure in a
credential-minimal workflow job and builds the selected Policy wheel there.
The privileged job verifies the source, closure, and wheel identities and
installs the prebuilt wheel without executing the backend. Ordinary local
runtime construction can perform the same digest-checked build in its
disposable builder environment.

The runtime/cache identity binds the toolchain commit, runtime-lock digest,
build-closure digest, backend artifact digest, builder-contract version, and
the existing Python/platform identity. Old cache entries without those fields
cannot satisfy the new identity.

### D. Publish and consume a prebuilt stable Policy wheel — deferred

A promoted wheel with a reviewed digest and independent attestation could avoid
per-run source builds. The current release lifecycle publishes a Git toolchain
revision and installer source, not a stable Policy wheel artifact. Introducing
one would add a new publication, attestation, promotion, retention, and
self-hosting identity to the release lifecycle. A run-scoped wheel built from
the exact selected Git source in the credential-minimal stage provides the
required boundary without introducing that new release authority. Revisit this
option only as a separately reviewed release-lifecycle change.

## Consequences

- Build backend artifact hashes and exact direct URLs become Policy-owned
  reviewed inputs; version pins alone are insufficient.
- Unsupported or expanded `pyproject.toml` build-system declarations fail
  closed until the closure and contract are reviewed together.
- Trusted-review workflow construction needs a low-permission build stage and
  an authenticated main-job check that binds its output to the observed base.
- Build-only packages remain absent from the runtime installed set.
- The stable toolchain and installer publication pins remain unchanged during
  implementation. A later promotion and Site re-adoption remain separate
  reviewed steps.

## Validation record

The selected toolchain source and build declaration are bound to the full Git
revision and pyproject blob above. Artifact SHA-256 values are copied from the
exact universal-wheel records for their named PyPI releases and independently
checked against downloaded bytes before any wheel is installed or executed.
`tests/test_legacy_pep517_reproduction.py` runs the old `pip install --no-deps
git+https://...@<full-sha>` command against the exact selected Git source,
rewritten to a local object mirror, and a loopback-only package index. That index
serves a controlled Hatchling-compatible wheel labeled `1.31.0`; the isolated
build environment requests it and executes its sentinel hook even though the
runtime lock does not list Hatchling. The fixture keeps the reproduction
deterministic and avoids executing an unreviewed public artifact. Focused
regressions also cover metadata-preserving artifact substitution, unsupported
build declarations, missing/expanded dependencies, offline build, runtime
separation, and cache identity.
