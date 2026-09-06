# WebMCP for Website and Web application consumers

This is the Site-owned reader guide to Composition's optional `capability.webmcp`. **Composition remains the semantic authority** for component selection, contracts, schemas, validation, and implementation-evidence requirements; this page does not redefine those rules.

## What is WebMCP?

WebMCP is a browser-context interface that lets an AI-capable browser discover and invoke meaningful product tools exposed by a page. The current Composition v1 profile targets the imperative `document.modelContext` API. WebMCP can exist without a backend MCP server and is independent of MCP, MCP Apps, runtime, and the standalone Web-interface capability.

Selecting Website or Web application does not select WebMCP. Selecting WebMCP does not select MCP, MCP Apps, runtime, or the standalone Web interface.

## Should I adopt it?

Adopt WebMCP when the product has stable domain operations useful to an agent in the authenticated browser context and those operations can share the same authorization, validation, confirmation, state-transition, and side-effect semantics as the human-facing product path.

Do not adopt it merely to expose UI controls. Tool boundaries should express user/domain intent rather than low-level actions such as clicking a button.

Composition represents three distinct intentions:

| Intent | Composition selection | Meaning |
| --- | --- | --- |
| Default | neither include nor exclude | unspecified/default intent |
| Adopt | include `capability.webmcp` | explicit adoption |
| Explicitly exclude | exclude `capability.webmcp` | durable explicit non-adoption |

Explicit non-adoption is not equivalent to omission even while the current recipes do not select WebMCP by default.

## WebMCP vs MCP

MCP is a protocol/interface capability that can be used outside a browser page. WebMCP is a browser-context capability. A product may expose either, both, or neither; selection of one does not imply the other.

## WebMCP vs MCP Apps

MCP Apps adds application UI/resource semantics around MCP. WebMCP instead exposes tools from the browser context. Selecting either capability does not imply the other.

## WebMCP vs ordinary Web UI

Human UI remains a first-class interface. Where Human UI and WebMCP reach the same domain operation, they should converge on shared application/domain code. A WebMCP callback must not become a privileged alternate implementation that bypasses rules enforced by the human UI or API.

## Security implications

WebMCP execution must not bypass product authorization, input validation, required confirmation, state-transition rules, or externally observable side-effect semantics. An authenticated browser session provides context; it is not sufficient authorization for every operation.

Treat prompt injection, tool metadata poisoning, untrusted tool output, sensitive input/output, stale registration, confused-deputy behavior, and Human UI/WebMCP path divergence as explicit trust-boundary concerns. Upstream annotations or hints are interoperability metadata, not security authority.

Same-origin/narrow exposure is the default. Cross-origin exposure is an explicit Composition contract choice requiring a narrow allowlist, relevant Permissions Policy handling, and positive and denied-origin browser evidence.

## Imperative and Declarative WebMCP

The current Composition v1 product profile is **Imperative WebMCP** through `document.modelContext`. **Declarative WebMCP** remains experimental/informative rather than part of the current product contract. Consumer-visible evolution is handled through immutable Composition revisions, component/schema versions, migrations, and lifecycle evidence rather than a second consumer-selected upstream specification revision.

## Verify the selection

The Composition Playground presents **Default / Adopt / Explicitly exclude**. Validity, conflicts, resulting materials/contracts, dependency reasons, and explainability come from the exact pinned Composition provider projection; Site browser code does not implement the dependency resolver.

For implementation work, use the provider-owned `WEBMCP.md`, tool-design, security, testing, machine-contract, and implementation-evidence materials supplied by `capability.webmcp`.
