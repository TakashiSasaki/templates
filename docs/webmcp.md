# WebMCP

WebMCP is an optional browser-context interface that lets an AI agent discover and invoke product-defined tools while operating in the authenticated browser context. In this repository, the semantic authority is Composition's `capability.webmcp`; this Site page is a reader-facing guide and does not redefine the contract.

## Should I adopt it?

Adopt WebMCP when a Website or Webapp has meaningful domain operations that should be callable by browser agents and those operations can reuse the same authorization, validation, confirmation, state-transition, and side-effect semantics as the human-facing product.

Do not adopt it merely to expose UI controls. A useful WebMCP inventory is expressed in domain intent such as search, retrieve, update, or initiate a guarded workflow.

Composition represents three distinct consumer intentions:

| Intent | Composition selection | Meaning |
| --- | --- | --- |
| Default | neither include nor exclude | unspecified/default intent |
| Adopt | include `capability.webmcp` | explicit adoption |
| Explicitly exclude | exclude `capability.webmcp` | durable explicit non-adoption |

The last two states remain distinct even while the current recipe default does not select WebMCP.

## WebMCP compared with related interfaces

**WebMCP vs MCP.** WebMCP is a browser-context capability and does not require a backend MCP server. Selecting either capability does not imply the other.

**WebMCP vs MCP Apps.** MCP Apps is a separate capability and is not selected by WebMCP. WebMCP does not require an MCP runtime or MCP Apps host.

**WebMCP vs ordinary Web UI.** Human UI remains a first-class interface. WebMCP should adapt the same domain/application operations rather than create a privileged alternate business path.

## Security implications

WebMCP execution must not bypass product authorization, input validation, required confirmation, state-transition rules, or externally observable side-effect semantics. An authenticated browser session provides context; it is not sufficient authorization for every operation.

Treat tool metadata and untrusted tool output as injection/trust-boundary inputs. Consequential actions retain the product's confirmation rules. Registration must not remain stale when route, state, session, or owning UI lifetime changes.

The Composition v1 contract defaults to same-origin exposure. Cross-origin exposure is an explicit contract choice requiring a narrow HTTPS allowlist, WebMCP Permissions Policy handling, and positive/negative browser evidence for allowed and denied origins.

## Imperative and declarative WebMCP

The current templates v1 product profile is **imperative WebMCP** through `document.modelContext`. Declarative WebMCP is treated as experimental/informative rather than a product baseline. Composition evolves this promise through immutable source revisions, component/contract schema versions, migrations, and implementation evidence rather than a consumer-selectable upstream specification revision.

## Verify the selection

The Composition Playground presents WebMCP as **Default / Adopt / Explicitly exclude**. Its validity, conflict, resulting materials/contracts, dependency reasons, and explainability come from the exact pinned Composition provider projection; the browser UI does not implement a dependency resolver.
