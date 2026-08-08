# Web application template documentation

This directory is the maintainer-facing documentation index for the `webapp` branch. The copyable template has its own consumer-facing index at [`template/docs/index.md`](../template/docs/index.md).

This file is a navigation index following the `index.md` conventions in OKF v0.2 section 8. It does not declare this directory or repository to be a formal OKF bundle.

## Repository operation

- [Operationalization](operationalization.md) — Defines how a generated repository moves from template declarations to product-owned implementation and release evidence.

## Architecture and contracts

- [Architecture index](architecture/index.md) — Groups contract-model, evidence, release, distribution, and readiness documentation for template maintainers.

## Contract migrations

`docs/migrations/` is a closed artifact inventory validated as part of contract evolution, so it intentionally has no `index.md`.

- [Contract manifest v1 to v2](migrations/contract-manifest-v1-to-v2.md) — Migrates the manifest to complete family histories and migration ownership.
- [Routes v1 to v2](migrations/routes-v1-to-v2.md) — Migrates the routes contract from version 1 to version 2.
- [UI states v1 to v2](migrations/ui-states-v1-to-v2.md) — Migrates the UI-states contract from version 1 to version 2.

## Publication maintenance

- [Publication catalog](publication-catalog.md) — Documents the selected Webapp material exported to the unrelated `site` publication branch.
- [Publication catalog data](publication-catalog.json) — Machine-readable source list used by the publication assembly pipeline.

## Copyable documentation

- [Consumer documentation index](../template/docs/index.md) — Shows only documentation that belongs to repositories copied from `template/`.
