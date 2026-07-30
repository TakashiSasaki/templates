# Contributing

## Before implementation

1. Read `AGENTS.md` and `SKILL.md`.
2. Identify the smallest selected profile in `docs/skill-profiles.md`.
3. Read and update only the contracts that apply:
   - operational references, assets, or helper scripts: their exact entries and handling instructions in `SKILL.md`;
   - helper scripts with runtime dependencies: the applicable runtime record when one is retained;
   - packaged CLI: `RUNTIME.md` and `INTERFACES.md`;
   - MCP: `RUNTIME.md`, `INTERFACES.md`, and `docs/mcp-transports.md`;
   - browser-facing interface: `RUNTIME.md`, `WEB_INTERFACE.md`, and applicable architecture/deployment documentation;
   - headless network service: the authoritative runtime/service record and applicable security, health, lifecycle, and deployment documentation.
4. Do not retain unsupported placeholder contracts merely to satisfy a generic checklist.
5. Avoid adding unused ecosystem boilerplate.

## Change process

- Keep operational instructions in `SKILL.md` concise and explicit.
- Put runtime-loaded detail in `references/`.
- Put static workflow resources in `assets/`.
- Use `scripts/` for bounded helpers or stable launchers when needed.
- Declare every retained reference, asset, and script by exact path in `SKILL.md`; linked references may supplement but not replace those declarations.
- Do not use symlinks under `references/`, `assets/`, or `scripts/`; retained operational resources must be regular files inside the installable skill.
- Keep CLI, MCP, and Web adapters thin only when those interfaces exist.
- Add tests at the lowest layer that can establish the behavior.
- Update only the public contracts affected by the selected profile.

## Pull requests

Describe:

- the selected profile and behavior changed;
- the operational resource or interface affected;
- the runtime or dependency impact, or state that none applies;
- the tests and profile-aware validation executed;
- any compatibility, security, permission, or portability implications.
