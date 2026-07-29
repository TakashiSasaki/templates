# Implementation source

Replace this file with the concrete skill implementation after selecting a runtime in `RUNTIME.md`.

The exact source layout is runtime-specific. Examples include a Python `src/<package>/` layout, a TypeScript `src/` layout, or a compiled-language package layout. The template does not prescribe one.

Regardless of language, separate:

- domain rules and value objects;
- application/use-case orchestration;
- CLI parsing and presentation;
- MCP protocol adaptation;
- filesystem, network, and subprocess infrastructure.

The CLI and MCP layers must depend on the application layer, not on each other.
