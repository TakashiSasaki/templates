# Reusable capabilities

This is the Site-owned reader index for reusable capabilities. The canonical
capability semantics and source documents are owned by the `composition`
provider; this page only supplies the stable `/capabilities/` reader entry point
and groups published destinations.

Artifact identity is a separate decision. A browser product chooses `website`
or `webapp` from its caller-visible product model, while optional capabilities
such as runtime, PWA, or standalone interfaces are selected only when their own
behavior applies. Start with [Choose Website or Web application](../web/) when
you have not yet chosen the browser artifact.

For the Composition-level explanation of component roles and dependency
closure, see [Composition concepts](../composition/concepts/).

## Implementation runtime

Defines how a product is implemented and run, including its language/runtime,
dependency workflow, commands, environment, distribution, and deployment
choices. Runtime selection does not decide whether a browser product is a
Website or Web application.

- [Implementation runtime decision record](runtime/)
- [Choosing an implementation runtime](runtime/selection/)

## Interfaces

Defines how users, agents, browsers, or other systems interact with a product.
Interface contracts describe caller-visible behavior separately from artifact
identity and from the implementation-runtime choices above.

- [Packaged CLI interface](cli/)
- [MCP interface](mcp/)
- [MCP transports](mcp/transports/)
- [MCP Apps interface](mcp-apps/)
- [MCP Apps guidance](mcp-apps/guidance/)
- [Standalone browser interface](browser/)
- [Headless service interface](service/)

## Browser products

Website and Web application are sibling artifact identities. Both receive the
shared `foundation.web` browser baseline transitively; consumers do not select
that foundation as an optional capability. The shared baseline owns browser
identity, generalized routes, and viewport expectations.

- [Choose Website or Web application](../web/) — select the browser artifact by
  product identity rather than static/dynamic rendering, hosting, or runtime.
- [Website](../website/) — content/document-oriented browser products.
- [Web application](../webapp/) — task/state/action-oriented browser products.
- [Progressive Web App capability](pwa/) — optional for either Website or Web
  application when installability, offline/freshness, platform application
  identity, and update behavior are part of the supported product contract.

The separate [Policy PWA usage guide](../policy/pwa/) documents install and use
of the Policy documentation site itself. It is not the reusable PWA capability
authority.

Browser and operating-system mechanisms can differ. Follow the Composition
source for product invariants and evidence boundaries rather than treating a
current browser install prompt or platform-specific presentation detail as Site
authority.

The public paths above are Site publication destinations. Their provenance in a
built artifact resolves to the exact Composition revision recorded in
`build-provenance.json`.
