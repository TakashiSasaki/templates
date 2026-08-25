# Composition installer release

This directory records the immutable publication identities for the installable Composition Agent Skill. It is a release-publication surface, not the installed skill's runtime authority.

The stable publication deliberately separates three full-SHA identities:

- **installer script revision** `9c1c093fca1e7e47a9974150e7739665ec570f6e` — the remotely executed stdlib-only bootstrap script;
- **skill source revision** `f9508b92f5b7835fa1af9741f3941f32f6d3db28` — the `skills/composition/` tree downloaded and atomically installed by that bootstrap script; and
- **stable Composition toolchain revision** `423d30c647238eee3fd4064ab0a02aac7f527bd6` — the exact Composer source selected by the installed skill's `runtime-manifest.json`.

`composition-installer.json` is the machine-readable authority for these identities. `scripts/verify_composition_skill_installer_release.py` verifies the descriptor against repository history and the referenced files.

## Immutable one-line installation

Install the published skill with an installer URL pinned to the installer script revision:

```bash
python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/TakashiSasaki/templates/9c1c093fca1e7e47a9974150e7739665ec570f6e/scripts/install_composition_skill.py', timeout=30).read())" /path/to/agent-skills/composition
```

For an existing Composition skill installation, append `--replace`. Replacement remains guarded by the local skill installer and is accepted only when the destination is already identified as this skill.

The command above never executes the mutable `composition` branch or a tag. Normal Composition operations are performed through the installed skill runner; this release surface does not introduce a global Composer CLI.