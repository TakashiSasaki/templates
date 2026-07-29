# Architecture

## Package boundary

The repository root is both the development repository and the deployable skill directory. A clone, submodule checkout, or release archive should not require another wrapping directory.

## Layers

```text
SKILL.md and references
        |
        v
public execution policy
        |
        +-------------------+
        |                   |
        v                   v
      CLI adapter       MCP adapter
        |                   |
        +---------+---------+
                  v
          application layer
                  v
             domain core
                  v
 infrastructure/filesystem/network
```

The specific filenames depend on the selected implementation language. The dependency direction does not.

## Skill instructions

`SKILL.md` defines when the skill applies, required workflow, safety constraints, and the stable execution entry point. It should not become a complete developer manual.

## Public adapters

The CLI serves humans and may also provide the stable process interface used by an agent. The optional MCP server exposes typed protocol tools. Both adapters must translate to the same application operations.

## Application and domain

Application code coordinates use cases. Domain code implements the rules being protected by the skill. Neither layer should know whether a request originated from CLI or MCP.

## Runtime-loaded references versus maintainer docs

- `references/`: potentially loaded during skill execution;
- `docs/`: used to develop and maintain the skill.

This distinction limits unnecessary context while keeping the repository understandable.

## Distribution

A release may include the whole repository or a reduced skill bundle. If a reduced bundle is produced, it must retain everything needed for in-place execution and must preserve relative paths referenced by `SKILL.md`.
