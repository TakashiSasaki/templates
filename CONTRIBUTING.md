# Contributing

## Before implementation

1. Read `AGENTS.md`.
2. Confirm that `RUNTIME.md` has a selected primary runtime.
3. Confirm the execution policy in `INTERFACES.md`.
4. Avoid adding unused ecosystem boilerplate.

## Change process

- Keep operational instructions in `SKILL.md` concise.
- Put runtime-loaded detail in `references/`.
- Put maintainer-only design material in `docs/`.
- Keep CLI and MCP adapters thin.
- Add tests at the lowest layer that can establish the behavior.
- Update public contracts when behavior changes.

## Pull requests

Describe:

- the behavior changed;
- the interface affected;
- the runtime or dependency impact;
- the tests executed;
- any compatibility or security implications.
