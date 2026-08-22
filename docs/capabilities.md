# Application capabilities

This is the Site-owned reader index for reusable application capabilities. The
canonical capability semantics and source documents are owned by the
`composition` provider; this page only supplies the stable `/capabilities/`
reader entry point and groups the published destinations.

For the Composition-level explanation of how these components participate in a
composition, see the [Composition documentation index](../composition/docs/#reusable-application-capabilities).

## Implementation runtime

Defines how the application is implemented and run, including its
language/runtime, dependency workflow, commands, environment, distribution,
and deployment choices.

- [Implementation runtime decision record](runtime/)
- [Choosing an implementation runtime](runtime/selection/)

## Interfaces

Defines how users, agents, browsers, or other systems interact with the
application. Interface contracts describe caller-visible behavior separately
from the implementation-runtime choices above.

- [Packaged CLI interface](cli/)
- [MCP interface](mcp/)
- [MCP transports](mcp/transports/)
- [MCP Apps interface](mcp-apps/)
- [MCP Apps guidance](mcp-apps/guidance/)
- [Standalone browser interface](browser/)
- [Headless service interface](service/)

The public paths above are Site publication destinations. Their provenance in a
built artifact resolves to the exact Composition revision recorded in
`build-provenance.json`.
