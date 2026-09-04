# Bootstrap operation

## Role

Bootstrap is the unmanaged-repository operation of the single `skills/agent-policy/` skill. Empty repositories use fresh adoption; repositories with existing handwritten instructions use migration adoption. There is no separately installed bootstrap skill.

The skill never executes the mutable `policy` branch tip. `runtime-manifest.json` pins a reviewed full commit SHA from `TakashiSasaki/templates` and the SHA-256 of that revision's `requirements-runtime.lock`. Bootstrap and managed operation share the same persistent runtime-cache implementation.

## Install the published skill

The recommended remote installation command executes an installer script from one immutable full-SHA URL:

```bash
python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/TakashiSasaki/templates/cc9c7b26168dd5875c485e8fc9343fa57d9f44a8/scripts/install_agent_policy_skill.py', timeout=30).read())" /path/to/agent-skills/agent-policy
```

Append `--replace` only when replacing an existing `agent-policy` skill installation.

The distribution uses three distinct revision roles:

- **installer script revision** `cc9c7b26168dd5875c485e8fc9343fa57d9f44a8` pins the remotely executed bootstrap script;
- **skill source revision** `22af789aa6e41c646f874d26c4885dd54584e690` pins the `skills/agent-policy/` subtree downloaded by that script; and
- the **stable runtime revision** in `runtime-manifest.json` independently pins the canonical CLI runtime used after installation.

`release/skill-installer.json` publishes the installer/skill-source pair. Neither the command nor the remote installer executes the mutable `policy` branch, a tag, or a short SHA.

A reviewed checkout can also install the skill tree from that checkout:

```bash
python skills/agent-policy/scripts/install.py \
  /path/to/agent-skills/agent-policy
```

Use `--replace` only when replacing an existing skill with the same identity. The local installer refuses a symlink target, an overlapping source/destination, or replacement of a directory whose `SKILL.md` does not identify `agent-policy`.

The local-checkout path is intended for repository development and review. It is not necessarily byte-for-byte identical to the currently published remote distribution unless the checkout matches the skill-source revision in `release/skill-installer.json`. Use the published remote installer when reproducing the published distribution is required.

## Skill contents

```text
skills/agent-policy/
  SKILL.md
  README.md
  runtime-manifest.json
  scripts/
    bootstrap.py
    install.py
    run.py
    runtime.py
    uninstall.py
```

`runtime.py` selects the immutable toolchain, constructs or reuses the persistent runtime cache, and verifies the installed distribution set. `bootstrap.py` handles unmanaged adoption. `run.py` handles managed operation using `.agent-policy.lock`.

The normal consumer entry points are these installed `scripts/bootstrap.py` and `scripts/run.py` wrappers. Direct `agent-policy ...` commands documented in the CLI and adoption reference describe the canonical toolchain CLI. Installing the skill does not by itself install an `agent-policy` executable globally on `PATH`.

## Repository inspection and dry run

Run from the installed skill directory:

```bash
python scripts/bootstrap.py --repository /path/to/product
```

The command does not modify files by default. It invokes `agent-policy adopt inspect` through the pinned runtime and reports one of the following states:

| State | Adoption strategy |
|---|---|
| `unmanaged-empty` | fresh adoption |
| `unmanaged-existing` | migration adoption |
| `managed` | stop bootstrap and use `scripts/run.py` |
| `inconsistent` | make no changes; repair partial adoption or unsafe paths first |

The strategy is derived from repository state. There is no user-selectable `init` route.

## Apply fresh adoption

For `unmanaged-empty`, review the dry-run plan and then authorize the inspected transition:

```bash
python scripts/bootstrap.py \
  --repository /path/to/product \
  --apply
```

The pinned toolchain may use `agent-policy init` internally as a fresh-adoption primitive. After application, `validate` and `check` run through the same pinned runtime. Initialization is not a separate user-facing operation.

## Prepare migration adoption of existing instructions

When inspection finds exactly one supported instruction file, bootstrap selects it automatically. When it finds multiple supported instruction files, choose one authoritative primary source explicitly. If no supported instruction files are discovered, create a supported `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, or `.github/copilot-instructions.md` first; policy or skill assets alone cannot be selected as primary instructions.

When an explicit primary is required:

```bash
python scripts/bootstrap.py \
  --repository /path/to/product \
  --primary-instructions AGENTS.md
```

After reviewing the plan, add `--apply` only when the prepared state should be created:

```bash
python scripts/bootstrap.py \
  --repository /path/to/product \
  --primary-instructions AGENTS.md \
  --apply
```

Omit `--primary-instructions` when inspection selected the only supported instruction file automatically.

Application runs migration preparation and then `adopt preview`. The existing primary instructions are not replaced.

After project policy and the preview have been reviewed, finalization is a separate explicit managed operation through the same skill:

```bash
python scripts/run.py \
  --repository /path/to/product \
  adopt finalize --apply
```

`runtime-manifest.json` and `bootstrap.py` expose no finalize route. Generic bootstrap `--apply` therefore cannot finalize migration.

## Persistent runtime and managed operation

For initial adoption, the skill uses the stable default full SHA in `runtime-manifest.json`. Once `.agent-policy.lock` exists, `scripts/run.py` prefers the repository's full-SHA toolchain pin. Malformed, mutable, or unsupported managed pins fail closed rather than falling back to the default.

Runtime identity includes repository, full revision, runtime-lock SHA-256, Python major/minor, and platform. A valid cache hit is reusable without network access. Cache construction is staged, verified, and switched into place only after `pip check` and exact installed-set verification succeed.

## Trust boundary

Review these components together as the installed skill trust seed and distribution surface:

- the installer publication identity in `release/skill-installer.json`;
- the full-SHA remote installer script `scripts/install_agent_policy_skill.py`;
- the safety constraints in `SKILL.md`;
- the repository, full SHA, runtime-lock digest, and internal routes in `runtime-manifest.json`;
- runtime selection and cache construction in `scripts/runtime.py`;
- inspection and state-derived adoption logic in `scripts/bootstrap.py`;
- managed command dispatch in `scripts/run.py`;
- installer and uninstaller behavior; and
- single-skill, installer-publication, and release-lifecycle tests.

The same skill remains the repository-facing entry point after adoption; authority for the managed toolchain revision transfers to `.agent-policy.lock`.
