# Generated artifact transport and mutation payload classification

Repository-change orchestration must classify a payload before choosing how to mutate or transport it. The classification is provider-neutral and applies whether the change is implemented through a local checkout, an API/connector, a browser automation surface, or another repository mutation mechanism.

## Required classification

For every planned file payload that is large, binary, encoded, generated, or otherwise transport-sensitive, classify it as exactly one of these roles before mutation:

1. **Git-tracked authority source** — hand-maintained or generated source that the repository intentionally versions and treats as an authority input.
2. **Generated build product** — deterministic output derived from authority source and not itself an authority input.
3. **External artifact** — a product whose durable home is an artifact store, release asset, object store, package registry, or another surface outside the Git tree.

The classification must be based on the repository's authority and generation contracts, not merely on the file extension. Binary content can be source; textual JSON can be a generated build product.

## Transport planning

Before mutation, record enough transport facts to select a safe mechanism:

- whether the payload belongs in Git at all;
- expected or observed byte size;
- text versus binary encoding requirements;
- whether the mutation API requires whole-file replacement, base64, multipart upload, Git blob creation, or another representation;
- whether a deterministic provider-owned generator/materializer can reconstruct the payload from smaller tracked source;
- whether the transport mechanism has practical payload, request, logging, or transcript limits.

Do not solve a transport problem by changing the authority model. In particular, do not make a generated projection canonical source merely because the source API is easier to call, and do not add a generated build product to Git solely to move it between execution environments.

## Generated build products

Prefer deterministic provider-owned generation or materialization over transporting generated build products through repository mutation APIs. The provider contract should identify the tracked inputs, generator/materializer entry point, output inventory, deterministic validation, and provenance needed by consumers.

A generated build product must remain reproducible from its authority source. If a consumer needs the product at build time, arrange materialization at the consumer/provider boundary rather than copying a repository-external binary into version control without an explicit authority decision.

## Binary and encoded payloads

Do not default to huge inline base64 payloads in a mutation request, chat transcript, PR comment, or similar textual control plane. Base64 expands data and can exceed request or logging limits while obscuring the real authority boundary.

If a binary payload legitimately belongs in Git, prefer a mutation mechanism designed for binary/blob transport and verify the resulting object identity. If it does not belong in Git, use its declared artifact transport or regenerate it at the destination.

## Failure handling

If the available mutation surface cannot safely carry an authority-source payload that must be Git-tracked, stop that mutation path and select another supported transport. Do not silently substitute a generated product, lossy encoding, truncated content, or unverified external copy.

If deterministic regeneration is available, transport or mutate the tracked source and generator contract instead, then validate the materialized product at the exact resulting revision.

## Work ledger interaction

When the classification affects execution or resumption, record the payload role and chosen transport in the repository-change Work ledger. The ledger records the operational decision; it does not become the authority source or a duplicate artifact store.
