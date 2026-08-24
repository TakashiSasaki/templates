# Composition installer release

This directory records the immutable publication identities for the installable Composition Agent Skill. It is a release-publication surface, not the installed skill's runtime authority.

The stable publication deliberately separates three full-SHA identities:

- **installer script revision** `7412e9545e7648ddd8b3f4c05fe9ef171887d15b` — the remotely executed stdlib-only bootstrap script;
- **skill source revision** `5b93c5628cd3cf7e72393dc3999a70aeb2b2a826` — the `skills/composition/` tree downloaded and atomically installed by that bootstrap script; and
- **stable Composition toolchain revision** `cd19bf8edacc146cd928b6175429e62985f17670` — the exact Composer source selected by the installed skill's `runtime-manifest.json`.

`composition-installer.json` is the machine-readable authority for these identities. `scripts/verify_composition_skill_installer_release.py` verifies the descriptor against repository history and the referenced files.

## Immutable one-line installation

Install the published skill with an installer URL pinned to the installer script revision:

```bash
python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/TakashiSasaki/templates/7412e9545e7648ddd8b3f4c05fe9ef171887d15b/scripts/install_composition_skill.py', timeout=30).read())" /path/to/agent-skills/composition
```

For an existing Composition skill installation, append `--replace`. Replacement remains guarded by the local skill installer and is accepted only when the destination is already identified as this skill.

The command above never executes the mutable `composition` branch or a tag. Normal Composition operations are performed through the installed skill runner; this release surface does not introduce a global Composer CLI.