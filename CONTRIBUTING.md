# Contributing

## Before implementation

1. Read `AGENTS.md` and `SKILL.md`.
2. Confirm that `SKILL.md` contains exactly one concrete `Selected profiles:` declaration matching the intended repository shape. Replace `template-scaffold` before adding operational resources or treating the repository as a concrete skill.
3. Use `docs/skill-profiles.md` to verify that the smallest sufficient tags were selected.
4. Read and update only the contracts that apply:
   - operational references, assets, or helper scripts: their exact entries and handling instructions in `SKILL.md`;
   - helper scripts with runtime dependencies: the applicable runtime record when one is retained;
   - `packaged-cli`: completed `RUNTIME.md` and `INTERFACES.md`;
   - `mcp-enabled`: completed `RUNTIME.md`, `INTERFACES.md`, and `docs/mcp-transports.md`;
   - `browser-interface`: completed `RUNTIME.md`, `WEB_INTERFACE.md`, and applicable architecture/deployment documentation;
   - `headless-service`: completed `RUNTIME.md` and applicable security, health, lifecycle, and deployment configuration.
5. Do not retain unsupported placeholder contracts merely to satisfy a generic checklist.
6. Avoid adding unused ecosystem boilerplate.

## Change process

- Keep operational instructions in `SKILL.md` concise and explicit.
- Put runtime-loaded detail in `references/`.
- Put static workflow resources in `assets/`.
- Use `scripts/` for bounded helpers or stable launchers when needed.
- Declare every retained reference, asset, and script by exact path in `SKILL.md`; linked references may supplement but not replace those declarations.
- Do not use symlinks or Git submodules/gitlinks under `references/`, `assets/`, or `scripts/`; retained operational resources must be regular files inside the installable skill.
- Keep CLI, MCP, and Web adapters thin only when those interfaces exist.
- Add tests at the lowest layer that can establish the behavior.
- Update only the public contracts activated by `Selected profiles:`.

## Pull requests

Describe:

- the selected profile tags and behavior changed;
- the operational resource or interface affected;
- the runtime or dependency impact, or state that none applies;
- the tests and profile-aware validation executed;
- any compatibility, security, permission, or portability implications.
