# Skill and capability responsibility map

| Concern | Authority |
|---|---|
| Trigger, exclusions, workflow | `artifact.skill-core` / `SKILL.md` |
| Operational references | `artifact.skill-core` / `SKILL.md` + `references/` |
| Static assets | `artifact.skill-core` / `SKILL.md` + `assets/` |
| Private helper scripts | `artifact.skill-core` / `SKILL.md` + `scripts/` |
| Preferred agent route and fallback | `artifact.skill-core` / `SKILL.md` |
| Runtime, commands, dependency workflow | `capability.runtime` |
| Packaged CLI behavior | `capability.cli` |
| MCP core/transport behavior | `capability.mcp` |
| MCP Apps extension | `capability.mcp-apps` |
| Standalone browser interface | `capability.web-interface` |
| Headless service behavior | `capability.service` |

## Key invariant

Generic capabilities do not name or depend on `artifact.skill-core`. Artifact-specific routing may refer to selected capabilities, but the reusable capability remains usable by other artifact recipes.

## Legacy mapping

| Former Skill contract/profile | Composition authority |
|---|---|
| `INTERFACES.md` agent routing | folded into `SKILL.md` |
| `INTERFACES.md` cross-interface invariants | capability contracts |
| `packaged-cli` | `capability.cli` |
| `mcp-enabled` | `capability.mcp` |
| MCP Apps extension selection | `capability.mcp-apps` |
| `browser-interface` | `capability.web-interface` |
| `headless-service` | `capability.service` |
